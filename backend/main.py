from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from auth import create_access_token, get_current_user, hash_password, verify_password
from analytics import (
    build_report_summary,
    calculate_indicators,
    calculate_risk_metrics,
    daily_returns,
    generate_signals,
    portfolio_metrics,
    portfolio_var,
    run_ema_backtest,
)
from forecast import DISCLAIMER, build_forecast, evaluate_forecast
from database import (
    add_to_watchlist,
    create_user,
    get_cached_history,
    get_db_session,
    get_portfolio,
    get_user_by_email,
    get_watchlist,
    init_db,
    remove_from_watchlist,
    remove_portfolio_position,
    save_price_history,
    upsert_portfolio_position,
)
from models import User
from moex_client import MoexClient, MoexClientError, TickerNotFoundError
from schemas import (
    AnalysisResponse,
    BacktestPoint,
    BacktestResponse,
    CompareTickerMetrics,
    CompareCurvePoint,
    CompareTickersResponse,
    DividendItem,
    ForecastMetrics,
    ForecastPoint,
    ForecastResponse,
    FundamentalResponse,
    HistoryResponse,
    LoginRequest,
    OrderBookResponse,
    PopularInstrumentResponse,
    PortfolioAnalysisResponse,
    PortfolioPositionRequest,
    PortfolioPositionResponse,
    QuoteResponse,
    RankingResponse,
    RegisterRequest,
    SearchResult,
    SecurityPassportResponse,
    SecurityReportResponse,
    TokenResponse,
    UserProfileResponse,
)

app = FastAPI(
    title="Market Analysis API",
    description="API для анализа динамики рынка ценных бумаг (MOEX).",
    version="1.0.0",
)

# Разрешаем запросы от фронтенда Vue (Vite по умолчанию на 5173 порту).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

moex_client = MoexClient()


async def _resolve_market(ticker: str, market: str | None) -> str:
    if market:
        return market.lower().strip()
    return await moex_client.detect_market(ticker)


async def _load_analysis_bundle(
    ticker: str,
    from_date: date,
    to_date: date,
    market: str | None = None,
) -> tuple[str, list[dict], dict, dict, list[str]]:
    resolved_market = await _resolve_market(ticker, market)
    candles = await moex_client.get_history(ticker, from_date, to_date, market=resolved_market)
    benchmark = await moex_client.get_benchmark_history(from_date, to_date)
    indicators = calculate_indicators(candles)
    risk = calculate_risk_metrics(candles, benchmark)
    signals = generate_signals(indicators, market=resolved_market)
    return resolved_market, candles, indicators, risk, signals


def _analysis_response(
    ticker: str,
    market: str,
    from_date: date,
    to_date: date,
    indicators: dict,
    risk: dict,
    signals: list[str],
) -> AnalysisResponse:
    return AnalysisResponse(
        ticker=ticker.upper(),
        market=market,
        from_date=from_date,
        to_date=to_date,
        signals=signals,
        sharpe=float(risk.get("sharpe", 0.0)),
        sortino=float(risk.get("sortino", 0.0)),
        beta=risk.get("beta"),
        correlation_to_index=risk.get("correlation_to_index"),
        **indicators,
    )


@app.on_event("startup")
async def on_startup() -> None:
    """Инициализация БД при запуске приложения."""
    await init_db()


@app.get("/")
async def root() -> dict:
    """Проверка доступности API."""
    return {"status": "ok", "message": "FastAPI backend is running", "title": "Анализатор рынка"}


