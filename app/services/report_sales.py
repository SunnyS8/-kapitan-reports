"""Отчёт: Продажи по клиентам."""
import pandas as pd
from pathlib import Path


def generate_sales_clients(filepaths: list[Path]) -> dict:
    """
    Группировка продаж по клиенту.
    Возвращает: summary, data, chart_data.
    """
    from app.services.excel_parser import read_sales_excel

    frames = []
    for fp in filepaths:
        try:
            df = read_sales_excel(fp)
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return {"summary": {}, "data": [], "chart": {}}

    df = pd.concat(frames, ignore_index=True)

    if "client" not in df.columns:
        return {"summary": {"error": "Колонка 'Клиент' не найдена"}, "data": [], "chart": {}}

    # Группировка по клиенту
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
    }

    chart = {
        "labels": [d["client"][:20] for d in data[:10]],
        "values": [d["revenue"] for d in data[:10]],
    }

    return {"summary": summary, "data": data, "chart": chart}
