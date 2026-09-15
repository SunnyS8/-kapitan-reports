"""Отчёт: Реестр клиентов (2.1)."""
import pandas as pd
from typing import Optional
from pathlib import Path
from datetime import datetime


def generate_clients(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """Реестр клиентов: Менеджер | Клиент | Город | Адрес | Телефон | Плательщик."""
    from app.services.excel_parser import read_clients_excel, _filter_by_date

    frames = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_clients_excel(fp)
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
        item = {
            "Менеджер": str(row.get("manager", "")) if pd.notna(row.get("manager", None)) else "",
            "Клиент": str(row.get("client", "")) if pd.notna(row.get("client")) else "Без имени",
            "Город": str(row.get("city", "")) if pd.notna(row.get("city", None)) else "",
            "Адрес": str(row.get("address", "")) if pd.notna(row.get("address", None)) else "",
            "Телефон": str(row.get("phone", "")) if pd.notna(row.get("phone", None)) else "",
            "Плательщик": str(row.get("payer", "")) if pd.notna(row.get("payer", None)) else "",
        }
        data.append(item)

    data.sort(key=lambda x: x["Клиент"])

    summary = {
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "total_clients": len(data),
        "debug": debug_all,
    }

    return {"summary": summary, "data": data, "chart": {}}