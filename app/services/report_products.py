"""Отчёт: Продажи по товарам (ABC-анализ)."""
import pandas as pd
from pathlib import Path

from app.services.excel_parser import compute_date_period


def generate_sales_products(filepaths: list[Path]) -> dict:
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

    period = compute_date_period(df)

    if "product" not in df.columns:
        available = list(df.columns)
        return {
            "summary": {"error": f"Колонка 'Товар' не найдена. Доступные колонки: {available}", "debug": debug_all},
            "data": [], "chart": {},
        }

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
        "generated_at": period["generated_at"],
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "total_revenue": round(float(total), 2),
        "total_products": len(grouped),
        "count_a": abc_counts.get("A", 0),
        "count_b": abc_counts.get("B", 0),
        "count_c": abc_counts.get("C", 0),
        "debug": debug_all,
    }

    chart = {
        "labels": [d["product"][:20] for d in data[:15]],
        "values": [d["revenue"] for d in data[:15]],
        "colors": ["#16a34a" if d["category"] == "A" else "#eab308" if d["category"] == "B" else "#dc2626" for d in data[:15]],
    }

    return {"summary": summary, "data": data, "chart": chart}
