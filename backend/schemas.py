from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class QuoteResponse(BaseModel):
    """Схема ответа с текущей котировкой инструмента."""

    ticker: str = Field(..., description="Тикер инструмента")
    name: str = Field(..., description="Название инструмента")
    board: str | None = Field(None, description="Выбранная торговая доска")
    available_boards: list[str] = Field(default_factory=list, description="Доступные доски для тикера")
    current_price: float = Field(..., description="Текущая цена")
    change: float = Field(..., description="Изменение цены за день")
    change_percent: float = Field(..., description="Изменение цены в процентах")
    volume: float = Field(..., description="Объем торгов")
    turnover: float = Field(0.0, description="Денежный оборот")
    num_trades: int = Field(0, description="Количество сделок")
    vwap: float = Field(0.0, description="Средневзвешенная цена")
    capitalization: float = Field(0.0, description="Капитализация инструмента")
    trading_status: str | None = Field(None, description="Торговый статус инструмента на выбранной доске")
    source_field: str = Field("UNKNOWN", description="Поле MOEX, из которого взята текущая цена")
    last_update: datetime = Field(..., description="Время последнего обновления")


class HistoryResponse(BaseModel):
    """Схема одной свечи для исторического графика."""

    date: dt_date = Field(..., description="Дата свечи")
    open: float = Field(..., description="Цена открытия")
    high: float = Field(..., description="Максимальная цена")
    low: float = Field(..., description="Минимальная цена")
    close: float = Field(..., description="Цена закрытия")
    volume: float = Field(..., description="Объем торгов")


class SearchResult(BaseModel):
    """Схема результата поиска по инструментам."""

    ticker: str = Field(..., description="Тикер")
    name: str = Field(..., description="Название инструмента")
    secid: str = Field(..., description="Идентификатор бумаги MOEX")


class RegisterRequest(BaseModel):
    """Схема регистрации пользователя."""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """Схема входа пользователя."""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    """Схема ответа с JWT токеном."""

    access_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    """Схема профиля пользователя."""

    id: int
    email: EmailStr
    created_at: datetime


class PopularInstrumentResponse(BaseModel):
    """Схема популярного инструмента по рынку."""

    ticker: str
    name: str
    market: str
    board: str | None = None
    last_price: float = 0.0
    change_percent: float = 0.0
    volume: float = 0.0


class OrderBookLevel(BaseModel):
    """Один уровень стакана."""

    price: float
    volume: float


class OrderBookResponse(BaseModel):
    """Схема ответа по стакану."""

    ticker: str
    board: str | None = None
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    last_update: datetime


class AnalysisResponse(BaseModel):
    """Схема аналитики по инструменту."""

    ticker: str
    market: str = "shares"
    from_date: dt_date
    to_date: dt_date
    ema20: float | None = None
    ema50: float | None = None
    rsi14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    volatility: float = 0.0
    max_drawdown: float = 0.0
    return_pct: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    beta: float | None = None
    correlation_to_index: float | None = None
    signals: list[str] = Field(default_factory=list)


class BacktestPoint(BaseModel):
    date: dt_date
    equity: float


class BacktestResponse(BaseModel):
    ticker: str
    from_date: dt_date
    to_date: dt_date
    fast_period: int
    slow_period: int
    strategy_return_pct: float
    buy_hold_return_pct: float
    trades: int
    win_rate: float
    equity_curve: list[BacktestPoint] = Field(default_factory=list)


class RankingResponse(BaseModel):
    ticker: str
    name: str
    market: str
    board: str | None = None
    return_pct: float
    volatility: float
    sharpe: float = 0.0
    score: float


class SecurityPassportResponse(BaseModel):
    ticker: str
    name: str
    short_name: str
    market: str
    instrument_type: str
    isin: str | None = None
    reg_number: str | None = None
    currency: str = "RUB"
    lot_size: int = 1
    face_value: float | None = None
    coupon_percent: float | None = None
    coupon_value: float | None = None
    maturity_date: str | None = None
    issuer: str | None = None
    group: str | None = None
    board: str | None = None
    current_price: float = 0.0
    change_percent: float = 0.0
    capitalization: float = 0.0
    volume: float = 0.0
    turnover: float = 0.0


class DividendItem(BaseModel):
    registry_date: str
    value: float
    currency: str = "RUB"


