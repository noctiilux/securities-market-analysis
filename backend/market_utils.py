from __future__ import annotations

MARKET_MAPPING: dict[str, tuple[str, str]] = {
    "shares": ("stock", "shares"),
    "bonds": ("stock", "bonds"),
    "futures": ("futures", "forts"),
    "etf": ("stock", "shares"),
    "index": ("stock", "index"),
}

BENCHMARK_TICKER = "IMOEX"
BENCHMARK_MARKET = "index"

GROUP_TO_MARKET: dict[str, str] = {
    "stock_shares": "shares",
    "stock_bonds": "bonds",
    "stock_etf": "etf",
    "stock_ppif": "etf",
    "futures_forts": "futures",
    "stock_index": "index",
}

INSTRUMENT_LABELS: dict[str, str] = {
    "shares": "Акция",
    "bonds": "Облигация",
    "futures": "Фьючерс",
    "etf": "ETF/БПИФ",
    "index": "Индекс",
}


def normalize_market(market: str | None) -> str:
    value = (market or "shares").lower().strip()
    if value not in MARKET_MAPPING:
        raise ValueError(f"Неподдерживаемый рынок: {market}")
    return value


def engine_market(market: str) -> tuple[str, str]:
    return MARKET_MAPPING[normalize_market(market)]


def market_from_group(group: str | None, sec_type: str | None = None) -> str:
    group_norm = str(group or "").lower().strip()
    if group_norm in GROUP_TO_MARKET:
        return GROUP_TO_MARKET[group_norm]
    type_norm = str(sec_type or "").lower().strip()
    if "bond" in type_norm or "облига" in type_norm:
        return "bonds"
    if "future" in type_norm or "фьюч" in type_norm:
        return "futures"
    if "etf" in type_norm or "пиф" in type_norm or "фонд" in type_norm:
        return "etf"
    return "shares"
