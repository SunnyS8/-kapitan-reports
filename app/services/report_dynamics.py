"""Отчёт: Динамика продаж (сравнение периодов)."""
import pandas as pd
from pathlib import Path


def generate_dynamics(filepaths: list[Path]) -> dict:
    """
    Сравнение продаж между периодами (2+ файла).
    """
    from app.services.excel_parser import read_sales_excel

    if len(filepaths) < 2:
        return {
            "summary": {"error": "Нужно минимум 2 файла для сравнения"},
            "data": [],
            "chart": {},
        }

    period_data = []
    for fp in filepaths:
        try:
            df = read_sales_excel(fp)
            total = float(df["sum"].sum()) if "sum" in df.columns else 0
            count = int(df["sum"].count()) if "sum" in df.columns else 0
            period_data.append({
                "name": fp.stem,
                "revenue": round(total, 2),
                "sales_count": count,
            })
        except Exception:
            continue

    if len(period_data) < 2:
        return {"summary": {"error": "Не удалось распарсить достаточно файлов"}, "data": [], "chart": {}}

    # Сравнение первых двух периодов
    p1, p2 = period_data[0], period_data[1]
    diff = p2["revenue"] - p1["revenue"]
    pct = (diff / p1["revenue"] * 100) if p1["revenue"] else 0

    data = []
    for pd_item in period_data:
        data.append({
            "period": pd_item["name"],
            "revenue": pd_item["revenue"],
            "sales_count": pd_item["sales_count"],
        })

    summary = {
        "period_1": p1["name"],
        "period_2": p2["name"],
        "revenue_1": p1["revenue"],
        "revenue_2": p2["revenue"],
        "diff": round(diff, 2),
        "diff_pct": round(pct, 1),
        "trend": "up" if diff > 0 else "down" if diff < 0 else "flat",
    }

    chart = {
        "labels": [d["period"][:20] for d in data],
        "values": [d["revenue"] for d in data],
    }

    return {"summary": summary, "data": data, "chart": chart}
