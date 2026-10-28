"""Дополнительные маршруты API (экспорт, скринер, алерты, оверлеи)."""

from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from analytics import (
    calculate_indicators,
    calculate_risk_metrics,
    chart_overlays,
    daily_returns,
    run_walk_forward_backtest,
    returns_distribution,
)
from auth import get_current_user
from database import (
    get_db_session,
    get_watchlist_alerts,
    remove_watchlist_alert,
    upsert_watchlist_alert,
)
from export_report import report_to_csv, report_to_pdf_bytes
from forecast import DISCLAIMER, compare_forecast_models
from models import User
from moex_client import MoexClient, MoexClientError, TickerNotFoundError
from schemas import (
    ChartOverlayPoint,
    ChartOverlaysResponse,
    ForecastCompareResponse,
    ForecastMetrics,
    ForecastModelScore,
    ForecastPoint,
    ForecastResponse,
    ReturnsDistributionResponse,
    ScreenerItemResponse,
    TriggeredAlertResponse,
    WalkForwardPeriod,
    WalkForwardResponse,
    WatchlistAlertRequest,
    WatchlistAlertResponse,
)

router = APIRouter(tags=["extended"])


def register_extended_routes(app, moex_client: MoexClient, resolve_market, load_report):
    """Регистрирует расширенные маршруты на приложении FastAPI."""

    @router.get("/api/chart-overlays/{ticker}", response_model=ChartOverlaysResponse)
    async def get_chart_overlays(
        ticker: str,
        from_date: date = Query(..., alias="from"),
        to_date: date = Query(..., alias="to"),
        market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
    ) -> ChartOverlaysResponse:
        if from_date > to_date:
            raise HTTPException(status_code=400, detail="Параметр 'from' не может быть позже 'to'")
        try:
            resolved = await resolve_market(ticker, market)
            candles = await moex_client.get_history(ticker, from_date, to_date, market=resolved)
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MoexClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if len(candles) < 25:
            raise HTTPException(status_code=400, detail="Недостаточно данных для индикаторов")
        raw = chart_overlays(candles)
        bollinger = []
        for row in raw["bollinger"]:
            if row.get("bb_upper") is None:
                continue
            d = row["date"]
            if not hasattr(d, "year"):
                d = date.fromisoformat(str(d))
            bollinger.append(
                ChartOverlayPoint(
                    date=d,
                    bb_upper=row.get("bb_upper"),
                    bb_middle=row.get("bb_middle"),
                    bb_lower=row.get("bb_lower"),
                )
            )
        return ChartOverlaysResponse(
            ticker=ticker.upper(),
            bollinger=bollinger,
            support=raw.get("support"),
            resistance=raw.get("resistance"),
        )

    @router.get("/api/returns-distribution/{ticker}", response_model=ReturnsDistributionResponse)
    async def get_returns_distribution(
        ticker: str,
        from_date: date = Query(..., alias="from"),
        to_date: date = Query(..., alias="to"),
        market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
        bins: int = Query(20, ge=5, le=50),
    ) -> ReturnsDistributionResponse:
        try:
            resolved = await resolve_market(ticker, market)
            candles = await moex_client.get_history(ticker, from_date, to_date, market=resolved)
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MoexClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        dist = returns_distribution(daily_returns(candles), bins=bins)
        return ReturnsDistributionResponse(ticker=ticker.upper(), **dist)

    @router.get("/api/forecast/{ticker}/compare", response_model=ForecastCompareResponse)
    async def compare_forecast(
        ticker: str,
        horizon: int = Query(10, ge=5, le=30),
        lookback_days: int = Query(120, ge=60, le=365),
        market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
    ) -> ForecastCompareResponse:
        to_date = date.today()
        from_date = date.fromordinal(to_date.toordinal() - lookback_days)
        try:
            resolved = await resolve_market(ticker, market)
            candles = await moex_client.get_history(ticker, from_date, to_date, market=resolved)
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MoexClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if len(candles) < 40:
            raise HTTPException(status_code=400, detail="Недостаточно истории для сравнения моделей")
        compared = compare_forecast_models(candles, horizon=horizon)
        best = compared["forecast"]
        forecast_resp = ForecastResponse(
            ticker=ticker.upper(),
            market=resolved,
            method=best.get("method", compared["best_method"]),
            horizon=horizon,
            last_price=float(best.get("last_price", 0)),
            trend=str(best.get("trend", "flat")),
            expected_return_pct=float(best.get("expected_return_pct", 0)),
            points=[ForecastPoint(**p) for p in best.get("points", [])],
            metrics=ForecastMetrics(),
            disclaimer=DISCLAIMER,
        )
        return ForecastCompareResponse(
            ticker=ticker.upper(),
            best_method=compared["best_method"],
            best_mape=compared.get("best_mape"),
            models=[ForecastModelScore(**m) for m in compared["models"]],
            forecast=forecast_resp,
        )

    @router.get("/api/backtest/{ticker}/walkforward", response_model=WalkForwardResponse)
    async def walkforward_backtest(
        ticker: str,
        from_date: date = Query(..., alias="from"),
        to_date: date = Query(..., alias="to"),
        fast: int = Query(20, ge=5, le=50),
        slow: int = Query(50, ge=10, le=200),
        window_days: int = Query(60, ge=30, le=200),
        step_days: int = Query(20, ge=5, le=60),
        market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
    ) -> WalkForwardResponse:
        if fast >= slow:
            raise HTTPException(status_code=400, detail="Параметр fast должен быть меньше slow")
        try:
            resolved = await resolve_market(ticker, market)
            candles = await moex_client.get_history(ticker, from_date, to_date, market=resolved)
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MoexClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        result = run_walk_forward_backtest(candles, fast, slow, window_days, step_days)
        return WalkForwardResponse(
            ticker=ticker.upper(),
            fast_period=fast,
            slow_period=slow,
            window_days=window_days,
            step_days=step_days,
            periods=[WalkForwardPeriod(**p) for p in result["periods"]],
            avg_strategy_return_pct=result["avg_strategy_return_pct"],
            avg_buy_hold_return_pct=result["avg_buy_hold_return_pct"],
        )

    @router.get("/api/report/{ticker}/export.csv")
    async def export_report_csv(
        ticker: str,
        from_date: date = Query(..., alias="from"),
        to_date: date = Query(..., alias="to"),
        market: str | None = Query(None, pattern="^(shares|futures|bonds|etf)$"),
    ) -> Response:
        report = await load_report(ticker, from_date, to_date, market)
        content = report_to_csv(report.model_dump(mode="json"))
        filename = f"{ticker.upper()}_report.csv"
        return Response(
            content="\ufeff" + content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/api/report/{ticker}/export.pdf")
    async def export_report_pdf(
        ticker: str,
        from_date: date = Query(..., alias="from"),
        to_date: date = Query(..., alias="to"),
        market: str | None = Query(None, pattern="^(shares|futures|bonds|etf)$"),
    ) -> Response:
        report = await load_report(ticker, from_date, to_date, market)
        pdf_bytes = report_to_pdf_bytes(report.model_dump(mode="json"))
        filename = f"{ticker.upper()}_report.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/api/screener", response_model=list[ScreenerItemResponse])
    async def screener(
        market: str = Query("shares", pattern="^(shares|futures|bonds|etf)$"),
        lookback_days: int = Query(60, ge=20, le=365),
        universe_size: int = Query(35, ge=10, le=80),
        rsi_min: float | None = Query(None, ge=0, le=100),
        rsi_max: float | None = Query(None, ge=0, le=100),
        sharpe_min: float | None = Query(None),
        sector: str | None = Query(None, description="Группа/сектор из паспорта MOEX"),
        div_yield_min: float | None = Query(None, ge=0),
        limit: int = Query(30, ge=5, le=100),
    ) -> list[ScreenerItemResponse]:
        to_date = date.today()
        from_date = date.fromordinal(to_date.toordinal() - lookback_days)
        try:
            universe = await moex_client.get_securities(market=market, limit=universe_size, offset=0)
        except MoexClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if not universe:
            return []

        universe.sort(key=lambda row: float(row.get("volume") or 0), reverse=True)
        need_passport = bool(sector and sector.strip()) or div_yield_min is not None
        semaphore = asyncio.Semaphore(10)

        async def scan(item: dict) -> ScreenerItemResponse | None:
            async with semaphore:
                try:
                    t = item["ticker"]
                    item_market = item.get("market") or market
                    candles = await moex_client.get_history(t, from_date, to_date, market=item_market)
                    if len(candles) < 20:
                        return None
                    indicators = calculate_indicators(candles)
                    risk = calculate_risk_metrics(candles, None)
                    rsi = indicators.get("rsi14")
                    sharpe = float(risk.get("sharpe", 0.0))
                    if rsi_min is not None and (rsi is None or rsi < rsi_min):
                        return None
                    if rsi_max is not None and (rsi is None or rsi > rsi_max):
                        return None
                    if sharpe_min is not None and sharpe < sharpe_min:
                        return None

                    sector_name = item_market
                    div_yield = None
                    if need_passport:
                        try:
                            passport = await moex_client.get_security_passport(t, market=item_market)
                            sector_name = passport.get("group") or passport.get("instrument_type") or sector_name
                            if sector and sector_name and sector.lower() not in str(sector_name).lower():
                                return None
                            if div_yield_min is not None:
                                fund = await moex_client.get_fundamental(t, market=item_market)
                                div_yield = fund.get("dividend_yield_pct")
                                if div_yield is None or div_yield < div_yield_min:
                                    return None
                        except Exception:
                            return None
                    elif div_yield_min is not None:
                        return None

                    return ScreenerItemResponse(
                        ticker=t,
                        name=item.get("name", t),
                        market=item_market,
                        sector=sector_name,
                        return_pct=float(indicators.get("return_pct", 0.0)),
                        volatility=float(indicators.get("volatility", 0.0)),
                        sharpe=sharpe,
                        rsi14=rsi,
                        dividend_yield_pct=div_yield,
                    )
                except Exception:
                    return None

        results = await asyncio.gather(*(scan(item) for item in universe))
        filtered = [r for r in results if r is not None]
        filtered.sort(key=lambda x: x.sharpe, reverse=True)
        return filtered[:limit]

    @router.get("/api/watchlist/alerts", response_model=list[WatchlistAlertResponse])
    async def list_alerts(
        session: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ) -> list[WatchlistAlertResponse]:
        items = await get_watchlist_alerts(session, current_user.id)
        return [
            WatchlistAlertResponse(
                id=i.id,
                ticker=i.ticker,
                alert_type=i.alert_type,
                threshold_value=i.threshold_value,
            )
            for i in items
        ]

    @router.put("/api/watchlist/alerts", response_model=list[WatchlistAlertResponse])
    async def upsert_alert(
        payload: WatchlistAlertRequest,
        session: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ) -> list[WatchlistAlertResponse]:
        await upsert_watchlist_alert(
            session,
            current_user.id,
            payload.ticker,
            payload.alert_type,
            payload.threshold_value,
        )
        items = await get_watchlist_alerts(session, current_user.id)
        return [
            WatchlistAlertResponse(
                id=i.id, ticker=i.ticker, alert_type=i.alert_type, threshold_value=i.threshold_value
            )
            for i in items
        ]

    @router.delete("/api/watchlist/alerts/{alert_id}", response_model=list[WatchlistAlertResponse])
    async def delete_alert(
        alert_id: int,
        session: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ) -> list[WatchlistAlertResponse]:
        await remove_watchlist_alert(session, current_user.id, alert_id)
        items = await get_watchlist_alerts(session, current_user.id)
        return [
            WatchlistAlertResponse(
                id=i.id, ticker=i.ticker, alert_type=i.alert_type, threshold_value=i.threshold_value
            )
            for i in items
        ]

    @router.get("/api/watchlist/alerts/triggered", response_model=list[TriggeredAlertResponse])
    async def triggered_alerts(
        session: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ) -> list[TriggeredAlertResponse]:
        alerts = await get_watchlist_alerts(session, current_user.id)
        if not alerts:
            return []

        triggered: list[TriggeredAlertResponse] = []
        for alert in alerts:
            try:
                quote = await moex_client.get_quote(alert.ticker)
            except Exception:
                continue
            price = float(quote.get("current_price", 0))
            change_pct = float(quote.get("change_percent", 0))
            hit = False
            msg = ""
            if alert.alert_type == "price_above" and price >= alert.threshold_value:
                hit = True
                msg = f"{alert.ticker}: цена {price:.2f} ≥ порога {alert.threshold_value:.2f}"
            elif alert.alert_type == "price_below" and price <= alert.threshold_value:
                hit = True
                msg = f"{alert.ticker}: цена {price:.2f} ≤ порога {alert.threshold_value:.2f}"
            elif alert.alert_type == "change_pct_above" and change_pct >= alert.threshold_value:
                hit = True
                msg = f"{alert.ticker}: изменение {change_pct:+.2f}% ≥ порога {alert.threshold_value:.2f}%"
            if hit:
                triggered.append(
                    TriggeredAlertResponse(
                        alert_id=alert.id,
                        ticker=alert.ticker,
                        alert_type=alert.alert_type,
                        threshold_value=alert.threshold_value,
                        current_price=price,
                        change_percent=change_pct,
                        message=msg,
                    )
                )
        return triggered

    app.include_router(router)