class FundamentalResponse(BaseModel):
    ticker: str
    market: str
    dividend_yield_pct: float | None = None
    dividends_12m: float = 0.0
    yield_to_maturity: float | None = None
    accrued_interest: float | None = None
    coupon_percent: float | None = None
    face_value: float | None = None
    maturity_date: str | None = None
    capitalization: float = 0.0
    pe_ratio: float | None = None
    dividends: list[DividendItem] = Field(default_factory=list)


class ForecastPoint(BaseModel):
    date: dt_date
    price: float
    lower: float
    upper: float


class ForecastMetrics(BaseModel):
    mae: float | None = None
    mape: float | None = None
    samples: int = 0


class ForecastResponse(BaseModel):
    ticker: str
    market: str
    method: str
    horizon: int
    last_price: float
    trend: str
    expected_return_pct: float
    points: list[ForecastPoint] = Field(default_factory=list)
    metrics: ForecastMetrics
    disclaimer: str


class SecurityReportResponse(BaseModel):
    ticker: str
    market: str
    instrument_type: str
    from_date: dt_date
    to_date: dt_date
    passport: SecurityPassportResponse
    fundamental: FundamentalResponse
    technical: AnalysisResponse
    forecast: ForecastResponse | None = None
    summary: dict


class PortfolioPositionRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    market: str = Field(default="shares", pattern="^(shares|futures|bonds|etf)$")
    weight_pct: float = Field(..., ge=0.0, le=100.0)


class PortfolioPositionResponse(BaseModel):
    ticker: str
    market: str
    weight_pct: float
    return_pct: float | None = None
    volatility: float | None = None
    beta: float | None = None
    sharpe: float | None = None


class PortfolioAnalysisResponse(BaseModel):
    positions: list[PortfolioPositionResponse]
    metrics: dict


class CompareTickerMetrics(BaseModel):
    ticker: str
    return_pct: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0
    rsi14: float | None = None
    ema20: float | None = None
    ema50: float | None = None
    signals: list[str] = Field(default_factory=list)


class CompareCurvePoint(BaseModel):
    date: dt_date
    left_norm: float
    right_norm: float
    left_price: float
    right_price: float


class CompareTickersResponse(BaseModel):
    from_date: dt_date
    to_date: dt_date
    left: CompareTickerMetrics
    right: CompareTickerMetrics
    leader_by_return: str
    leader_by_risk_adjusted: str
    normalized_curve: list[CompareCurvePoint] = Field(default_factory=list)


class ChartOverlayPoint(BaseModel):
    date: dt_date
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None


class ChartOverlaysResponse(BaseModel):
    ticker: str
    bollinger: list[ChartOverlayPoint]
    support: float | None = None
    resistance: float | None = None


class ReturnsDistributionResponse(BaseModel):
    ticker: str
    bins: list[dict]
    counts: list[int]
    mean: float
    std: float


class WalkForwardPeriod(BaseModel):
    from_date: dt_date
    to_date: dt_date
    strategy_return_pct: float
    buy_hold_return_pct: float
    trades: int
    win_rate: float


class WalkForwardResponse(BaseModel):
    ticker: str
    fast_period: int
    slow_period: int
    window_days: int
    step_days: int
    periods: list[WalkForwardPeriod]
    avg_strategy_return_pct: float
    avg_buy_hold_return_pct: float


class ForecastModelScore(BaseModel):
    method: str
    mae: float | None = None
    mape: float | None = None
    samples: int = 0


class ForecastCompareResponse(BaseModel):
    ticker: str
    best_method: str
    best_mape: float | None = None
    models: list[ForecastModelScore]
    forecast: ForecastResponse


class ScreenerItemResponse(BaseModel):
    ticker: str
    name: str
    market: str
    sector: str | None = None
    return_pct: float
    volatility: float
    sharpe: float
    rsi14: float | None = None
    dividend_yield_pct: float | None = None


class PortfolioVarMetrics(BaseModel):
    var_daily_pct: float
    var_weekly_pct: float
    confidence: float = 0.95


class WatchlistAlertRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    alert_type: str = Field(..., pattern="^(price_above|price_below|change_pct_above)$")
    threshold_value: float


class WatchlistAlertResponse(BaseModel):
    id: int
    ticker: str
    alert_type: str
    threshold_value: float


class TriggeredAlertResponse(BaseModel):
    alert_id: int
    ticker: str
    alert_type: str
    threshold_value: float
    current_price: float
    change_percent: float
    message: str


# Пример использования:
# quote = QuoteResponse(
#     ticker="SBER",
#     name="Сбербанк",
#     current_price=300.12,
#     change=1.2,
#     change_percent=0.4,
#     volume=1234567,
#     last_update=datetime.utcnow(),
# )
