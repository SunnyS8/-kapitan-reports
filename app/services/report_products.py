"""Отчёт: Продажи по товарам (ABC-анализ)."""
import pandas as pd
from pathlib import Path


def generate_sales_products(filepaths: list[Path]) -> dict:
    """
    ABC-анализ продаж по товарам.
    A = 80% выручки, B = 15%, C = 5%.
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

    if "product" not in df.columns:
        return {"summary": {"error": "Колонка 'Товар' не найдена"}, "data": [], "chart": {}}

    grouped = df.groupby("product", dropna=False).agg(
        revenue=("sum", "sum"),
        quantity=("quantity", "sum") if "quantity" in df.columns else ("sum", "count"),
    ).reset_index()

    total = grouped["revenue"].sum()
    grouped = grouped.sort_values("revenue", ascending=False)
    grouped["cum_share"] = (grouped["revenue"].cumsum() / total * 100).round(1) if total else 0

    def abc_category(cum):
        if cum <= 80:
            return "A"
        elif cum <= 95:
            return "B"
        return "C"

    grouped["category"] = grouped["cum_share"].apply(abc_category)
    grouped["share"] = (grouped["revenue"] / total * 100).round(1) if total else 0

    data = []
    for _, row in grouped.iterrows():
        data.append({
            "product": str(row["product"]) if pd.notna(row["product"]) else "Без названия",
            "category": row["category"],
            "revenue": round(float(row["revenue"]), 2),
            "quantity": int(row.get("quantity", 0)),
            "share": float(row["share"]),
            "cum_share": float(row["cum_share"]),
        })

    abc_counts = grouped["category"].value_counts().to_dict()
    summary = {
        "total_revenue": round(float(total), 2),
        "total_products": len(grouped),
        "count_a": abc_counts.get("A", 0),
        "count_b": abc_counts.get("B", 0),
        "count_c": abc_counts.get("C", 0),
    }

    chart = {
        "labels": [d["product"][:20] for d in data[:15]],
        "values": [d["revenue"] for d in data[:15]],
        "colors": ["#16a34a" if d["category"] == "A" else "#eab308" if d["category"] == "B" else "#dc2626" for d in data[:15]],
    }

    return {"summary": summary, "data": data, "chart": chart}
