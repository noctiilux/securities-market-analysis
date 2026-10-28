from __future__ import annotations

from datetime import date, datetime
from json import JSONDecodeError
from typing import Any, Dict, List

import httpx

from market_utils import (
    BENCHMARK_MARKET,
    BENCHMARK_TICKER,
    INSTRUMENT_LABELS,
    engine_market as resolve_engine_market,
    market_from_group,
    normalize_market,
)


class MoexClientError(Exception):
    """Базовая ошибка клиента MOEX."""


class TickerNotFoundError(MoexClientError):
    """Ошибка: тикер не найден в MOEX ISS."""


class MoexClient:
    """Клиент для работы с публичным API MOEX ISS."""

    BASE_URL = "https://iss.moex.com/iss"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self._market_cache: dict[str, str] = {}

    @staticmethod
    def _first_number(*values: Any, default: float = 0.0) -> float:
        """Возвращает первое валидное числовое значение из списка."""
        for value in values:
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return default

    async def _get_json(self, url: str, params: dict | None = None) -> Dict[str, Any]:
        """Выполняет HTTP GET запрос и возвращает JSON с базовой обработкой ошибок."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                try:
                    return response.json()
                except (JSONDecodeError, ValueError) as exc:
                    content_type = response.headers.get("content-type", "unknown")
                    snippet = response.text[:200].replace("\n", " ").strip()
                    raise MoexClientError(
                        f"MOEX вернул не-JSON ответ (content-type: {content_type}). "
                        f"Фрагмент ответа: {snippet or '<empty>'}"
                    ) from exc
        except httpx.HTTPStatusError as exc:
            raise MoexClientError(f"Ошибка HTTP от MOEX: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise MoexClientError(f"Сетевая ошибка при обращении к MOEX: {exc}") from exc

    @staticmethod
    def _rows(payload: Dict[str, Any], block: str) -> List[dict]:
        """Преобразует JSON-таблицу MOEX в список словарей."""
        table = payload.get(block, {})
        columns = table.get("columns", [])
        data = table.get("data", [])
        return [dict(zip(columns, row)) for row in data]

    @staticmethod
    def _pick_board(
        boards: list[dict],
        requested_board: str | None = None,
        primary_board: str | None = None,
    ) -> dict | None:
        """Выбирает торговую доску по явному запросу, PRIMARYBOARDID и приоритетам."""
        if not boards:
            return None

        if requested_board:
            wanted = requested_board.upper()
            for row in boards:
                if str(row.get("BOARDID", "")).upper() == wanted:
                    return row

        # PRIMARYBOARDID из metadata MOEX обычно указывает основной режим торгов.
        if primary_board:
            primary = primary_board.upper()
            for row in boards:
                if str(row.get("BOARDID", "")).upper() == primary:
                    return row

        # Приоритет основных режимов для акций/фондов/облигаций/фьючерсов.
        preferred = ["TQBR", "TQTF", "TQIF", "TQTD", "TQTE", "TQOB", "TQCB", "RFUD", "FQBR"]
        for board in preferred:
            for row in boards:
                if str(row.get("BOARDID", "")).upper() == board:
                    return row

        # Fallback: берем доску с лучшей торговой активностью.
        return max(
            boards,
            key=lambda row: (
                float(row.get("LAST") or row.get("MARKETPRICE") or 0),
                float(row.get("VOLTODAY") or 0),
                float(row.get("VALTODAY") or 0),
                float(row.get("NUMTRADES") or 0),
            ),
        )

    @staticmethod
    def _board_priority_score(board: str | None) -> int:
        """Приоритет досок для выбора единственной записи по тикеру."""
        order = ["TQBR", "TQTF", "TQTD", "TQTE", "TQOB", "TQCB", "RFUD", "TQIF"]
        board_norm = str(board or "").upper()
        return len(order) - order.index(board_norm) if board_norm in order else 0

    async def detect_market(self, ticker: str) -> str:
        """Определяет категорию рынка по описанию бумаги MOEX."""
        normalized = ticker.strip().upper()
        cached = self._market_cache.get(normalized)
        if cached:
            return cached

        url = f"{self.BASE_URL}/securities/{normalized}.json"
        try:
            payload = await self._get_json(url, params={"iss.only": "description"})
            rows = self._rows(payload, "description")
            if rows:
                row = rows[0]
                resolved = market_from_group(row.get("GROUP"), row.get("TYPE"))
                self._market_cache[normalized] = resolved
                return resolved
        except MoexClientError:
            pass

        for candidate in ("shares", "bonds", "futures", "etf"):
            engine, moex_market = resolve_engine_market(candidate)
            probe_url = f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/securities/{normalized}.json"
            try:
                payload = await self._get_json(probe_url, params={"iss.only": "securities", "limit": 1})
                if self._rows(payload, "securities"):
                    self._market_cache[normalized] = candidate
                    return candidate
            except MoexClientError:
                continue
        self._market_cache[normalized] = "shares"
        return "shares"

    async def _fetch_candles(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
        market: str,
    ) -> List[dict]:
        """Загружает свечи с MOEX для конкретного рынка."""
        normalized = ticker.strip().upper()
        engine, moex_market = resolve_engine_market(market)
        url = f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/securities/{normalized}/candles.json"
        payload = await self._get_json(
            url,
            params={"from": from_date.isoformat(), "till": to_date.isoformat(), "interval": 24},
        )
        candles_rows = self._rows(payload, "candles")
        if not candles_rows:
            return []

        result: List[dict] = []
        for row in candles_rows:
            begin_raw = str(row.get("begin", ""))[:10]
            if not begin_raw:
                continue
            result.append(
                {
                    "date": date.fromisoformat(begin_raw),
                    "open": self._first_number(row.get("open")),
                    "high": self._first_number(row.get("high")),
                    "low": self._first_number(row.get("low")),
                    "close": self._first_number(row.get("close")),
                    "volume": self._first_number(row.get("volume"), row.get("value")),
                }
            )
        return result

    async def get_security_passport(self, ticker: str, market: str | None = None) -> dict:
        """Паспорт ценной бумаги: идентификаторы, параметры выпуска и котировка."""
        normalized = ticker.strip().upper()
        resolved_market = normalize_market(market) if market else await self.detect_market(normalized)

        description: dict = {}
        url = f"{self.BASE_URL}/securities/{normalized}.json"
        try:
            payload = await self._get_json(url, params={"iss.only": "description,boards"})
            desc_rows = self._rows(payload, "description")
            if desc_rows:
                description = desc_rows[0]
        except MoexClientError:
            description = {}

        quote = await self.get_quote(normalized, market=resolved_market)
        face_value = self._first_number(description.get("FACEVALUE"), default=0.0)
        lot_size = int(self._first_number(description.get("LOTSIZE"), default=1.0))
        matdate_raw = description.get("MATDATE") or description.get("BUYBACKDATE")
        matdate = str(matdate_raw)[:10] if matdate_raw else None

        return {
            "ticker": normalized,
            "name": description.get("NAME") or description.get("SHORTNAME") or quote.get("name") or normalized,
            "short_name": description.get("SHORTNAME") or quote.get("name") or normalized,
            "market": resolved_market,
            "instrument_type": INSTRUMENT_LABELS.get(resolved_market, resolved_market),
            "isin": description.get("ISIN"),
            "reg_number": description.get("REGNUMBER"),
            "currency": description.get("FACEUNIT") or "RUB",
            "lot_size": lot_size,
            "face_value": round(face_value, 4) if face_value else None,
            "coupon_percent": self._optional_float(description.get("COUPONPERCENT")),
            "coupon_value": self._optional_float(description.get("COUPONVALUE")),
            "maturity_date": matdate,
            "issuer": description.get("EMITENT_TITLE") or description.get("ISSUERNAME"),
            "group": description.get("GROUP"),
            "board": quote.get("board"),
            "current_price": quote.get("current_price"),
            "change_percent": quote.get("change_percent"),
            "capitalization": quote.get("capitalization"),
            "volume": quote.get("volume"),
            "turnover": quote.get("turnover"),
        }

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None

    async def get_dividends(self, ticker: str) -> List[dict]:
        """История дивидендов по акции/ETF."""
        normalized = ticker.strip().upper()
        url = f"{self.BASE_URL}/securities/{normalized}/dividends.json"
        try:
            payload = await self._get_json(url)
        except MoexClientError:
            return []
        rows = self._rows(payload, "dividends")
        result: List[dict] = []
        for row in rows:
            registry = row.get("registryclosedate") or row.get("CLOSEDATE")
            if not registry:
                continue
            result.append(
                {
                    "registry_date": str(registry)[:10],
                    "value": self._first_number(row.get("value"), row.get("VALUE")),
                    "currency": row.get("currency") or row.get("CURRENCY") or "RUB",
                }
            )
        return result

    async def get_fundamental(self, ticker: str, market: str | None = None) -> dict:
        """Базовые фундаментальные показатели (дивиденды, доходность облигации)."""
        normalized = ticker.strip().upper()
        resolved_market = normalize_market(market) if market else await self.detect_market(normalized)
        passport = await self.get_security_passport(normalized, market=resolved_market)
        price = float(passport.get("current_price") or 0.0)

        dividend_yield_pct = None
        dividends_12m = 0.0
        if resolved_market in {"shares", "etf"}:
            dividends = await self.get_dividends(normalized)
            cutoff = date.today().toordinal() - 365
            for item in dividends:
                try:
                    reg_date = date.fromisoformat(str(item["registry_date"]))
                except ValueError:
                    continue
                if reg_date.toordinal() >= cutoff:
                    dividends_12m += float(item.get("value") or 0.0)
            if price > 0 and dividends_12m > 0:
                dividend_yield_pct = round((dividends_12m / price) * 100.0, 4)

        yield_to_maturity = None
        accrued_int = None
        if resolved_market == "bonds":
            engine, moex_market = resolve_engine_market("bonds")
            url = f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/securities/{normalized}.json"
            try:
                payload = await self._get_json(url, params={"iss.only": "marketdata,securities"})
                market_rows = self._rows(payload, "marketdata")
                if market_rows:
                    row = market_rows[0]
                    yield_to_maturity = self._optional_float(
                        row.get("YIELDTOMATURITY") or row.get("YIELDATWAPRISE") or row.get("YIELD")
                    )
                    accrued_int = self._optional_float(row.get("ACCRUEDINT"))
            except MoexClientError:
                pass

        pe_ratio = None
        if price > 0 and passport.get("capitalization"):
            # Упрощённая оценка: без отчётности P/E недоступен точно.
            pe_ratio = None

        return {
            "ticker": normalized,
            "market": resolved_market,
            "dividend_yield_pct": dividend_yield_pct,
            "dividends_12m": round(dividends_12m, 4),
            "yield_to_maturity": yield_to_maturity,
            "accrued_interest": accrued_int,
            "coupon_percent": passport.get("coupon_percent"),
            "face_value": passport.get("face_value"),
            "maturity_date": passport.get("maturity_date"),
            "capitalization": passport.get("capitalization"),
            "pe_ratio": pe_ratio,
        }

    async def get_benchmark_history(self, from_date: date, to_date: date) -> List[dict]:
        """История индекса IMOEX для расчёта beta."""
        return await self.get_history(BENCHMARK_TICKER, from_date, to_date, market=BENCHMARK_MARKET)

    async def get_quote(self, ticker: str, board: str | None = None, market: str | None = None) -> dict:
        """Возвращает текущую котировку, изменение и объем торгов по тикеру."""
        normalized = ticker.strip().upper()
        if market:
            resolved_market = normalize_market(market)
        elif normalized in self._market_cache:
            resolved_market = self._market_cache[normalized]
        else:
            resolved_market = "shares"

        engine, moex_market = resolve_engine_market(resolved_market)
        url = f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/securities/{normalized}.json"
        payload = await self._get_json(url)

        securities_rows = self._rows(payload, "securities")
        marketdata_rows = self._rows(payload, "marketdata")

        if not securities_rows and not market:
            resolved_market = await self.detect_market(normalized)
            engine, moex_market = resolve_engine_market(resolved_market)
            url = f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/securities/{normalized}.json"
            payload = await self._get_json(url)
            securities_rows = self._rows(payload, "securities")
            marketdata_rows = self._rows(payload, "marketdata")

        if not securities_rows:
            raise TickerNotFoundError(f"Тикер '{normalized}' не найден")

        self._market_cache[normalized] = resolved_market

        boards_map: dict[str, dict] = {}
        for market_row in marketdata_rows:
            board_id = str(market_row.get("BOARDID") or "").upper()
            if board_id:
                boards_map[board_id] = market_row

        for sec_row in securities_rows:
            board_id = str(sec_row.get("BOARDID") or "").upper()
            if board_id and board_id not in boards_map:
                boards_map[board_id] = sec_row

        board_rows = list(boards_map.values()) if boards_map else (marketdata_rows or securities_rows)
        primary_board = None
        for sec_row in securities_rows:
            primary_candidate = sec_row.get("PRIMARYBOARDID")
            if primary_candidate:
                primary_board = str(primary_candidate)
                break
        selected = self._pick_board(board_rows, board, primary_board=primary_board)
        if not selected:
            selected = securities_rows[0]

        selected_board = selected.get("BOARDID")
        # Берем security row той же доски для дополнительных фундаментальных полей.
        security = next(
            (row for row in securities_rows if row.get("BOARDID") == selected_board),
            securities_rows[0],
        )
        market = next(
            (row for row in marketdata_rows if row.get("BOARDID") == selected_board),
            selected,
        )

        price_candidates = [
            ("LAST", market.get("LAST")),
            ("MARKETPRICE", market.get("MARKETPRICE")),
            ("LCLOSEPRICE", market.get("LCLOSEPRICE")),
            ("PREVWAPRICE", market.get("PREVWAPRICE")),
        ]
        price_source = "UNKNOWN"
        for field_name, raw_value in price_candidates:
            if raw_value is None or raw_value == "":
                continue
            try:
                float(raw_value)
                price_source = field_name
                break
            except (TypeError, ValueError):
                continue

        # Для MOEX корректнее брать LAST + PREVPRICE (или fallback).
        last_price = self._first_number(
            market.get("LAST"),
            market.get("MARKETPRICE"),
            market.get("LCLOSEPRICE"),
            market.get("PREVWAPRICE"),
        )
        previous_close = self._first_number(
            market.get("PREVPRICE"),
            market.get("LCLOSEPRICE"),
            market.get("PREVWAPRICE"),
            default=last_price,
        )
        delta_abs = last_price - previous_close if previous_close else 0.0
        delta_pct = (
            self._first_number(market.get("LASTTOPREVPRICE"))
            if market.get("LASTTOPREVPRICE") is not None
            else ((delta_abs / previous_close) * 100.0 if previous_close else 0.0)
        )

        # VOLTODAY - количество бумаг, VALTODAY - денежный оборот.
        volume = self._first_number(
            market.get("VOLTODAY"),
            market.get("VOLUME"),
            market.get("NUMTRADES"),
        )
        turnover = self._first_number(
            market.get("VALTODAY"),
            market.get("VALUE"),
        )
        num_trades = int(self._first_number(market.get("NUMTRADES"), default=0.0))
        vwap = self._first_number(
            market.get("WAPRICE"),
            market.get("VWAP"),
            market.get("PREVWAPRICE"),
        )
        capitalization = self._first_number(
            security.get("ISSUECAPITALIZATION"),
            security.get("ISSUESIZE"),
        )

        return {
            "ticker": normalized,
            "name": security.get("SHORTNAME") or security.get("SECNAME") or normalized,
            "board": selected_board,
            "available_boards": sorted({str(row.get("BOARDID")) for row in board_rows if row.get("BOARDID")}),
            "current_price": round(last_price, 4),
            "change": round(delta_abs, 4),
            "change_percent": round(delta_pct, 4),
            "volume": round(volume, 2),
            "turnover": round(turnover, 2),
            "num_trades": num_trades,
            "vwap": round(vwap, 4),
            "capitalization": round(capitalization, 2),
            "trading_status": str(market.get("TRADINGSTATUS") or market.get("STATUS") or "").strip() or None,
            "source_field": price_source,
            "last_update": datetime.utcnow(),
        }

    async def get_history(self, ticker: str, from_date: date, to_date: date, market: str | None = None) -> List[dict]:
        """Возвращает дневные свечи по тикеру за указанный период."""
        normalized = ticker.strip().upper()

        if market:
            resolved_market = normalize_market(market)
            result = await self._fetch_candles(normalized, from_date, to_date, resolved_market)
            if result:
                self._market_cache[normalized] = resolved_market
            return result

        cached_market = self._market_cache.get(normalized)
        if cached_market:
            return await self._fetch_candles(normalized, from_date, to_date, cached_market)

        # Быстрый путь: большинство тикеров на вкладке графиков — акции.
        result = await self._fetch_candles(normalized, from_date, to_date, "shares")
        if result:
            self._market_cache[normalized] = "shares"
            return result

        resolved_market = await self.detect_market(normalized)
        result = await self._fetch_candles(normalized, from_date, to_date, resolved_market)
        if not result:
            await self.get_quote(normalized, market=resolved_market)
        elif result:
            self._market_cache[normalized] = resolved_market
        return result

    async def search(self, query: str) -> List[dict]:
        """Ищет инструменты по строке запроса (тикер/название)."""
        q = query.strip()
        if not q:
            return []

        url = f"{self.BASE_URL}/securities.json"
        payload = await self._get_json(url, params={"q": q, "limit": 20})
        rows = self._rows(payload, "securities")

        results: List[dict] = []
        for row in rows:
            secid = row.get("secid")
            shortname = row.get("shortname")
            if not secid or not shortname:
                continue
            results.append({"ticker": secid, "name": shortname, "secid": secid})

        return results

    async def get_popular(self, market: str) -> List[dict]:
        """Возвращает популярные инструменты MOEX по категории рынка."""
        normalized_market = market.lower().strip()
        market_mapping = {
            "shares": ("stock", "shares"),
            "futures": ("futures", "forts"),
            "bonds": ("stock", "bonds"),
            "etf": ("stock", "shares"),
        }
        if normalized_market not in market_mapping:
            raise MoexClientError("Поддерживаемые категории: shares, futures, bonds")

        engine, moex_market = market_mapping[normalized_market]
        url = f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/securities.json"
        payload = await self._get_json(url, params={"iss.only": "securities,marketdata", "limit": 50})

        securities_rows = self._rows(payload, "securities")
        marketdata_rows = self._rows(payload, "marketdata")
        marketdata_by_secid = {row.get("SECID"): row for row in marketdata_rows if row.get("SECID")}

        results: List[dict] = []
        for security in securities_rows:
            secid = security.get("SECID")
            if not secid:
                continue

            market_row = marketdata_by_secid.get(secid, {})
            last_price = self._first_number(
                market_row.get("LAST"),
                market_row.get("MARKETPRICE"),
                market_row.get("LCLOSEPRICE"),
            )
            change_percent = self._first_number(
                market_row.get("LASTTOPREVPRICE"),
                market_row.get("CHANGE"),
                default=0.0,
            )
            volume = self._first_number(
                market_row.get("VOLTODAY"),
                market_row.get("VOLUME"),
                market_row.get("NUMTRADES"),
                default=0.0,
            )

            board = security.get("BOARDID")
            if normalized_market == "etf" and str(board or "").upper() not in {"TQTF", "TQIF"}:
                continue

            results.append(
                {
                    "ticker": secid,
                    "name": security.get("SHORTNAME") or security.get("SECNAME") or secid,
                    "market": normalized_market,
                    "board": board,
                    "last_price": round(last_price, 4),
                    "change_percent": round(change_percent, 4),
                    "volume": round(volume, 2),
                }
            )

        # Убираем дубли по тикеру (разные board одной бумаги), оставляем лучший вариант.
        deduped: dict[str, dict] = {}
        for item in results:
            key = item["ticker"]
            existing = deduped.get(key)
            if not existing:
                deduped[key] = item
                continue
            existing_score = (existing["volume"], self._board_priority_score(existing.get("board")))
            current_score = (item["volume"], self._board_priority_score(item.get("board")))
            if current_score > existing_score:
                deduped[key] = item

        merged = list(deduped.values())
        # Сортируем по объему, чтобы показать наиболее "популярные" бумаги.
        merged.sort(key=lambda item: item["volume"], reverse=True)
        return merged[:25]

    async def get_securities(self, market: str, limit: int = 300, offset: int = 0) -> List[dict]:
        """Возвращает расширенный список инструментов MOEX по категории."""
        normalized_market = market.lower().strip()
        market_mapping = {
            "shares": ("stock", "shares"),
            "futures": ("futures", "forts"),
            "bonds": ("stock", "bonds"),
            "etf": ("stock", "shares"),
        }
        if normalized_market not in market_mapping:
            raise MoexClientError("Поддерживаемые категории: shares, futures, bonds, etf")

        engine, moex_market = market_mapping[normalized_market]
        url = f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/securities.json"

        collected: List[dict] = []
        start = offset
        page_size = 100

        while len(collected) < limit:
            payload = await self._get_json(
                url,
                params={"iss.only": "securities,marketdata", "start": start, "limit": page_size},
            )
            securities_rows = self._rows(payload, "securities")
            marketdata_rows = self._rows(payload, "marketdata")
            if not securities_rows:
                break

            marketdata_by_secid = {row.get("SECID"): row for row in marketdata_rows if row.get("SECID")}
            for security in securities_rows:
                secid = security.get("SECID")
                if not secid:
                    continue
                board = security.get("BOARDID")
                if normalized_market == "shares" and str(board or "").upper() in {"TQTF", "TQIF"}:
                    # ETF/БПИФ вынесены в отдельную вкладку.
                    continue
                if normalized_market == "etf" and str(board or "").upper() not in {"TQTF", "TQIF"}:
                    continue
                market_row = marketdata_by_secid.get(secid, {})
                collected.append(
                    {
                        "ticker": secid,
                        "name": security.get("SHORTNAME") or security.get("SECNAME") or secid,
                        "market": normalized_market,
                        "board": board,
                        "last_price": round(
                            self._first_number(
                                market_row.get("LAST"),
                                market_row.get("MARKETPRICE"),
                                market_row.get("LCLOSEPRICE"),
                            ),
                            4,
                        ),
                        "change_percent": round(
                            self._first_number(market_row.get("LASTTOPREVPRICE"), market_row.get("CHANGE"), default=0.0),
                            4,
                        ),
                        "volume": round(
                            self._first_number(
                                market_row.get("VOLTODAY"),
                                market_row.get("VOLUME"),
                                market_row.get("NUMTRADES"),
                                default=0.0,
                            ),
                            2,
                        ),
                    }
                )
                if len(collected) >= limit:
                    break

            if len(securities_rows) < page_size:
                break
            start += page_size

        # Дедупликация по тикеру: выбираем наиболее ликвидную/приоритетную доску.
        deduped: dict[str, dict] = {}
        for item in collected:
            key = item["ticker"]
            existing = deduped.get(key)
            if not existing:
                deduped[key] = item
                continue
            existing_score = (existing["volume"], self._board_priority_score(existing.get("board")))
            current_score = (item["volume"], self._board_priority_score(item.get("board")))
            if current_score > existing_score:
                deduped[key] = item

        return list(deduped.values())[:limit]

    async def get_orderbook(
        self,
        ticker: str,
        board: str | None = None,
        depth: int = 20,
        market: str | None = None,
    ) -> dict:
        """Возвращает стакан заявок по инструменту."""
        quote = await self.get_quote(ticker, board=board, market=market)
        selected_board = quote.get("board")
        if not selected_board:
            raise MoexClientError("Не удалось определить торговую доску для стакана")

        normalized = ticker.strip().upper()
        resolved_market = normalize_market(market) if market else await self.detect_market(normalized)
        engine, moex_market = resolve_engine_market(resolved_market)
        url = (
            f"{self.BASE_URL}/engines/{engine}/markets/{moex_market}/boards/"
            f"{selected_board}/securities/{normalized}/orderbook.json"
        )
        try:
            payload = await self._get_json(url, params={"depth": depth})
        except MoexClientError:
            # Для публичного режима MOEX стакан может быть недоступен или приходить не в JSON.
            return {
                "ticker": normalized,
                "board": selected_board,
                "bids": [],
                "asks": [],
                "last_update": datetime.utcnow(),
            }
        rows = self._rows(payload, "orderbook")

        bids: list[dict] = []
        asks: list[dict] = []
        for row in rows:
            level = {
                "price": self._first_number(row.get("PRICE")),
                "volume": self._first_number(row.get("QUANTITY"), row.get("VOLUME")),
            }
            if row.get("BUYSELL") == "B":
                bids.append(level)
            elif row.get("BUYSELL") == "S":
                asks.append(level)

        bids.sort(key=lambda level: level["price"], reverse=True)
        asks.sort(key=lambda level: level["price"])

        return {
            "ticker": normalized,
            "board": selected_board,
            "bids": bids[:depth],
            "asks": asks[:depth],
            "last_update": datetime.utcnow(),
        }


# Пример использования:
# import asyncio
#
# async def demo() -> None:
#     client = MoexClient()
#     print(await client.get_quote("SBER"))
#
# asyncio.run(demo())
