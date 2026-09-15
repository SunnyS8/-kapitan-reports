"""Отчёт: Незавершённые ЭДО (2.2)."""
import math
import pandas as pd
from typing import Optional
from pathlib import Path
from datetime import datetime


def _num(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def generate_edo(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """Реестр незавершённых ЭДО: Клиент | Адрес | Номер накладной | Сумма |
    Состояние | Остановлен."""
    from app.services.excel_parser import read_edo_excel, _filter_by_date

    frames = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_edo_excel(fp)
            frames.append(df)
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if not frames:
        return {"summary": {"error": "Не удалось распарсить файлы", "debug": debug_all}, "data": [], "chart": {}}

    df = pd.concat(frames, ignore_index=True)
    df = _filter_by_date(df, date_from, date_to)

    if "client" not in df.columns:
        return {"summary": {"error": "Колонка 'Клиент' не найдена", "debug": debug_all}, "data": [], "chart": {}}

    data = []
    for _, row in df.iterrows():
        state = str(row.get("state", "")) if pd.notna(row.get("state", None)) else ""
        stopped = str(row.get("stopped", "")) if pd.notna(row.get("stopped", None)) else ""
        item = {
            "Клиент": str(row.get("client", "")) if pd.notna(row.get("client")) else "Без имени",
            "Адрес": str(row.get("address", "")) if pd.notna(row.get("address", None)) else "",
            "Номер накладной": str(row.get("invoice_number", "")) if pd.notna(row.get("invoice_number", None)) else "",
            "Сумма": round(_num(row.get("sum", 0)), 2),
            "Состояние": state,
            "Остановлен": stopped,
            "territory": str(row.get("city", "")) if "city" in df.columns else "",
            "manager": str(row.get("manager", "")) if "manager" in df.columns else "",
        }
        data.append(item)

    data.sort(key=lambda x: x["Сумма"], reverse=True)

    total_sum = sum(d["Сумма"] for d in data)
    stopped_count = sum(1 for d in data if d["Остановлен"].strip().lower() in ("да", "1", "истина", "true"))

    summary = {
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "total_docs": len(data),
        "total_sum": round(total_sum, 2),
        "stopped_count": stopped_count,
        "debug": debug_all,
    }

    chart = {
        "labels": [d["Клиент"][:20] for d in data[:10]],
        "values": [d["Сумма"] for d in data[:10]],
    }

    return {"summary": summary, "data": data, "chart": chart}