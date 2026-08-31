"""Отчёт: Продажи по клиентам."""
import pandas as pd
from pathlib import Path


def generate_sales_clients(filepaths: list[Path]) -> dict:
    from app.services.excel_parser import read_sales_excel

    frames = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_sales_excel(fp)
            frames.append(df)
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if not frames:
        return {"summary": {"error": "Не удалось распарсить файлы", "debug": debug_all}, "data": [], "chart": {}}

    df = pd.concat(frames, ignore_index=True)

    if "client" not in df.columns:
        available = list(df.columns)
        return {
            "summary": {"error": f"Колонка 'Клиент' не найдена. Доступные колонки: {available}", "debug": debug_all},
            "data": [], "chart": {},
        }

    grouped = df.groupby("client", dropna=False).agg(
        revenue=("sum", "sum"),
        sales_count=("sum", "count"),
    ).reset_index()

    grouped["avg_check"] = grouped["revenue"] / grouped["sales_count"].replace(0, 1)
    total_revenue = grouped["revenue"].sum()
    grouped["share"] = (grouped["revenue"] / total_revenue * 100).round(1) if total_revenue else 0
    grouped = grouped.sort_values("revenue", ascending=False)

    data = []
    for _, row in grouped.iterrows():
        data.append({
            "client": str(row["client"]) if pd.notna(row["client"]) else "Без имени",
            "revenue": round(float(row["revenue"]), 2),
            "sales_count": int(row["sales_count"]),
            "avg_check": round(float(row["avg_check"]), 2),
            "share": float(row["share"]),
        })

    summary = {
        "total_revenue": round(float(total_revenue), 2),
        "total_clients": len(grouped),
        "total_sales": int(grouped["sales_count"].sum()),
        "avg_check": round(float(total_revenue / max(grouped["sales_count"].sum(), 1)), 2),
        "debug": debug_all,
    }

    chart = {
        "labels": [d["client"][:20] for d in data[:10]],
        "values": [d["revenue"] for d in data[:10]],
    }

    return {"summary": summary, "data": data, "chart": chart}
