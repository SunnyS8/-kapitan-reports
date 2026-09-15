"""Отчёт: Динамика продаж (помесячно, без внутренних контрагентов)."""
import pandas as pd
from typing import Optional
from pathlib import Path

from app.services.internal_clients import is_internal_client
from app.config import INTERNAL_CLIENT_TAG

_MONTHS_RU = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


def _month_label(period):
    """'2025-01' -> 'Январь 2025'."""
    try:
        y, m = str(period).split("-")
        return f"{_MONTHS_RU[int(m) - 1].capitalize()} {y}"
    except Exception:
        return str(period)


def generate_dynamics(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    from app.services.excel_parser import read_sales_excel, _filter_by_date

    frames = []
    internal_frames = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_sales_excel(fp)
            internal_df = None
            if "client" in df.columns:
                df["is_internal"] = df["client"].map(is_internal_client)
                internal_df = df[df["is_internal"]]
                df = df[~df["is_internal"]].drop(columns=["is_internal"])
            frames.append(df)
            if internal_df is not None and not internal_df.empty:
                internal_frames.append(internal_df)
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if not frames or not any("sum" in df.columns for df in frames):
        return {"summary": {"error": "Не удалось распарсить файлы продаж", "debug": debug_all}, "data": [], "chart": {}, "categories": [], "top_products": []}

    df = pd.concat(frames, ignore_index=True)
    df = _filter_by_date(df, date_from, date_to)

    if "date" not in df.columns:
        return {"summary": {"error": "В выгрузках нет колонки с датами — нельзя построить помесячную динамику.", "debug": debug_all}, "data": [], "chart": {}, "categories": [], "top_products": []}

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date"])
    df["period"] = df["date"].dt.to_period("M").astype(str)

    grouped = df.groupby("period").agg(
        revenue=("sum", "sum"),
        sales_count=("sum", "count"),
    ).reset_index().sort_values("period")

    total = float(grouped["revenue"].sum())
    total_sales = int(grouped["sales_count"].sum())

    # --- Уникальные клиенты и количество товара по месяцам ---
    clients_per_period = df.groupby("period")["client"].nunique() if "client" in df.columns else pd.Series(dtype=int)
    quantity_per_period = df.groupby("period")["quantity"].sum() if "quantity" in df.columns else pd.Series(dtype=float)
    quantity_m2_per_period = df.groupby("period")["quantity_m2"].sum() if "quantity_m2" in df.columns else pd.Series(dtype=float)

    data = []
    prev_revenue = None
    for _, row in grouped.iterrows():
        rev = float(row["revenue"])
        sales_cnt = int(row["sales_count"])
        mom_pct = None
        if prev_revenue:
            mom_pct = round((rev - prev_revenue) / prev_revenue * 100, 1) if prev_revenue else 0.0
        territory = ""
        manager = ""
        if "city" in df.columns:
            period_clients = df[df["period"] == row["period"]]["city"].dropna()
            if len(period_clients):
                territory = str(period_clients.iloc[0])
        if "manager" in df.columns:
            period_managers = df[df["period"] == row["period"]]["manager"].dropna()
            if len(period_managers):
                manager = str(period_managers.iloc[0])
        client_count = int(clients_per_period.get(row["period"], 0)) if row["period"] in clients_per_period.index else 0
        qty = float(quantity_per_period.get(row["period"], 0)) if row["period"] in quantity_per_period.index else 0
        qty_m2 = float(quantity_m2_per_period.get(row["period"], 0)) if row["period"] in quantity_m2_per_period.index else 0
        data.append({
            "period": row["period"],
            "month": _month_label(row["period"]),
            "revenue": round(rev, 2),
            "sales_count": sales_cnt,
            "avg_check": round(rev / sales_cnt, 2) if sales_cnt else 0.0,
            "mom_pct": mom_pct,
            "territory": territory,
            "manager": manager,
            "client_count": client_count,
            "quantity": round(qty, 2),
            "quantity_m2": round(qty_m2, 2),
        })
        prev_revenue = rev

    # Первый месяц — mom = null, говорим про него иначе
    if data:
        data[0]["mom_pct"] = None

    best = max(data, key=lambda d: d["revenue"]) if data else {}
    worst = min(data, key=lambda d: d["revenue"]) if data else {}

    # --- Продажи по складам помесячно ---
    wh_col = "warehouse" if "warehouse" in df.columns else "city"
    by_warehouse = []
    chart_warehouse = {"labels": [], "datasets": []}
    if wh_col in df.columns:
        wh = df[wh_col].fillna("Без склада").astype(str)
        wg = df.groupby([wh, "period"]).agg(
            revenue=("sum", "sum"),
            sales_count=("sum", "count"),
        ).reset_index()
        by_warehouse = [
            {
                "period": row["period"],
                "month": _month_label(row["period"]),
                "warehouse": row[wh_col],
                "revenue": round(float(row["revenue"]), 2),
                "sales_count": int(row["sales_count"]),
            }
            for _, row in wg.iterrows()
        ]
        by_warehouse.sort(key=lambda d: d["period"])
        warehouses = sorted({d["warehouse"] for d in by_warehouse})
        months = []
        for p in sorted({d["period"] for d in by_warehouse}):
            if p not in months:
                months.append(p)
        rev_by = {}
        for d in by_warehouse:
            rev_by.setdefault(d["warehouse"], {})[d["period"]] = d["revenue"]
        chart_warehouse = {
            "labels": [_month_label(p) for p in months],
            "datasets": [
                {"label": w, "values": [round(rev_by.get(w, {}).get(p, 0), 2) for p in months]}
                for w in warehouses
            ],
        }

    # --- Категории по месяцам ---
    categories = []
    if "category" in df.columns:
        cat_period = df.groupby(["category", "period"])["sum"].sum().reset_index()
        cats = sorted({c for c in cat_period["category"].unique()})
        cat_periods = sorted(cat_period["period"].unique())
        for cat in cats:
            cat_data = cat_period[cat_period["category"] == cat].set_index("period")["sum"].to_dict()
            categories.append({
                "category": cat,
                "values": [round(float(cat_data.get(p, 0)), 2) for p in cat_periods],
                "periods": cat_periods,
            })
        # Таблица категорий по месяцам
        cat_table = []
        for _, row in cat_period.iterrows():
            cat_table.append({
                "period": row["period"],
                "month": _month_label(row["period"]),
                "category": str(row["category"]),
                "revenue": round(float(row["sum"]), 2),
            })
    else:
        cat_table = []

    # --- Топ-5 товаров по месяцам ---
    top_products = []
    if "product" in df.columns:
        for period_val in sorted(df["period"].unique()):
            period_df = df[df["period"] == period_val]
            top = period_df.groupby("product")["sum"].sum().sort_values(ascending=False).head(5).reset_index()
            for rank, (_, row) in enumerate(top.iterrows(), 1):
                top_products.append({
                    "period": period_val,
                    "month": _month_label(period_val),
                    "product": str(row["product"]),
                    "revenue": round(float(row["sum"]), 2),
                    "rank": rank,
                })

    # Внутренние контрагенты отдельным блоком (по месяцам)
    internal_rows = []
    if internal_frames:
        idf = pd.concat(internal_frames, ignore_index=True)
        if "date" in idf.columns:
            idf["date"] = pd.to_datetime(idf["date"], errors="coerce", dayfirst=True)
            idf = idf.dropna(subset=["date"])
            idf["period"] = idf["date"].dt.to_period("M").astype(str)
            ig = idf.groupby("period").agg(revenue=("sum", "sum")).reset_index().sort_values("period")
            for _, row in ig.iterrows():
                internal_rows.append({
                    "Месяц": _month_label(row["period"]),
                    "Сумма": round(float(row["revenue"]), 2),
                    "Пометка": INTERNAL_CLIENT_TAG,
                })

    internal_total = sum(r["Сумма"] for r in internal_rows)

    period_start = str(df["date"].min().date()) if not df["date"].empty else ""
    period_end = str(df["date"].max().date()) if not df["date"].empty else ""

    summary = {
        "total_revenue": round(total, 2),
        "total_sales": total_sales,
        "avg_check": round(total / total_sales, 2) if total_sales else 0,
        "months_count": len(data),
        "period_start": period_start,
        "period_end": period_end,
        "best_month": best.get("month", ""),
        "best_revenue": round(best.get("revenue", 0), 2) if best else 0,
        "worst_month": worst.get("month", ""),
        "worst_revenue": round(worst.get("revenue", 0), 2) if worst else 0,
        "internal_total": round(internal_total, 2),
        "internal_count": len(internal_rows),
        "skipped_sources": [d["filename"] for d in debug_all if "error" in d],
        "debug": debug_all,
    }

    chart = {
        "labels": [d["month"] for d in data],
        "values": [d["revenue"] for d in data],
        "mom": [d["mom_pct"] if d["mom_pct"] is not None else 0 for d in data],
    }

    return {"summary": summary, "data": data, "chart": chart,
            "chart_warehouse": chart_warehouse,
            "by_warehouse": by_warehouse,
            "internal": internal_rows if internal_rows else [],
            "categories": categories,
            "cat_table": cat_table,
            "top_products": top_products}
