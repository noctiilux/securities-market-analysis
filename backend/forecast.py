from __future__ import annotations

from datetime import date, timedelta
from math import sqrt
from statistics import mean

from analytics import _ema, _stddev, calculate_indicators, daily_returns

DISCLAIMER = (
    "Прогноз основан только на исторических ценах и не учитывает новости, "
    "отчётность и макроэкономику. Не является инвестиционной рекомендацией."
)


def next_trading_days(start: date, count: int) -> list[date]:
    """Следующие торговые дни (без субботы и воскресенья)."""
    result: list[date] = []
    current = start
    while len(result) < count:
        current += timedelta(days=1)
        if current.weekday() < 5:
            result.append(current)
    return result


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return (values[-1] - values[0]) / (len(values) - 1)


def build_forecast(
    candles: list[dict],
    horizon: int = 10,
    method: str = "ema",
    ema_period: int = 20,
    confidence_z: float = 1.28,
) -> dict:
    """Строит краткосрочный прогноз цены с доверительным коридором."""
    if len(candles) < ema_period + 5:
        return {
            "points": [],
            "last_price": 0.0,
            "trend": "flat",
            "expected_return_pct": 0.0,
            "method": method,
            "horizon": horizon,
        }

    closes = [float(c["close"]) for c in candles]
    last_price = closes[-1]
    last_date = candles[-1]["date"]
    if isinstance(last_date, str):
        last_date = date.fromisoformat(last_date)

    indicators = calculate_indicators(candles)
    annual_vol = float(indicators.get("volatility", 0.0) or 0.0)
    daily_vol = annual_vol / sqrt(252) if annual_vol > 0 else _stddev(daily_returns(candles))

    if method == "linear":
        tail = closes[-min(20, len(closes)) :]
        slope = _linear_slope(tail)
        base_price = last_price
    elif method == "sma":
        from analytics import _sma

        sma_series = _sma(closes, ema_period)
        valid = [v for v in sma_series if v is not None]
        if len(valid) < 3:
            slope = 0.0
            base_price = last_price
        else:
            tail = valid[-5:]
            slope = _linear_slope(tail)
            base_price = valid[-1]
        method = "sma"
    else:
        ema_series = _ema(closes, ema_period)
        valid = [v for v in ema_series if v is not None]
        if len(valid) < 3:
            slope = 0.0
            base_price = last_price
        else:
            tail = valid[-5:]
            slope = _linear_slope(tail)
            base_price = valid[-1]
        method = "ema"

    forecast_dates = next_trading_days(last_date, horizon)
    points: list[dict] = []
    for i, forecast_date in enumerate(forecast_dates, start=1):
        projected = base_price + slope * i
        band = last_price * daily_vol * sqrt(i) * confidence_z
        lower = max(0.01, projected - band)
        upper = projected + band
        points.append(
            {
                "date": forecast_date,
                "price": round(projected, 4),
                "lower": round(lower, 4),
                "upper": round(upper, 4),
            }
        )

    final_price = points[-1]["price"] if points else last_price
    expected_return_pct = ((final_price / last_price) - 1.0) * 100.0 if last_price else 0.0
    if expected_return_pct > 1.0:
        trend = "up"
    elif expected_return_pct < -1.0:
        trend = "down"
    else:
        trend = "flat"

    return {
        "points": points,
        "last_price": round(last_price, 4),
        "trend": trend,
        "expected_return_pct": round(expected_return_pct, 4),
        "method": method,
        "horizon": horizon,
        "daily_volatility": round(daily_vol, 6),
    }


def evaluate_forecast(
    candles: list[dict],
    horizon: int = 5,
    holdout_days: int = 15,
    method: str = "ema",
) -> dict:
    """Оценка качества: обучение без последних holdout_days, сравнение с фактом."""
    if len(candles) < holdout_days + 30:
        return {"mae": None, "mape": None, "samples": 0}

    train = candles[:-holdout_days]
    actual = candles[-holdout_days:]
    eval_horizon = min(horizon, holdout_days, len(actual))

    predicted = build_forecast(train, horizon=eval_horizon, method=method)
    pred_points = predicted.get("points", [])
    if not pred_points:
        return {"mae": None, "mape": None, "samples": 0}

    errors: list[float] = []
    pct_errors: list[float] = []
    for i in range(min(len(pred_points), len(actual))):
        actual_price = float(actual[i]["close"])
        pred_price = float(pred_points[i]["price"])
        errors.append(abs(actual_price - pred_price))
        if actual_price > 0:
            pct_errors.append(abs(actual_price - pred_price) / actual_price * 100.0)

    if not errors:
        return {"mae": None, "mape": None, "samples": 0}

    return {
        "mae": round(mean(errors), 4),
        "mape": round(mean(pct_errors), 4),
        "samples": len(errors),
    }


def compare_forecast_models(
    candles: list[dict],
    horizon: int = 10,
    holdout_days: int = 15,
) -> dict:
    """Сравнивает EMA, linear, SMA — выбирает лучшую по MAPE."""
    methods = ["ema", "linear", "sma"]
    ranked: list[dict] = []
    for method in methods:
        metrics = evaluate_forecast(candles, horizon=horizon, holdout_days=holdout_days, method=method)
        mape = metrics.get("mape")
        ranked.append(
            {
                "method": method,
                "mae": metrics.get("mae"),
                "mape": mape,
                "samples": metrics.get("samples", 0),
            }
        )

    with_mape = [r for r in ranked if r.get("mape") is not None]
    best = min(with_mape, key=lambda x: x["mape"]) if with_mape else ranked[0]
    best_forecast = build_forecast(candles, horizon=horizon, method=best["method"])
    return {
        "models": ranked,
        "best_method": best["method"],
        "best_mape": best.get("mape"),
        "forecast": best_forecast,
    }