@app.post("/api/auth/register", response_model=UserProfileResponse, status_code=201)
async def register_user(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    """Регистрация нового пользователя."""
    existing = await get_user_by_email(session, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

    user = await create_user(session, email=payload.email, password_hash=hash_password(payload.password))
    return UserProfileResponse(id=user.id, email=user.email, created_at=user.created_at)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login_user(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Вход пользователя и выдача JWT."""
    user = await get_user_by_email(session, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@app.get("/api/auth/me", response_model=UserProfileResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    """Текущий авторизованный пользователь."""
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )


@app.get("/api/quote/{ticker}", response_model=QuoteResponse)
async def get_quote(
    ticker: str,
    board: str | None = Query(None, description="Торговая доска (BOARDID)"),
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
) -> QuoteResponse:
    """Текущая котировка инструмента."""
    try:
        quote = await moex_client.get_quote(ticker, board=board, market=market)
        return QuoteResponse(**quote)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _history_cache_is_usable(
    cached: list,
    from_date: date,
    to_date: date,
) -> bool:
    """Кэш годится только если покрывает период и не устарел."""
    if not cached:
        return False

    span_days = (to_date - from_date).days + 1
    min_bars = max(1, int(span_days * 5 / 7) - 2)
    if len(cached) < min_bars:
        return False

    latest = cached[-1].date
    freshness_cutoff = min(to_date, date.today()) - timedelta(days=4)
    if latest < freshness_cutoff:
        return False

    return True


@app.get("/api/history/{ticker}", response_model=List[HistoryResponse])
async def get_history(
    ticker: str,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
    session: AsyncSession = Depends(get_db_session),
) -> List[HistoryResponse]:
    """Исторические свечи по инструменту для построения графика."""
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Параметр 'from' не может быть позже 'to'")

    cached = await get_cached_history(session, ticker, from_date, to_date)
    if _history_cache_is_usable(cached, from_date, to_date):
        return [
            HistoryResponse(
                date=item.date,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                volume=item.volume,
            )
            for item in cached
        ]

    try:
        resolved_market = await _resolve_market(ticker, market)
        history = await moex_client.get_history(ticker, from_date, to_date, market=resolved_market)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if history:
        await save_price_history(session, ticker, history)

    return [HistoryResponse(**item) for item in history]


@app.get("/api/security/{ticker}", response_model=SecurityPassportResponse)
async def get_security_passport(
    ticker: str,
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
) -> SecurityPassportResponse:
    """Паспорт ценной бумаги."""
    try:
        data = await moex_client.get_security_passport(ticker, market=market)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SecurityPassportResponse(**data)


@app.get("/api/fundamental/{ticker}", response_model=FundamentalResponse)
async def get_fundamental(
    ticker: str,
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf)$"),
) -> FundamentalResponse:
    """Фундаментальные показатели бумаги."""
    try:
        data = await moex_client.get_fundamental(ticker, market=market)
        dividends = await moex_client.get_dividends(ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return FundamentalResponse(
        **data,
        dividends=[DividendItem(**item) for item in dividends[:20]],
    )


@app.get("/api/report/{ticker}", response_model=SecurityReportResponse)
async def get_security_report(
    ticker: str,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf)$"),
) -> SecurityReportResponse:
    """Комплексный отчёт по ценной бумаге."""
    return await _build_security_report(ticker, from_date, to_date, market)


@app.get("/api/analysis/{ticker}", response_model=AnalysisResponse)
async def get_analysis(
    ticker: str,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
) -> AnalysisResponse:
    """Рассчитывает индикаторы и сигналы по выбранному инструменту."""
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Параметр 'from' не может быть позже 'to'")
    try:
        resolved_market, candles, indicators, risk, signals = await _load_analysis_bundle(
            ticker, from_date, to_date, market=market
        )
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if len(candles) < 20:
        raise HTTPException(status_code=400, detail="Недостаточно исторических данных для анализа")

    return _analysis_response(ticker, resolved_market, from_date, to_date, indicators, risk, signals)


def _forecast_response(
    ticker: str,
    market: str,
    candles: list[dict],
    horizon: int,
    method: str,
    with_metrics: bool,
) -> ForecastResponse:
    raw = build_forecast(candles, horizon=horizon, method=method)
    metrics_raw = evaluate_forecast(candles, horizon=min(horizon, 10), method=method) if with_metrics else {}
    return ForecastResponse(
        ticker=ticker.upper(),
        market=market,
        method=raw.get("method", method),
        horizon=horizon,
        last_price=float(raw.get("last_price", 0.0)),
        trend=str(raw.get("trend", "flat")),
        expected_return_pct=float(raw.get("expected_return_pct", 0.0)),
        points=[ForecastPoint(**p) for p in raw.get("points", [])],
        metrics=ForecastMetrics(**metrics_raw),
        disclaimer=DISCLAIMER,
    )


@app.get("/api/forecast/{ticker}", response_model=ForecastResponse)
async def get_forecast(
    ticker: str,
    horizon: int = Query(10, ge=5, le=30),
    method: str = Query("ema", pattern="^(ema|linear|sma)$"),
    lookback_days: int = Query(120, ge=60, le=365),
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
    evaluate: bool = Query(True, description="Считать MAE/MAPE на hold-out"),
) -> ForecastResponse:
    """Краткосрочный прогноз цены с доверительным коридором."""
    to_date = date.today()
    from_date = date.fromordinal(to_date.toordinal() - lookback_days)
    try:
        resolved_market = await _resolve_market(ticker, market)
        candles = await moex_client.get_history(ticker, from_date, to_date, market=resolved_market)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if len(candles) < 30:
        raise HTTPException(status_code=400, detail="Недостаточно истории для прогноза (минимум ~30 свечей)")

    return _forecast_response(ticker, resolved_market, candles, horizon, method, evaluate)


@app.get("/api/backtest/{ticker}", response_model=BacktestResponse)
async def get_backtest(
    ticker: str,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    fast: int = Query(20, ge=5, le=50),
    slow: int = Query(50, ge=10, le=200),
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
) -> BacktestResponse:
    """Запускает простой бэктест стратегии EMA crossover."""
    if fast >= slow:
        raise HTTPException(status_code=400, detail="Параметр fast должен быть меньше slow")
    try:
        resolved_market = await _resolve_market(ticker, market)
        candles = await moex_client.get_history(ticker, from_date, to_date, market=resolved_market)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result = run_ema_backtest(candles, fast=fast, slow=slow)
    return BacktestResponse(
        ticker=ticker.upper(),
        from_date=from_date,
        to_date=to_date,
        fast_period=fast,
        slow_period=slow,
        strategy_return_pct=result["strategy_return_pct"],
        buy_hold_return_pct=result["buy_hold_return_pct"],
        trades=result["trades"],
        win_rate=result["win_rate"],
        equity_curve=[
            BacktestPoint(date=date.fromisoformat(point["date"]), equity=point["equity"])
            for point in result["equity_curve"]
        ],
    )


@app.get("/api/orderbook/{ticker}", response_model=OrderBookResponse)
async def get_orderbook(
    ticker: str,
    board: str | None = Query(None, description="Торговая доска (BOARDID)"),
    depth: int = Query(20, ge=1, le=50),
    market: str | None = Query(None, pattern="^(shares|futures|bonds|etf|index)$"),
) -> OrderBookResponse:
    """Стакан заявок по выбранному тикеру."""
    try:
        data = await moex_client.get_orderbook(ticker=ticker, board=board, depth=depth, market=market)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return OrderBookResponse(**data)


@app.get("/api/search", response_model=List[SearchResult])
async def search_instruments(query: str = Query(..., min_length=1)) -> List[SearchResult]:
    """Поиск инструментов по тикеру или названию."""
    try:
        items = await moex_client.search(query)
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [SearchResult(**item) for item in items]


@app.get("/api/popular", response_model=List[PopularInstrumentResponse])
async def get_popular_instruments(
    market: str = Query("shares", pattern="^(shares|futures|bonds|etf)$"),
) -> List[PopularInstrumentResponse]:
    """Список популярных инструментов по выбранной категории рынка MOEX."""
    try:
        items = await moex_client.get_popular(market)
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [PopularInstrumentResponse(**item) for item in items]


@app.get("/api/securities", response_model=List[PopularInstrumentResponse])
async def get_securities_list(
    market: str = Query("shares", pattern="^(shares|futures|bonds|etf)$"),
    limit: int = Query(1500, ge=50, le=5000),
    offset: int = Query(0, ge=0, le=50000),
) -> List[PopularInstrumentResponse]:
    """Расширенный список инструментов MOEX по категории рынка."""
    try:
        items = await moex_client.get_securities(market=market, limit=limit, offset=offset)
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [PopularInstrumentResponse(**item) for item in items]


@app.get("/api/ranking", response_model=List[RankingResponse])
async def get_ranking(
    market: str = Query("shares", pattern="^(shares|futures|bonds|etf)$"),
    lookback_days: int = Query(60, ge=20, le=365),
    universe_size: int = Query(40, ge=10, le=120),
) -> List[RankingResponse]:
    """Ранжирует бумаги по риск-доходности на заданном горизонте."""
    to_date = date.today()
    from_date = date.fromordinal(to_date.toordinal() - lookback_days)

    try:
        universe = await moex_client.get_securities(market=market, limit=universe_size, offset=0)
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    semaphore = asyncio.Semaphore(8)

    benchmark = await moex_client.get_benchmark_history(from_date, to_date)

    async def analyze_item(item: dict) -> RankingResponse | None:
        async with semaphore:
            try:
                item_market = item.get("market") or market
                candles = await moex_client.get_history(
                    item["ticker"], from_date, to_date, market=item_market
                )
                if len(candles) < 20:
                    return None
                indicators = calculate_indicators(candles)
                risk = calculate_risk_metrics(candles, benchmark)
                ret = float(indicators.get("return_pct", 0.0))
                vol = float(indicators.get("volatility", 0.0))
                sharpe = float(risk.get("sharpe", 0.0))
                score = sharpe if sharpe else ret / (vol * 100.0 + 1e-6)
                return RankingResponse(
                    ticker=item["ticker"],
                    name=item["name"],
                    market=item["market"],
                    board=item.get("board"),
                    return_pct=round(ret, 4),
                    volatility=round(vol, 6),
                    sharpe=round(sharpe, 4),
                    score=round(score, 6),
                )
            except Exception:
                return None

    ranked = await asyncio.gather(*(analyze_item(item) for item in universe))
    filtered = [item for item in ranked if item is not None]
    filtered.sort(key=lambda x: x.score, reverse=True)
    return filtered[:20]


@app.get("/api/compare", response_model=CompareTickersResponse)
async def compare_tickers(
    left: str = Query(..., min_length=1),
    right: str = Query(..., min_length=1),
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
) -> CompareTickersResponse:
    """Сравнивает два тикера по доходности, риску и индикаторам."""
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Параметр 'from' не может быть позже 'to'")

    try:
        left_candles, right_candles = await asyncio.gather(
            moex_client.get_history(left, from_date, to_date),
            moex_client.get_history(right, from_date, to_date),
        )
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if len(left_candles) < 20 or len(right_candles) < 20:
        raise HTTPException(status_code=400, detail="Недостаточно данных для сравнения")

    left_ind = calculate_indicators(left_candles)
    right_ind = calculate_indicators(right_candles)
    left_sig = generate_signals(left_ind)
    right_sig = generate_signals(right_ind)

    left_metrics = CompareTickerMetrics(
        ticker=left.upper(),
        return_pct=float(left_ind.get("return_pct", 0.0)),
        volatility=float(left_ind.get("volatility", 0.0)),
        max_drawdown=float(left_ind.get("max_drawdown", 0.0)),
        rsi14=left_ind.get("rsi14"),
        ema20=left_ind.get("ema20"),
        ema50=left_ind.get("ema50"),
        signals=left_sig,
    )
    right_metrics = CompareTickerMetrics(
        ticker=right.upper(),
        return_pct=float(right_ind.get("return_pct", 0.0)),
        volatility=float(right_ind.get("volatility", 0.0)),
        max_drawdown=float(right_ind.get("max_drawdown", 0.0)),
        rsi14=right_ind.get("rsi14"),
        ema20=right_ind.get("ema20"),
        ema50=right_ind.get("ema50"),
        signals=right_sig,
    )

    leader_by_return = left_metrics.ticker if left_metrics.return_pct >= right_metrics.return_pct else right_metrics.ticker
    left_risk_adj = left_metrics.return_pct / (left_metrics.volatility * 100.0 + 1e-6)
    right_risk_adj = right_metrics.return_pct / (right_metrics.volatility * 100.0 + 1e-6)
    leader_by_risk_adjusted = left_metrics.ticker if left_risk_adj >= right_risk_adj else right_metrics.ticker

    # Нормализованные кривые доходности (база = 100) для визуального сравнения.
    left_map = {str(item["date"]): float(item["close"]) for item in left_candles}
    right_map = {str(item["date"]): float(item["close"]) for item in right_candles}
    common_dates = sorted(set(left_map).intersection(right_map))
    normalized_curve: list[CompareCurvePoint] = []
    if common_dates:
        left_base = left_map[common_dates[0]] or 1.0
        right_base = right_map[common_dates[0]] or 1.0
        for d in common_dates:
            normalized_curve.append(
                CompareCurvePoint(
                    date=date.fromisoformat(d),
                    left_norm=round((left_map[d] / left_base) * 100.0, 4),
                    right_norm=round((right_map[d] / right_base) * 100.0, 4),
                    left_price=round(left_map[d], 4),
                    right_price=round(right_map[d], 4),
                )
            )

    return CompareTickersResponse(
        from_date=from_date,
        to_date=to_date,
        left=left_metrics,
        right=right_metrics,
        leader_by_return=leader_by_return,
        leader_by_risk_adjusted=leader_by_risk_adjusted,
        normalized_curve=normalized_curve,
    )


@app.get("/api/watchlist", response_model=List[str])
async def get_user_watchlist(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Получение списка избранных тикеров пользователя."""
    items = await get_watchlist(session, user_id=current_user.id)
    return [item.ticker for item in items]


@app.post("/api/watchlist/{ticker}", response_model=List[str])
async def add_watchlist_ticker(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Добавление тикера в избранное."""
    await add_to_watchlist(session, current_user.id, ticker)
    items = await get_watchlist(session, user_id=current_user.id)
    return [item.ticker for item in items]


@app.get("/api/portfolio", response_model=PortfolioAnalysisResponse)
async def get_user_portfolio_analysis(
    lookback_days: int = Query(120, ge=20, le=365),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioAnalysisResponse:
    """Анализ портфеля пользователя с весами позиций."""
    to_date = date.today()
    from_date = date.fromordinal(to_date.toordinal() - lookback_days)
    positions_db = await get_portfolio(session, user_id=current_user.id)
    benchmark = await moex_client.get_benchmark_history(from_date, to_date)

    analyzed: list[PortfolioPositionResponse] = []
    metrics_input: list[dict] = []

    for pos in positions_db:
        try:
            candles = await moex_client.get_history(pos.ticker, from_date, to_date, market=pos.market)
            if len(candles) < 10:
                analyzed.append(
                    PortfolioPositionResponse(
                        ticker=pos.ticker,
                        market=pos.market,
                        weight_pct=pos.weight_pct,
                    )
                )
                continue
            indicators = calculate_indicators(candles)
            risk = calculate_risk_metrics(candles, benchmark)
            analyzed.append(
                PortfolioPositionResponse(
                    ticker=pos.ticker,
                    market=pos.market,
                    weight_pct=pos.weight_pct,
                    return_pct=float(indicators.get("return_pct", 0.0)),
                    volatility=float(indicators.get("volatility", 0.0)),
                    beta=risk.get("beta"),
                    sharpe=float(risk.get("sharpe", 0.0)),
                )
            )
            metrics_input.append(
                {
                    "ticker": pos.ticker,
                    "weight_pct": pos.weight_pct,
                    "return_pct": float(indicators.get("return_pct", 0.0)),
                    "volatility": float(indicators.get("volatility", 0.0)),
                    "beta": risk.get("beta"),
                    "daily_returns": daily_returns(candles),
                }
            )
        except Exception:
            analyzed.append(
                PortfolioPositionResponse(
                    ticker=pos.ticker,
                    market=pos.market,
                    weight_pct=pos.weight_pct,
                )
            )

    metrics = portfolio_metrics(metrics_input)
    metrics["var"] = portfolio_var(metrics_input)
    return PortfolioAnalysisResponse(
        positions=analyzed,
        metrics=metrics,
    )


@app.put("/api/portfolio", response_model=List[PortfolioPositionResponse])
async def upsert_portfolio_position_endpoint(
    payload: PortfolioPositionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> List[PortfolioPositionResponse]:
    """Добавление или обновление позиции в портфеле."""
    await upsert_portfolio_position(
        session,
        current_user.id,
        payload.ticker,
        payload.market,
        payload.weight_pct,
    )
    items = await get_portfolio(session, user_id=current_user.id)
    return [
        PortfolioPositionResponse(ticker=i.ticker, market=i.market, weight_pct=i.weight_pct)
        for i in items
    ]


@app.delete("/api/portfolio/{ticker}", response_model=List[PortfolioPositionResponse])
async def delete_portfolio_position_endpoint(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> List[PortfolioPositionResponse]:
    """Удаление позиции из портфеля."""
    removed = await remove_portfolio_position(session, current_user.id, ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Тикер '{ticker.upper()}' не найден в портфеле")
    items = await get_portfolio(session, user_id=current_user.id)
    return [
        PortfolioPositionResponse(ticker=i.ticker, market=i.market, weight_pct=i.weight_pct)
        for i in items
    ]


async def _build_security_report(
    ticker: str,
    from_date: date,
    to_date: date,
    market: str | None,
) -> SecurityReportResponse:
    """Внутренняя сборка отчёта для API и экспорта."""
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Параметр 'from' не может быть позже 'to'")
    try:
        passport_raw = await moex_client.get_security_passport(ticker, market=market)
        fundamental_raw = await moex_client.get_fundamental(ticker, market=passport_raw["market"])
        dividends = await moex_client.get_dividends(ticker)
        resolved_market, candles, indicators, risk, signals = await _load_analysis_bundle(
            ticker, from_date, to_date, market=passport_raw["market"]
        )
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MoexClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not indicators:
        raise HTTPException(status_code=400, detail="Недостаточно исторических данных для отчёта")

    forecast = _forecast_response(ticker, resolved_market, candles, horizon=10, method="ema", with_metrics=True)
    forecast_raw = forecast.model_dump()
    passport = SecurityPassportResponse(**passport_raw)
    fundamental = FundamentalResponse(
        **fundamental_raw,
        dividends=[DividendItem(**item) for item in dividends[:20]],
    )
    technical = _analysis_response(ticker, resolved_market, from_date, to_date, indicators, risk, signals)
    summary = build_report_summary(
        ticker=ticker.upper(),
        market=resolved_market,
        instrument_type=passport.instrument_type,
        indicators=indicators,
        risk=risk,
        fundamental=fundamental_raw,
        signals=signals,
        forecast=forecast_raw,
    )
    return SecurityReportResponse(
        ticker=ticker.upper(),
        market=resolved_market,
        instrument_type=passport.instrument_type,
        from_date=from_date,
        to_date=to_date,
        passport=passport,
        fundamental=fundamental,
        technical=technical,
        forecast=forecast,
        summary=summary,
    )


from routes_extended import register_extended_routes

register_extended_routes(app, moex_client, _resolve_market, _build_security_report)


@app.delete("/api/watchlist/{ticker}", response_model=List[str])
async def delete_watchlist_ticker(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Удаление тикера из избранного."""
    removed = await remove_from_watchlist(session, current_user.id, ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Тикер '{ticker.upper()}' не найден в избранном")

    items = await get_watchlist(session, user_id=current_user.id)
    return [item.ticker for item in items]


# Пример использования:
# 1) Установить зависимости: pip install -r requirements.txt
# 2) Запустить сервер: uvicorn main:app --reload
# 3) Открыть документацию: http://127.0.0.1:8000/docs
