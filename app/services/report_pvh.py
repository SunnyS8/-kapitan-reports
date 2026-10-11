"""Отчёт: Плёнка ПВХ."""
import re
import pandas as pd
from pathlib import Path
from typing import Optional

from app.services.excel_parser import read_pvh_excel, _filter_by_date


def extract_width(product_name: str) -> Optional[float]:
    """Извлекает ширину из названия продукта (например, '1.5м' из '303IDE, 1.5м (100)')."""
    if not product_name:
        return None
    match = re.search(r"(\d+\.?\d*)м", str(product_name))
    if match:
        return float(match.group(1))
    return None


def generate_pvh(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """Отчёт по плёнке ПВХ: цены, количество, площади по сериям и ширинам."""
    if not filepaths:
        return {"summary": {}, "data": [], "chart": {}}

    frames = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_pvh_excel(fp)
            frames.append(df)
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if not frames:
        return {"summary": {"error": "Не удалось распарсить файлы", "debug": debug_all}, "data": [], "chart": {}}

    df = pd.concat(frames, ignore_index=True)
    df = _filter_by_date(df, date_from, date_to)

    if "series" not in df.columns:
        return {"summary": {"error": "Колонка 'Серия' не найдена", "debug": debug_all}, "data": [], "chart": {}}

    df["width"] = df["product"].apply(extract_width)

    summary = {
        "total_quantity": round(float(df["quantity"].sum()), 2) if "quantity" in df.columns else 0,
        "total_area": round(float(df["area"].sum()), 2) if "area" in df.columns else 0,
        "total_value": round(float(df["total"].sum()), 2) if "total" in df.columns else 0,
        "avg_price": round(float(df["price"].mean()), 2) if "price" in df.columns and len(df) else 0,
        "total_products": len(df),
        "series_count": df["series"].nunique() if "series" in df.columns else 0,
        "date_from": df["date"].min().strftime("%d.%m.%Y") if "date" in df.columns and not df["date"].isna().all() else "",
        "date_to": df["date"].max().strftime("%d.%m.%Y") if "date" in df.columns and not df["date"].isna().all() else "",
    }

    products = []
    for _, row in df.iterrows():
        item = {
            "series": str(row["series"]) if pd.notna(row.get("series")) else "",
            "product": str(row["product"]) if pd.notna(row.get("product")) else "",
            "width": float(row["width"]) if pd.notna(row.get("width")) else None,
            "price": round(float(row["price"]), 2) if pd.notna(row.get("price")) else 0,
            "quantity": int(row["quantity"]) if pd.notna(row.get("quantity")) else 0,
            "area": round(float(row["area"]), 2) if pd.notna(row.get("area")) else 0,
            "total": round(float(row["total"]), 2) if pd.notna(row.get("total")) else 0,
        }
        if "date" in df.columns and pd.notna(row.get("date")):
            item["date"] = row["date"].strftime("%d.%m.%Y")
        else:
            item["date"] = ""
        if "type" in df.columns and pd.notna(row.get("type")):
            item["type"] = str(row["type"])
        if "city" in df.columns and pd.notna(row.get("city")):
            item["city"] = str(row["city"])
        products.append(item)

    series_data = {}
    if "series" in df.columns and "total" in df.columns:
        for name, group in df.groupby("series", dropna=False):
            series_data[str(name)] = {
                "quantity": round(float(group["quantity"].sum()), 2),
                "area": round(float(group["area"].sum()), 2),
                "total": round(float(group["total"].sum()), 2),
                "count": len(group),
            }

    width_data = {}
    if "width" in df.columns and "total" in df.columns:
        for width, group in df.groupby("width", dropna=False):
            if pd.notna(width):
                w = float(width)
                width_data[str(w)] = {
                    "total": round(float(group["total"].sum()), 2),
                    "quantity": round(float(group["quantity"].sum()), 2),
                    "count": len(group),
                }

    chart = {
        "labels": list(series_data.keys()),
        "values": [v["total"] for v in series_data.values()],
        "series_data": series_data,
        "width_data": width_data,
    }

    return {
        "summary": summary,
        "data": products,
        "chart": chart,
    }
