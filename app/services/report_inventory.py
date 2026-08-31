"""Отчёт: Остатки на складах."""
import pandas as pd
from pathlib import Path


def generate_inventory(filepaths: list[Path], threshold_days: int = 90) -> dict:
    """
    Остатки на складах с категоризацией по давности.
    """
    from app.services.excel_parser import read_stock_excel

    frames = []
    for fp in filepaths:
        try:
            df = read_stock_excel(fp)
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return {"summary": {}, "data": [], "chart": {}}

    df = pd.concat(frames, ignore_index=True)

    data = []
    for _, row in df.iterrows():
        item = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                item[col] = ""
            elif isinstance(val, (int, float)):
                item[col] = round(float(val), 2)
            else:
                item[col] = str(val)
        data.append(item)

    # Summary по складам
    total_end = 0
    if "end_balance" in df.columns:
        total_end = float(df["end_balance"].sum())

    warehouse_stats = {}
    if "warehouse" in df.columns:
        for wh, grp in df.groupby("warehouse", dropna=False):
            wh_name = str(wh) if pd.notna(wh) else "Неизвестный"
            warehouse_stats[wh_name] = {
                "count": len(grp),
                "end_balance": round(float(grp["end_balance"].sum()), 2) if "end_balance" in grp.columns else 0,
            }

    summary = {
        "total_items": len(df),
        "total_end_balance": round(total_end, 2),
        "warehouses": warehouse_stats,
    }

    chart = {
        "labels": list(warehouse_stats.keys()),
        "values": [v["end_balance"] for v in warehouse_stats.values()],
    }

    return {"summary": summary, "data": data, "chart": chart}
