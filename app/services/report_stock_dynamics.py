"""Отчёт: Динамика по складу (1.2)."""
import math
import pandas as pd
from pathlib import Path
from datetime import datetime


def _num(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def generate_stock_dynamics(filepaths: list[Path]) -> dict:
    """Динамика движения по складам: Город склада | Номенклатура | Начальный
    приход | Остатки на день выгрузки | Резерв (вариант А и Б)."""
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

    for col in ("start_balance", "end_balance", "income", "outcome", "reserve"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "product" in df.columns:
        mask = df["product"].astype(str).str.strip()
        df = df[~mask.isin(["", "nan", "None", "Итого", "Всего", "Итог", "Итого:"])]
        df.reset_index(drop=True, inplace=True)

    if "product" not in df.columns:
        return {"summary": {"error": "Колонка 'Номенклатура' не найдена", "debug": debug_all}, "data": [], "chart": {}}

    # Вариант А: склад/город на каждой строке (generic). Город берём из city, если есть.
    # Вариант Б: завод-ведомость, где склад в заголовках секций (даёт колонку warehouse).
    warehouse_col = "warehouse" if "warehouse" in df.columns else "city"
    if warehouse_col not in df.columns:
        df[warehouse_col] = "Все склады"

    df["loc"] = df[warehouse_col].fillna("Без склада").astype(str)

    agg = {"end_balance": ("end_balance", "sum")}
    if "start_balance" in df.columns:
        agg["start_balance"] = ("start_balance", "sum")
    if "income" in df.columns:
        agg["income"] = ("income", "sum")
    if "outcome" in df.columns:
        agg["outcome"] = ("outcome", "sum")
    if "reserve" in df.columns:
        agg["reserve"] = ("reserve", "sum")

    grouped = df.groupby(["loc", "product"], dropna=False).agg(**agg).reset_index()
    grouped = grouped.sort_values(["loc", "end_balance"], ascending=[True, False])

    data = []
    for _, row in grouped.iterrows():
        item = {
            "Город склада": str(row["loc"]),
            "Номенклатура": str(row["product"]) if pd.notna(row["product"]) else "Без названия",
            "Остаток": round(_num(row.get("end_balance", 0)), 2),
        }
        if "start_balance" in row.index:
            item["Начальный приход"] = round(_num(row.get("start_balance", 0)), 2)
        if "income" in row.index:
            item["Приход"] = round(_num(row.get("income", 0)), 2)
        if "outcome" in row.index:
            item["Расход"] = round(_num(row.get("outcome", 0)), 2)
        if "reserve" in row.index:
            item["Резерв"] = round(_num(row.get("reserve", 0)), 2)
        data.append(item)

    total_balance = sum(d["Остаток"] for d in data)
    total_reserve = sum(d.get("Резерв", 0) for d in data)

    summary = {
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "total_items": len(data),
        "total_balance": round(total_balance, 2),
        "total_reserve": round(total_reserve, 2),
        "debug": debug_all,
    }

    # Диаграмма: остатки по складам
    by_loc = df.groupby("loc")["end_balance"].sum().sort_values(ascending=False).head(12)
    chart = {
        "labels": [str(i) for i in by_loc.index],
        "values": [round(float(v), 2) for v in by_loc.values],
    }

    return {"summary": summary, "data": data, "chart": chart}