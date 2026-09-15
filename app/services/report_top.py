"""Отчёты: Топ продаж по номенклатуре (3.1) и Топ клиенты в разрезе номенклатуры (3.2)."""
import pandas as pd
from typing import Optional
from pathlib import Path

from app.config import INTERNAL_CLIENT_TAG
from app.services.excel_parser import compute_date_period, _filter_by_date
from app.services.internal_clients import is_internal_client
from app.services.excel_parser import _add_date_to_data

TOP_N = 50


def _load_sales(filepaths: list[Path]) -> tuple[pd.DataFrame, list]:
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
        raise ValueError("Не удалось распарсить файлы продаж")

    df = pd.concat(frames, ignore_index=True)
    df = _filter_by_date(df, date_from, date_to)
    return df, debug_all


def _round(v) -> float:
    try:
        return round(float(v), 2)
    except Exception:
        return 0.0


def generate_top_products(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """3.1 Топ продаж по номенклатуре: Номенклатура | Количество | Сумма."""
    df, debug_all = _load_sales(filepaths)

    if "product" not in df.columns:
        return {"summary": {"error": "Колонка 'Номенклатура' не найдена", "debug": debug_all}, "data": [], "chart": {}}

    agg = {"sum": ("sum", "sum")}
    if "quantity" in df.columns:
        agg["quantity"] = ("quantity", "sum")
    if "quantity_m2" in df.columns:
        agg["quantity_m2"] = ("quantity_m2", "sum")

    grouped = df.groupby("product", dropna=False).agg(**agg).reset_index()
    grouped = grouped.sort_values("sum", ascending=False)

    total = float(grouped["sum"].sum())
    top = grouped.head(TOP_N).copy()

    # Territory and Manager mapping from df
    city_map = {}
    manager_map = {}
    if "city" in df.columns:
        city_map = df.groupby("product", dropna=False)["city"].agg(lambda x: next((v for v in x if pd.notna(v) and str(v).strip() and str(v).lower() not in ("nan", "none", "")), ""))
    if "manager" in df.columns:
        manager_map = df.groupby("product", dropna=False)["manager"].agg(lambda x: next((v for v in x if pd.notna(v) and str(v).strip() and str(v).lower() not in ("nan", "none", "")), ""))

    data = []
    for _, row in top.iterrows():
        item = {
            "Номенклатура": str(row["product"]) if pd.notna(row["product"]) else "Без названия",
            "Количество": int(row.get("quantity", 0)),
            "Сумма": _round(row["sum"]),
            "territory": str(city_map.get(row["product"], "")) if row["product"] in city_map.index else "",
            "manager": str(manager_map.get(row["product"], "")) if row["product"] in manager_map.index else "",
        }
        if "quantity_m2" in row.index:
            item["Количество м2"] = _round(row.get("quantity_m2", 0))
        data.append(item)

    period = compute_date_period(df)

    summary = {
        "generated_at": period["generated_at"],
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "total_revenue": _round(total),
        "total_products": len(grouped),
        "top_shown": len(data),
        "top_revenue_share": round(float(top["sum"].sum() / total * 100), 1) if total else 0,
        "debug": debug_all,
    }

    chart = {
        "labels": [d["Номенклатура"][:25] for d in data[:15]],
        "values": [d["Сумма"] for d in data[:15]],
    }

    _add_date_to_data(data, df)

    return {"summary": summary, "data": data, "chart": chart}


def generate_top_clients(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """3.2 Топ клиенты в разрезе номенклатуры: Клиент | Номенклатура | Шт/кв.м | Сумма.

    Внутренние контрагенты (для НДС) выводятся отдельной строкой с пометкой
    и не учитываются в общих результатах (общая выручка, топ, диаграмма).
    """
    df, debug_all = _load_sales(filepaths)

    period = compute_date_period(df)

    for col in ("client", "product", "sum"):
        if col not in df.columns:
            return {"summary": {"error": f"Колонка '{col}' не найдена", "debug": debug_all}, "data": [], "chart": {}}

    agg = {"sum": ("sum", "sum")}
    if "quantity" in df.columns:
        agg["quantity"] = ("quantity", "sum")
    if "quantity_m2" in df.columns:
        agg["quantity_m2"] = ("quantity_m2", "sum")

    df["is_internal"] = df["client"].map(is_internal_client)
    internal_df = df[df["is_internal"]]
    df = df[~df["is_internal"]].drop(columns=["is_internal"], errors="ignore")

    # Territory and Manager mapping from df for clients
    city_map = {}
    manager_map = {}
    if "city" in df.columns:
        city_map = df.groupby("client", dropna=False)["city"].agg(lambda x: next((v for v in x if pd.notna(v) and str(v).strip() and str(v).lower() not in ("nan", "none", "")), ""))
    if "manager" in df.columns:
        manager_map = df.groupby("client", dropna=False)["manager"].agg(lambda x: next((v for v in x if pd.notna(v) and str(v).strip() and str(v).lower() not in ("nan", "none", "")), ""))

    grouped = df.groupby(["client", "product"], dropna=False).agg(**agg).reset_index()
    grouped = grouped.sort_values("sum", ascending=False)

    total = float(grouped["sum"].sum())
    top = grouped.head(TOP_N).copy()

    data = []
    for _, row in top.iterrows():
        item = {
            "Клиент": str(row["client"]) if pd.notna(row["client"]) else "Без имени",
            "Номенклатура": str(row["product"]) if pd.notna(row["product"]) else "Без названия",
            "Шт": int(row.get("quantity", 0)),
            "Сумма": _round(row["sum"]),
            "territory": str(city_map.get(row["client"], "")) if row["client"] in city_map.index else "",
            "manager": str(manager_map.get(row["client"], "")) if row["client"] in manager_map.index else "",
        }
        if "quantity_m2" in row.index:
            item["Кв.м"] = _round(row.get("quantity_m2", 0))
        data.append(item)

    # Внутренние контрагенты — отдельным блоком с пометкой
    internal_rows = []
    if not internal_df.empty:
        ia = {"sum": ("sum", "sum")}
        if "quantity" in internal_df.columns:
            ia["quantity"] = ("quantity", "sum")
        if "quantity_m2" in internal_df.columns:
            ia["quantity_m2"] = ("quantity_m2", "sum")
        ig = internal_df.groupby(["client", "product"], dropna=False).agg(**ia).reset_index()
        ig = ig.sort_values("sum", ascending=False)
        for _, row in ig.iterrows():
            territory = str(city_map.get(row["client"], "")) if row["client"] in city_map.index else ""
            manager = str(manager_map.get(row["client"], "")) if row["client"] in manager_map.index else ""
            item = {
                "Клиент": str(row["client"]) if pd.notna(row["client"]) else "Без имени",
                "Номенклатура": str(row["product"]) if pd.notna(row["product"]) else "Без названия",
                "Шт": int(row.get("quantity", 0)),
                "Сумма": _round(row["sum"]),
                "territory": territory,
                "manager": manager,
                "Пометка": INTERNAL_CLIENT_TAG,
            }
            if "quantity_m2" in row.index:
                item["Кв.м"] = _round(row.get("quantity_m2", 0))
            internal_rows.append(item)

    summary = {
        "generated_at": period["generated_at"],
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "total_revenue": _round(total),
        "clients_in_report": int(df["client"].nunique()),
        "top_shown": len(data),
        "top_revenue_share": round(float(top["sum"].sum() / total * 100), 1) if total else 0,
        "internal_total": _round(float(internal_df["sum"].sum())) if not internal_df.empty else 0.0,
        "internal_count": int(internal_df["client"].nunique()) if not internal_df.empty else 0,
        "debug": debug_all,
    }

    chart = {
        "labels": [d["Клиент"][:25] for d in data[:15]],
        "values": [d["Сумма"] for d in data[:15]],
    }

    return {"summary": summary, "data": data, "chart": chart, "internal": internal_rows}
