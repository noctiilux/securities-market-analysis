from __future__ import annotations

import csv
import io
from typing import Any


def report_to_csv(report: dict[str, Any]) -> str:
    """Формирует CSV-отчёт по бумаге."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Поле", "Значение"])
    writer.writerow(["Тикер", report.get("ticker", "")])
    writer.writerow(["Рынок", report.get("market", "")])
    writer.writerow(["Период с", report.get("from_date", "")])
    writer.writerow(["Период по", report.get("to_date", "")])

    passport = report.get("passport") or {}
    writer.writerow(["Название", passport.get("name", "")])
    writer.writerow(["Тип", passport.get("instrument_type", "")])
    writer.writerow(["Цена", passport.get("current_price", "")])

    technical = report.get("technical") or {}
    writer.writerow(["Доходность %", technical.get("return_pct", "")])
    writer.writerow(["Волатильность", technical.get("volatility", "")])
    writer.writerow(["Sharpe", technical.get("sharpe", "")])
    writer.writerow(["Sortino", technical.get("sortino", "")])
    writer.writerow(["Beta", technical.get("beta", "")])
    writer.writerow(["RSI14", technical.get("rsi14", "")])
    writer.writerow(["EMA20", technical.get("ema20", "")])
    writer.writerow(["EMA50", technical.get("ema50", "")])
    writer.writerow(["MACD", technical.get("macd", "")])

    fundamental = report.get("fundamental") or {}
    writer.writerow(["Див. доходность %", fundamental.get("dividend_yield_pct", "")])
    writer.writerow(["YTM %", fundamental.get("yield_to_maturity", "")])

    forecast = report.get("forecast") or {}
    writer.writerow(["Прогноз метод", forecast.get("method", "")])
    writer.writerow(["Прогноз изменение %", forecast.get("expected_return_pct", "")])
    metrics = forecast.get("metrics") or {}
    writer.writerow(["MAPE", metrics.get("mape", "")])

    writer.writerow([])
    writer.writerow(["Сигналы"])
    for signal in technical.get("signals") or []:
        writer.writerow(["", signal])

    summary = report.get("summary") or {}
    writer.writerow([])
    writer.writerow(["Уровень риска", summary.get("risk_level", "")])
    writer.writerow(["Рекомендация", summary.get("recommendation", "")])
    for paragraph in summary.get("paragraphs") or []:
        writer.writerow(["Вывод", paragraph])

    return buffer.getvalue()


def report_to_pdf_bytes(report: dict[str, Any]) -> bytes:
    """Простой PDF-отчёт (латиница + кириллица через встроенный шрифт fpdf2)."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    def line(text: str) -> None:
        safe = text.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 8, safe)

    line(f"Security report: {report.get('ticker', '')}")
    line(f"Market: {report.get('market', '')}")
    line(f"Period: {report.get('from_date', '')} - {report.get('to_date', '')}")
    pdf.ln(4)

    passport = report.get("passport") or {}
    line(f"Name: {passport.get('name', '')}")
    line(f"Type: {passport.get('instrument_type', '')}")
    line(f"Price: {passport.get('current_price', '')}")
    pdf.ln(4)

    technical = report.get("technical") or {}
    line("Technical & risk:")
    line(f"  Return %: {technical.get('return_pct', '')}")
    line(f"  Volatility: {technical.get('volatility', '')}")
    line(f"  Sharpe: {technical.get('sharpe', '')}")
    line(f"  Sortino: {technical.get('sortino', '')}")
    line(f"  Beta: {technical.get('beta', '')}")
    line(f"  RSI14: {technical.get('rsi14', '')}")
    pdf.ln(4)

    forecast = report.get("forecast") or {}
    if forecast:
        line("Forecast:")
        line(f"  Method: {forecast.get('method', '')}")
        line(f"  Expected change %: {forecast.get('expected_return_pct', '')}")
        metrics = forecast.get("metrics") or {}
        line(f"  MAPE: {metrics.get('mape', '')}")
        pdf.ln(4)

    summary = report.get("summary") or {}
    line(f"Risk level: {summary.get('risk_level', '')}")
    line(f"Recommendation: {summary.get('recommendation', '')}")
    for paragraph in summary.get("paragraphs") or []:
        line(str(paragraph))

    return bytes(pdf.output())
