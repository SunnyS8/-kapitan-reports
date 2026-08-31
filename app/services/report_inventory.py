"""Отчёт: Остатки на складах."""
import pandas as pd
from pathlib import Path


def generate_inventory(filepaths: list[Path], threshold_days: int = 90) -> dict:
    from app.services.excel_parser import read_stock_excel

    frames = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_stock_excel(fp)
            frames.append(df)
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if not frames:
        return {"summary": {"error": "Не удалось распарсить файлы", "debug": debug_all}, "data": [], "chart": {}}

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
        "debug": debug_all,
    }

    chart = {
        "labels": list(warehouse_stats.keys()),
        "values": [v["end_balance"] for v in warehouse_stats.values()],
    }

    return {"summary": summary, "data": data, "chart": chart}
