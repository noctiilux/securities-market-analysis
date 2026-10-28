from __future__ import annotations

from math import sqrt
from statistics import mean


def _sma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < period:
            result.append(None)
            continue
        result.append(mean(values[i + 1 - period : i + 1]))
    return result


def _ema(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    k = 2 / (period + 1)
    ema_prev: float | None = None
    for i, value in enumerate(values):
        if i + 1 < period:
            result.append(None)
            continue
        if ema_prev is None:
            ema_prev = mean(values[i + 1 - period : i + 1])
        else:
            ema_prev = value * k + ema_prev * (1 - k)
        result.append(ema_prev)
    return result


def _rsi(closes: list[float], period: int = 14) -> list[float | None]:
    if len(closes) < period + 1:
        return [None] * len(closes)

    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))

    avg_gain = mean(gains[1 : period + 1])
    avg_loss = mean(losses[1 : period + 1])
    rsi_values: list[float | None] = [None] * len(closes)

    for i in range(period, len(closes)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_values[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_values[i] = 100 - (100 / (1 + rs))
    return rsi_values


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return sqrt(sum((v - avg) ** 2 for v in values) / (len(values) - 1))


def _macd(closes: list[float]) -> tuple[list[float | None], list[float | None]]:
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line: list[float | None] = []
    macd_values_for_signal: list[float] = []
    for i in range(len(closes)):
        if ema12[i] is None or ema26[i] is None:
            macd_line.append(None)
        else:
            value = ema12[i] - ema26[i]
            macd_line.append(value)
            macd_values_for_signal.append(value)

    signal = [None] * len(closes)
    if macd_values_for_signal:
        signal_values = _ema(macd_values_for_signal, 9)
        cursor = 0
        for i, m in enumerate(macd_line):
            if m is None:
                continue
            signal[i] = signal_values[cursor]
            cursor += 1
    return macd_line, signal


def daily_returns(candles: list[dict]) -> list[float]:
    closes = [float(c["close"]) for c in candles]
    if len(closes) < 2:
        return []
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def align_return_series(left_candles: list[dict], right_candles: list[dict]) -> tuple[list[float], list[float]]:
    left_map = {str(c["date"]): float(c["close"]) for c in left_candles}
    right_map = {str(c["date"]): float(c["close"]) for c in right_candles}
    dates = sorted(set(left_map).intersection(right_map))
    if len(dates) < 3:
        return [], []

    left_returns: list[float] = []
    right_returns: list[float] = []
    for i in range(1, len(dates)):
        prev = dates[i - 1]
        cur = dates[i]
        left_prev, left_cur = left_map[prev], left_map[cur]
        right_prev, right_cur = right_map[prev], right_map[cur]
        if left_prev and right_prev:
            left_returns.append(left_cur / left_prev - 1.0)
            right_returns.append(right_cur / right_prev - 1.0)
    return left_returns, right_returns


def sharpe_ratio(daily_rets: list[float], risk_free_annual: float = 0.12) -> float:
    if len(daily_rets) < 5:
        return 0.0
    rf_daily = risk_free_annual / 252.0
    excess = [r - rf_daily for r in daily_rets]
    vol = _stddev(daily_rets) * sqrt(252)
    if vol == 0:
        return 0.0
    return (mean(excess) * 252.0) / vol


def sortino_ratio(daily_rets: list[float], risk_free_annual: float = 0.12) -> float:
    if len(daily_rets) < 5:
        return 0.0
    rf_daily = risk_free_annual / 252.0
    excess = [r - rf_daily for r in daily_rets]
    downside = [min(0.0, r) for r in daily_rets]
    downside_vol = _stddev(downside) * sqrt(252)
    if downside_vol == 0:
        return 0.0
    return (mean(excess) * 252.0) / downside_vol


def beta_coefficient(asset_rets: list[float], market_rets: list[float]) -> float:
    n = min(len(asset_rets), len(market_rets))
    if n < 5:
        return 0.0
    asset = asset_rets[-n:]
    market = market_rets[-n:]
    market_var = _stddev(market) ** 2
    if market_var == 0:
        return 0.0
    asset_mean = mean(asset)
    market_mean = mean(market)
    cov = sum((a - asset_mean) * (m - market_mean) for a, m in zip(asset, market)) / (n - 1)
    return cov / market_var


def correlation_coefficient(left_rets: list[float], right_rets: list[float]) -> float:
    n = min(len(left_rets), len(right_rets))
    if n < 5:
        return 0.0
    left = left_rets[-n:]
    right = right_rets[-n:]
    left_std = _stddev(left)
    right_std = _stddev(right)
    if left_std == 0 or right_std == 0:
        return 0.0
    left_mean = mean(left)
    right_mean = mean(right)
    cov = sum((l - left_mean) * (r - right_mean) for l, r in zip(left, right)) / (n - 1)
    return cov / (left_std * right_std)


def calculate_indicators(candles: list[dict]) -> dict:
    closes = [float(c["close"]) for c in candles]
    if len(closes) < 2:
        return {}

    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    rsi14 = _rsi(closes, 14)
    macd_line, macd_signal = _macd(closes)

    returns = daily_returns(candles)
    volatility = _stddev(returns) * sqrt(252) if returns else 0.0
    drawdown = 0.0
    peak = closes[0]
    for close in closes:
        peak = max(peak, close)
        if peak:
            drawdown = min(drawdown, close / peak - 1.0)

    latest = len(closes) - 1
    return {
        "ema20": float(ema20[latest]) if ema20[latest] is not None else None,
        "ema50": float(ema50[latest]) if ema50[latest] is not None else None,
        "rsi14": float(rsi14[latest]) if rsi14[latest] is not None else None,
        "macd": float(macd_line[latest]) if macd_line[latest] is not None else None,
        "macd_signal": float(macd_signal[latest]) if macd_signal[latest] is not None else None,
        "volatility": round(volatility, 6),
        "max_drawdown": round(drawdown, 6),
        "return_pct": round((closes[-1] / closes[0] - 1.0) * 100.0, 4),
    }


def calculate_risk_metrics(candles: list[dict], benchmark_candles: list[dict] | None = None) -> dict:
    asset_rets = daily_returns(candles)
    metrics = {
        "sharpe": round(sharpe_ratio(asset_rets), 4),
        "sortino": round(sortino_ratio(asset_rets), 4),
        "beta": None,
        "correlation_to_index": None,
    }
    if benchmark_candles:
        asset_aligned, bench_aligned = align_return_series(candles, benchmark_candles)
        if asset_aligned and bench_aligned:
            metrics["beta"] = round(beta_coefficient(asset_aligned, bench_aligned), 4)
            metrics["correlation_to_index"] = round(correlation_coefficient(asset_aligned, bench_aligned), 4)
    return metrics


def generate_signals(indicators: dict, market: str = "shares") -> list[str]:
    signals: list[str] = []
    if market == "bonds":
        ret = float(indicators.get("return_pct", 0.0))
        vol = float(indicators.get("volatility", 0.0))
        if ret > 0:
            signals.append("Цена облигации растет на выбранном горизонте")
        else:
            signals.append("Цена облигации снижается на выбранном горизонте")
        if vol < 0.1:
            signals.append("Низкая волатильность — умеренный ценовой риск")
        else:
            signals.append("Повышенная волатильность — следить за ставками и кредитным риском")
        return signals

    ema20 = indicators.get("ema20")
    ema50 = indicators.get("ema50")
    rsi14 = indicators.get("rsi14")
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")

    if ema20 is not None and ema50 is not None:
        signals.append("Тренд бычий (EMA20 > EMA50)" if ema20 > ema50 else "Тренд медвежий (EMA20 <= EMA50)")
    if rsi14 is not None:
        if rsi14 < 30:
            signals.append("RSI указывает на перепроданность")
        elif rsi14 > 70:
            signals.append("RSI указывает на перекупленность")
        else:
            signals.append("RSI в нейтральной зоне")
    if macd is not None and macd_signal is not None:
        signals.append("MACD выше сигнальной линии" if macd > macd_signal else "MACD ниже сигнальной линии")
    return signals


def run_ema_backtest(candles: list[dict], fast: int = 20, slow: int = 50) -> dict:
    closes = [float(c["close"]) for c in candles]
    dates = [str(c["date"]) for c in candles]
    if len(closes) < max(fast, slow) + 2:
        return {
            "strategy_return_pct": 0.0,
            "buy_hold_return_pct": 0.0,
            "trades": 0,
            "win_rate": 0.0,
            "equity_curve": [],
        }

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    in_position = False
    entry_price = 0.0
    trades = 0
    wins = 0
    capital = 1.0
    equity_curve: list[dict] = []

    for i in range(1, len(closes)):
        ef_prev, es_prev = ema_fast[i - 1], ema_slow[i - 1]
        ef_cur, es_cur = ema_fast[i], ema_slow[i]
        if None in (ef_prev, es_prev, ef_cur, es_cur):
            equity_curve.append({"date": dates[i], "equity": capital})
            continue

        if not in_position and ef_prev <= es_prev and ef_cur > es_cur:
            in_position = True
            entry_price = closes[i]
            trades += 1
        elif in_position and ef_prev >= es_prev and ef_cur < es_cur:
            in_position = False
            trade_return = closes[i] / entry_price - 1.0
            capital *= 1.0 + trade_return
            if trade_return > 0:
                wins += 1
        equity_curve.append({"date": dates[i], "equity": round(capital, 6)})

    strategy_return = (capital - 1.0) * 100.0
    buy_hold_return = (closes[-1] / closes[0] - 1.0) * 100.0
    win_rate = (wins / trades * 100.0) if trades else 0.0

    return {
        "strategy_return_pct": round(strategy_return, 4),
        "buy_hold_return_pct": round(buy_hold_return, 4),
        "trades": trades,
        "win_rate": round(win_rate, 2),
        "equity_curve": equity_curve,
    }


def build_report_summary(
    ticker: str,
    market: str,
    instrument_type: str,
    indicators: dict,
    risk: dict,
    fundamental: dict | None,
    signals: list[str],
    forecast: dict | None = None,
) -> dict:
    ret = float(indicators.get("return_pct", 0.0))
    vol = float(indicators.get("volatility", 0.0))
    sharpe = float(risk.get("sharpe", 0.0))
    beta = risk.get("beta")

    risk_level = "низкий"
    if vol >= 0.35 or abs(ret) >= 25:
        risk_level = "высокий"
    elif vol >= 0.2 or abs(ret) >= 12:
        risk_level = "средний"

    recommendation = "удерживать / наблюдать"
    if market == "bonds":
        ytm = fundamental.get("yield_to_maturity") if fundamental else None
        if ytm and ytm >= 12:
            recommendation = "доходность привлекательна, оценить кредитный риск эмитента"
        elif ret < -3:
            recommendation = "осторожно: отрицательная динамика цены"
    else:
        bullish = sum(1 for s in signals if "быч" in s.lower() or "перепродан" in s.lower())
        bearish = sum(1 for s in signals if "медвеж" in s.lower() or "перекуплен" in s.lower())
        if sharpe > 1 and bullish >= bearish:
            recommendation = "умеренно позитивный профиль риск/доходность"
        elif bearish > bullish or ret < -8:
            recommendation = "повышенная осторожность"

    paragraphs = [
        f"{ticker} ({instrument_type}): доходность за период {ret:.2f}%, "
        f"годовая волатильность {vol:.2%}, коэффициент Шарпа {sharpe:.2f}.",
    ]
    if beta is not None:
        paragraphs.append(f"Бета к индексу IMOEX: {beta:.2f}.")
    if fundamental and fundamental.get("dividend_yield_pct") is not None:
        paragraphs.append(f"Дивидендная доходность (оценка): {fundamental['dividend_yield_pct']:.2f}%.")
    if fundamental and fundamental.get("yield_to_maturity") is not None:
        paragraphs.append(f"Доходность к погашению: {fundamental['yield_to_maturity']:.2f}%.")

    if forecast and forecast.get("points"):
        horizon = forecast.get("horizon", 0)
        exp_ret = float(forecast.get("expected_return_pct", 0.0))
        trend = forecast.get("trend", "flat")
        trend_ru = {"up": "рост", "down": "снижение", "flat": "боковик"}.get(trend, trend)
        paragraphs.append(
            f"Прогноз на {horizon} торг. дней (метод {forecast.get('method', 'ema')}): "
            f"ожидаемое изменение {exp_ret:+.2f}%, сценарий — {trend_ru}."
        )
        metrics = forecast.get("metrics") or {}
        if metrics.get("mape") is not None:
            paragraphs.append(
                f"Ошибка модели на тесте (MAPE): {metrics['mape']:.2f}% "
                f"на {metrics.get('samples', 0)} точках."
            )

    paragraphs.append(f"Уровень риска: {risk_level}. Рекомендация: {recommendation}.")

    return {
        "risk_level": risk_level,
        "recommendation": recommendation,
        "paragraphs": paragraphs,
        "signals": signals,
    }


def _sma_series(values: list[float], period: int) -> list[float | None]:
    return _sma(values, period)


def bollinger_bands(
    closes: list[float],
    period: int = 20,
    std_mult: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Верхняя/средняя/нижняя полосы Боллинджера."""
    middle = _sma(closes, period)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for i, mid in enumerate(middle):
        if mid is None or i + 1 < period:
            upper.append(None)
            lower.append(None)
            continue
        window = closes[i + 1 - period : i + 1]
        sigma = _stddev(window)
        upper.append(mid + std_mult * sigma)
        lower.append(mid - std_mult * sigma)
    return upper, middle, lower


def support_resistance_levels(candles: list[dict], lookback: int = 20) -> dict:
    """Уровни поддержки/сопротивления по локальным экстремумам."""
    if len(candles) < lookback:
        return {"support": None, "resistance": None}

    lows = [float(c["low"]) for c in candles[-lookback:]]
    highs = [float(c["high"]) for c in candles[-lookback:]]
    return {
        "support": round(min(lows), 4),
        "resistance": round(max(highs), 4),
    }


def historical_var(daily_rets: list[float], confidence: float = 0.95) -> float:
    """Исторический VaR (доля капитала, отрицательное число = потеря)."""
    if len(daily_rets) < 10:
        return 0.0
    sorted_rets = sorted(daily_rets)
    index = int((1.0 - confidence) * len(sorted_rets))
    index = max(0, min(index, len(sorted_rets) - 1))
    return round(sorted_rets[index], 6)


def portfolio_var(
    positions: list[dict],
    confidence: float = 0.95,
) -> dict:
    """
    VaR портфеля: взвешенная сумма дневных доходностей позиций,
    затем исторический перцентиль. positions: weight_pct, daily_returns[].
    """
    if not positions:
        return {"var_daily_pct": 0.0, "var_weekly_pct": 0.0, "confidence": confidence}

    total_weight = sum(float(p.get("weight_pct", 0.0)) for p in positions) or 1.0
    max_len = max(len(p.get("daily_returns") or []) for p in positions)
    if max_len < 10:
        return {"var_daily_pct": 0.0, "var_weekly_pct": 0.0, "confidence": confidence}

    portfolio_rets: list[float] = []
    for i in range(max_len):
        day_ret = 0.0
        for pos in positions:
            rets = pos.get("daily_returns") or []
            if i >= len(rets):
                continue
            w = float(pos.get("weight_pct", 0.0)) / total_weight
            day_ret += w * float(rets[i])
        portfolio_rets.append(day_ret)

    var_daily = historical_var(portfolio_rets, confidence) * 100.0
    var_weekly = var_daily * sqrt(5)
    return {
        "var_daily_pct": round(var_daily, 4),
        "var_weekly_pct": round(var_weekly, 4),
        "confidence": confidence,
    }


def returns_distribution(daily_rets: list[float], bins: int = 20) -> dict:
    """Гистограмма дневных доходностей."""
    if not daily_rets:
        return {"bins": [], "counts": [], "mean": 0.0, "std": 0.0}

    min_v = min(daily_rets)
    max_v = max(daily_rets)
    if min_v == max_v:
        return {
            "bins": [{"from": min_v, "to": max_v, "mid": min_v}],
            "counts": [len(daily_rets)],
            "mean": round(mean(daily_rets), 6),
            "std": 0.0,
        }

    width = (max_v - min_v) / bins
    counts = [0] * bins
    bin_edges: list[dict] = []
    for i in range(bins):
        left = min_v + i * width
        right = min_v + (i + 1) * width
        bin_edges.append({"from": round(left, 6), "to": round(right, 6), "mid": round((left + right) / 2, 6)})
    for r in daily_rets:
        idx = min(bins - 1, int((r - min_v) / width) if width else 0)
        counts[idx] += 1
    return {
        "bins": bin_edges,
        "counts": counts,
        "mean": round(mean(daily_rets), 6),
        "std": round(_stddev(daily_rets), 6),
    }


def chart_overlays(candles: list[dict], bb_period: int = 20) -> dict:
    """Данные для графика: Bollinger и уровни."""
    closes = [float(c["close"]) for c in candles]
    dates = [str(c["date"]) for c in candles]
    upper, middle, lower = bollinger_bands(closes, bb_period)
    levels = support_resistance_levels(candles)

    points: list[dict] = []
    for i, d in enumerate(dates):
        row: dict = {"date": d}
        if upper[i] is not None:
            row["bb_upper"] = round(upper[i], 4)
            row["bb_middle"] = round(middle[i], 4)
            row["bb_lower"] = round(lower[i], 4)
        points.append(row)

    return {
        "bollinger": points,
        "support": levels.get("support"),
        "resistance": levels.get("resistance"),
    }


def run_walk_forward_backtest(
    candles: list[dict],
    fast: int = 20,
    slow: int = 50,
    window_days: int = 60,
    step_days: int = 20,
) -> dict:
    """Walk-forward: скользящие окна, отчёт по каждому периоду."""
    if len(candles) < slow + window_days + 5:
        return {"periods": [], "avg_strategy_return_pct": 0.0, "avg_buy_hold_return_pct": 0.0}

    periods: list[dict] = []
    start = window_days
    while start + step_days <= len(candles):
        window = candles[start - window_days : start + step_days]
        result = run_ema_backtest(window, fast=fast, slow=slow)
        periods.append(
            {
                "from_date": str(window[0]["date"]),
                "to_date": str(window[-1]["date"]),
                "strategy_return_pct": result["strategy_return_pct"],
                "buy_hold_return_pct": result["buy_hold_return_pct"],
                "trades": result["trades"],
                "win_rate": result["win_rate"],
            }
        )
        start += step_days

    if not periods:
        return {"periods": [], "avg_strategy_return_pct": 0.0, "avg_buy_hold_return_pct": 0.0}

    return {
        "periods": periods,
        "avg_strategy_return_pct": round(mean(p["strategy_return_pct"] for p in periods), 4),
        "avg_buy_hold_return_pct": round(mean(p["buy_hold_return_pct"] for p in periods), 4),
    }


def portfolio_metrics(positions: list[dict]) -> dict:
    """positions: [{ticker, weight_pct, return_pct, volatility, beta}]"""
    if not positions:
        return {
            "positions_count": 0,
            "total_weight_pct": 0.0,
            "expected_return_pct": 0.0,
            "portfolio_volatility": 0.0,
            "herfindahl_index": 0.0,
            "effective_assets": 0.0,
            "warnings": ["Портфель пуст"],
        }

    total_weight = sum(float(p.get("weight_pct", 0.0)) for p in positions)
    weights = [float(p.get("weight_pct", 0.0)) / (total_weight or 1.0) for p in positions]
    expected_return = sum(w * float(p.get("return_pct", 0.0)) for w, p in zip(weights, positions))
    portfolio_vol = sqrt(sum((w * float(p.get("volatility", 0.0))) ** 2 for w, p in zip(weights, positions)))
    hhi = sum(w ** 2 for w in weights)
    effective_assets = 1.0 / hhi if hhi > 0 else 0.0

    warnings: list[str] = []
    if abs(total_weight - 100.0) > 0.5:
        warnings.append(f"Сумма весов {total_weight:.1f}% — рекомендуется 100%")
    if hhi > 0.4:
        warnings.append("Высокая концентрация: портфель зависит от нескольких бумаг")
    if portfolio_vol > 0.35:
        warnings.append("Повышенная совокупная волатильность портфеля")

    return {
        "positions_count": len(positions),
        "total_weight_pct": round(total_weight, 2),
        "expected_return_pct": round(expected_return, 4),
        "portfolio_volatility": round(portfolio_vol, 6),
        "herfindahl_index": round(hhi, 4),
        "effective_assets": round(effective_assets, 2),
        "warnings": warnings,
    }
