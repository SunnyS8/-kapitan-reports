"""Отчёт: Динамика продаж (сравнение периодов)."""
import pandas as pd
from pathlib import Path

from app.services.internal_clients import is_internal_client
from app.config import INTERNAL_CLIENT_TAG


def generate_dynamics(filepaths: list[Path]) -> dict:
    from app.services.excel_parser import read_sales_excel

    if len(filepaths) < 2:
        return {"summary": {"error": "Нужно минимум 2 файла для сравнения"}, "data": [], "chart": {}}

    period_data = []
    internal_by_period = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_sales_excel(fp)
            internal_df = None
            if "client" in df.columns:
                df["is_internal"] = df["client"].map(is_internal_client)
                internal_df = df[df["is_internal"]]
                df = df[~df["is_internal"]].drop(columns=["is_internal"])
            total = float(df["sum"].sum()) if "sum" in df.columns else 0
            count = int(df["sum"].count()) if "sum" in df.columns else 0
            period_data.append({"name": fp.stem, "revenue": round(total, 2), "sales_count": count})
            if internal_df is not None and not internal_df.empty:
                internal_by_period.append({
                    "Период": fp.stem,
                    "Сумма": round(float(internal_df["sum"].sum()), 2),
                    "Пометка": INTERNAL_CLIENT_TAG,
                })
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if len(period_data) < 2:
        return {"summary": {"error": "Не удалось распарсить достаточно файлов", "debug": debug_all}, "data": [], "chart": {}}

    p1, p2 = period_data[0], period_data[1]
    diff = p2["revenue"] - p1["revenue"]
    pct = (diff / p1["revenue"] * 100) if p1["revenue"] else 0

    data = [{"period": pd_item["name"], "revenue": pd_item["revenue"], "sales_count": pd_item["sales_count"]} for pd_item in period_data]

    summary = {
        "period_1": p1["name"], "period_2": p2["name"],
        "revenue_1": p1["revenue"], "revenue_2": p2["revenue"],
        "diff": round(diff, 2), "diff_pct": round(pct, 1),
        "trend": "up" if diff > 0 else "down" if diff < 0 else "flat",
        "internal_total": round(float(sum(r["Сумма"] for r in internal_by_period)), 2),
        "internal_count": len(internal_by_period),
        "debug": debug_all,
    }

    chart = {"labels": [d["period"][:20] for d in data], "values": [d["revenue"] for d in data]}
    return {"summary": summary, "data": data, "chart": chart,
            "internal": internal_by_period if internal_by_period else []}
