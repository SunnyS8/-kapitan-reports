"""Отчёт: Продажи по клиентам."""
import pandas as pd
from pathlib import Path
from typing import Optional

from app.services.excel_parser import compute_date_period, _filter_by_date
from app.services.internal_clients import is_internal_client
from app.config import INTERNAL_CLIENT_TAG


def generate_sales_clients(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
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
    df = _filter_by_date(df, date_from, date_to)

    period = compute_date_period(df)

    if "client" not in df.columns:
        available = list(df.columns)
        return {
            "summary": {"error": f"Колонка 'Клиент' не найдена. Доступные колонки: {available}", "debug": debug_all},
            "data": [], "chart": {},
        }

    # Внутренние контрагенты (для НДС) — отдельным блоком, в общие результаты не входят.
    df["is_internal"] = df["client"].map(is_internal_client)
    internal_df = df[df["is_internal"]]
    df = df[~df["is_internal"]].drop(columns=["is_internal"])

    # Дополнительные поля клиента (3.4): берём первое непустое значение по клиенту.
    extra_fields = {}
    for col, field in (("address", "address"), ("city", "city"),
                       ("organization", "organization"), ("manager", "manager")):
        if col in df.columns:
            s = (df.groupby("client", dropna=False)[col]
                   .agg(lambda x: next((v for v in x if pd.notna(v) and str(v).strip() and str(v).lower() not in ("nan", "none", "")), ""))
                   .reset_index(name=f"__{field}"))
            extra_fields[field] = s

    grouped = df.groupby("client", dropna=False).agg(
        revenue=("sum", "sum"),
        sales_count=("sum", "count"),
    ).reset_index()

    for field, s in extra_fields.items():
        grouped = grouped.merge(s, on="client", how="left")
        grouped[field] = grouped[f"__{field}"].fillna("")
        grouped = grouped.drop(columns=[f"__{field}"])

    grouped["avg_check"] = grouped["revenue"] / grouped["sales_count"].replace(0, 1)
    total_revenue = grouped["revenue"].sum()
    grouped["share"] = (grouped["revenue"] / total_revenue * 100).round(1) if total_revenue else 0
    grouped = grouped.sort_values("revenue", ascending=False)

    data = []
    for _, row in grouped.iterrows():
        item = {
            "client": str(row["client"]) if pd.notna(row["client"]) else "Без имени",
            "revenue": round(float(row["revenue"]), 2),
            "sales_count": int(row["sales_count"]),
            "avg_check": round(float(row["avg_check"]), 2),
            "share": float(row["share"]),
        }
        for field in ("address", "city", "organization", "manager"):
            if field in grouped.columns:
                item[field] = str(row[field])
        item["territory"] = str(row["city"]) if "city" in grouped.columns and pd.notna(row["city"]) else ""
        data.append(item)

    # Внутренние контрагенты — отдельным блоком с пометкой
    internal_rows = []
    if not internal_df.empty:
        ig = internal_df.groupby("client", dropna=False).agg(
            revenue=("sum", "sum"),
            sales_count=("sum", "count"),
        ).reset_index()
        ig = ig.sort_values("revenue", ascending=False)
        internal_total = float(ig["revenue"].sum())
        for _, row in ig.iterrows():
            internal_rows.append({
                "client": str(row["client"]) if pd.notna(row["client"]) else "Без имени",
                "revenue": round(float(row["revenue"]), 2),
                "sales_count": int(row["sales_count"]),
                "avg_check": round(float(row["revenue"] / max(row["sales_count"], 1)), 2),
                "Пометка": INTERNAL_CLIENT_TAG,
            })
    else:
        internal_total = 0.0

    summary = {
        "generated_at": period["generated_at"],
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "total_revenue": round(float(total_revenue), 2),
        "total_clients": len(grouped),
        "total_sales": int(grouped["sales_count"].sum()),
        "avg_check": round(float(total_revenue / max(grouped["sales_count"].sum(), 1)), 2),
        "internal_total": round(internal_total, 2),
        "internal_count": len(internal_rows),
        "debug": debug_all,
    }

    chart = {
        "labels": [d["client"][:20] for d in data[:10]],
        "values": [d["revenue"] for d in data[:10]],
    }

    return {"summary": summary, "data": data, "chart": chart, "internal": internal_rows}
