"""Отчёт: Динамика по складу (1.2) — подробная версия.

Структура:
  - сводка по складам (склад | нач.остаток | приход | расход | кон.остаток | резерв);
  - динамика остатков по периодам (по каждой выгрузке): остаток на конец периода
    по складу, приход/расход за период;
  - детализация по номенклатуре: артикул, характеристика, ширина (тип), м2;
  - исключение дублей: несколько файлов за один и тот же период — берём один,
    с наибольшей детализацией (приоритет файлу с колонкой м2).
"""
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


def _pick_period_file(groups: list[tuple[list[tuple[pd.DataFrame, dict]], str]]) -> list[tuple[pd.DataFrame, dict, str, str]]:
    """Для каждого периода оставляет один файл (с максимальной детализацией)."""
    picked = []
    for frames, period in groups:
        if not frames:
            continue
        best = frames[0][0]
        best_debug = frames[0][1]
        best_score = _detail_score(best, best_debug)
        for df, debug in frames[1:]:
            score = _detail_score(df, debug)
            if score > best_score:
                best, best_debug, best_score = df, debug, score
        flag = "dedup" if len(frames) > 1 else "single"
        picked.append((best, best_debug, period, flag))
    # порядок по возрастанию периода (по дате из первого совпадения)
    picked.sort(key=lambda t: _period_start_sort(t[2]))
    return picked


def _detail_score(df: pd.DataFrame, debug: dict) -> int:
    score = 0
    if "end_balance_m2" in df.columns:
        score += 10
    if "width" in df.columns and df["width"].astype(str).str.strip().ne("").sum():
        score += 5
    if "article" in df.columns and df["article"].astype(str).str.strip().ne("").sum():
        score += 3
    if "reserve" in df.columns:
        score += 2
    score += df.shape[0] / 1000.0  # чуть выше — у файла с большим числом строк
    return score


def _period_start_sort(period: str) -> tuple:
    """Сортирует периоды по начальной дате (формат 'ДД.ММ.ГГГГ - ДД.ММ.ГГГГ')."""
    try:
        start = period.split("-")[0].strip()
        dt = datetime.strptime(start, "%d.%m.%Y")
        return (dt.year, dt.month, dt.day)
    except Exception:
        return (9999, 12, 31)


def generate_stock_dynamics(filepaths: list[Path]) -> dict:
    """Динамика движения по складам: сводка по складам, по периодам, детали."""
    from app.services.excel_parser import read_stock_excel

    file_frames: list[tuple[pd.DataFrame, dict]] = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_stock_excel(fp)
            file_frames.append((df, debug))
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if not file_frames:
        return {"summary": {"error": "Не удалось распарсить файлы", "debug": debug_all}, "data": [], "chart": {}}

    # Группируем файлы по периоду (период из шапки выгрузки или из имени файла)
    by_period: dict[str, list[tuple[pd.DataFrame, dict]]] = {}
    for df, debug in file_frames:
        period = (debug.get("period") or "").strip()
        if not period:
            period = _period_from_filename(Path(debug["filename"]).name)
        by_period.setdefault(period, []).append((df, debug))

    periods_meta: list[dict] = []
    picked_frames = []
    dropped_info = []
    for df, debug, period, flag in _pick_period_file([(frames, p) for p, frames in by_period.items()]):
        df = df.copy()
        df["period"] = period
        picked_frames.append((df, debug))
        if flag == "dedup":
            others = [dbg.get("filename") for _, dbg in by_period.get(period, []) if dbg.get("filename") != debug.get("filename")]
            dropped_info.append({"period": period, "kept": debug.get("filename"), "dropped": others})
        periods_meta.append({
            "period": period,
            "file": debug.get("filename", ""),
            "format": debug.get("format", ""),
            "rows": int(debug.get("rows", 0)),
        })

    if not picked_frames:
        return {"summary": {"error": "Не удалось распарсить файлы", "debug": debug_all}, "data": [], "chart": {}}

    df = pd.concat([f for f, _ in picked_frames], ignore_index=True)

    for col in ("start_balance", "end_balance", "income", "outcome", "reserve", "end_balance_m2"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "article" not in df.columns:
        df["article"] = ""
    if "characteristic" not in df.columns:
        df["characteristic"] = ""
    if "width" not in df.columns:
        df["width"] = ""
    if "end_balance_m2" not in df.columns:
        df["end_balance_m2"] = 0.0

    if "product" in df.columns:
        mask = df["product"].astype(str).str.strip()
        df = df[~mask.isin(["", "nan", "None", "Итого", "Всего", "Итог", "Итого:"])]
        df.reset_index(drop=True, inplace=True)

    if "product" not in df.columns:
        return {"summary": {"error": "Колонка 'Номенклатура' не найдена", "debug": debug_all}, "data": [], "chart": {}}

    warehouse_col = "warehouse" if "warehouse" in df.columns else "city"
    if warehouse_col not in df.columns:
        df[warehouse_col] = "Все склады"

    df["loc"] = df[warehouse_col].fillna("Без склада").astype(str)

    # --- Сводка по складам: итоги по всем периодам за конец последнего периода ---
    num_cols = ["end_balance"]
    if "start_balance" in df.columns:
        num_cols.append("start_balance")
    if "income" in df.columns:
        num_cols.append("income")
    if "outcome" in df.columns:
        num_cols.append("outcome")
    if "reserve" in df.columns:
        num_cols.append("reserve")

    # Остатки по периодам: остаток на конец периода по каждому складу
    period_series = df.groupby(["period", "loc"])[["end_balance"]].sum().reset_index()

    # Сводка по складам — используем последний период как «текущий» остаток,
    # приход/расход суммируем по всем выбранным периодам.
    if periods_meta:
        last_period = periods_meta[-1]["period"]
    else:
        last_period = ""
    last_period_df = df[df["period"] == last_period] if last_period else df

    loc_agg = {"end_balance": ("end_balance", "sum")}
    if "start_balance" in df.columns:
        loc_agg["start_balance"] = ("start_balance", "sum")
    if "income" in df.columns:
        loc_agg["income"] = ("income", "sum")
    if "outcome" in df.columns:
        loc_agg["outcome"] = ("outcome", "sum")
    if "reserve" in df.columns:
        loc_agg["reserve"] = ("reserve", "sum")
    loc_agg["items"] = ("product", "nunique")

    # Сводка: остатки на конец последнего периода, движение — сумма за все периоды
    summary_by_loc = last_period_df.groupby("loc").agg(**loc_agg).reset_index()

    warehouses = []
    for _, row in summary_by_loc.iterrows():
        d = {
            "Город склада": str(row["loc"]),
            "Начальный приход": round(_num(row.get("start_balance", 0)), 2),
            "Приход": round(_num(row.get("income", 0)), 2),
            "Расход": round(_num(row.get("outcome", 0)), 2),
            "Остаток": round(_num(row.get("end_balance", 0)), 2),
            "Позиций": int(row.get("items", 0)),
        }
        if "reserve" in row.index:
            d["Резерв"] = round(_num(row.get("reserve", 0)), 2)
        warehouses.append(d)
    warehouses.sort(key=lambda x: x["Остаток"], reverse=True)

    total_balance = sum(d["Остаток"] for d in warehouses)
    total_reserve = sum(d.get("Резерв", 0) for d in warehouses)
    total_items = sum(d["Позиций"] for d in warehouses)

    # --- Детализация по номенклатуре ---
    group_cols = ["period", "loc", "product"]
    agg_detail = {
        "end_balance": ("end_balance", "sum"),
        "income": ("income", "sum"),
        "outcome": ("outcome", "sum"),
        "start_balance": ("start_balance", "sum"),
    }
    if "reserve" in df.columns:
        agg_detail["reserve"] = ("reserve", "sum")
    agg_detail["end_balance_m2"] = ("end_balance_m2", "sum")
    agg_detail["article"] = ("article", "first")
    agg_detail["characteristic"] = ("characteristic", "first")
    agg_detail["width"] = ("width", "first")
    if "manager" in df.columns:
        agg_detail["manager"] = ("manager", "first")

    detail = df.groupby(group_cols, dropna=False).agg(**agg_detail).reset_index()
    detail = detail.sort_values(["period", "loc", "end_balance"], ascending=[True, True, False])

    data = []
    for _, row in detail.iterrows():
        item = {
            "Период": str(row["period"]) if row["period"] else "—",
            "Город склада": str(row["loc"]),
            "Менеджер": str(row["manager"]) if "manager" in row.index and pd.notna(row.get("manager", "")) else "",
            "Номенклатура": str(row["product"]) if pd.notna(row["product"]) else "Без названия",
            "Артикул": str(row.get("article", "")) if pd.notna(row.get("article", "")) else "",
            "Характеристика": str(row.get("characteristic", "")) if pd.notna(row.get("characteristic", "")) else "",
            "Ширина": str(row.get("width", "")) if pd.notna(row.get("width", "")) else "",
            "Начальный приход": round(_num(row.get("start_balance", 0)), 2),
            "Приход": round(_num(row.get("income", 0)), 2),
            "Расход": round(_num(row.get("outcome", 0)), 2),
            "Остаток": round(_num(row.get("end_balance", 0)), 2),
            "Резерв": round(_num(row.get("reserve", 0)), 2),
            "Остаток м2": round(_num(row.get("end_balance_m2", 0)), 2),
        }
        data.append(item)

    # Динамика: остаток на конец периода по каждому складу (для линейного графика)
    series_labels = []
    for pm in periods_meta:
        if pm["period"] not in series_labels:
            series_labels.append(pm["period"])

    all_locs = sorted({d["Город склада"] for d in warehouses})
    series_map = {}
    for _, r in period_series.iterrows():
        series_map.setdefault(str(r["loc"]), {})[str(r["period"])] = round(float(r["end_balance"]), 2)

    # Если период один — столбчатая диаграмма по складам, иначе — линии по периодам
    if len(series_labels) <= 1:
        chart = {
            "type": "bar",
            "labels": warehouses and [d["Город склада"] for d in warehouses],
            "values": [d["Остаток"] for d in warehouses],
            "unit": "Остаток",
        }
    else:
        chart = {
            "type": "line",
            "labels": series_labels,
            "datasets": [
                {"label": loc, "values": [series_map.get(loc, {}).get(p, 0) for p in series_labels]}
                for loc in all_locs
            ],
            "unit": "Остаток",
        }

    summary = {
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "total_items": total_items,
        "total_balance": round(total_balance, 2),
        "total_reserve": round(total_reserve, 2),
        "periods": series_labels,
        "files": periods_meta,
        "dedup": dropped_info,
        "debug": debug_all,
    }

    return {"summary": summary, "warehouses": warehouses, "data": data, "chart": chart}


def _period_from_filename(name: str) -> str:
    """Пытается извлечь период из имени файла («…01.08-31.08…» → период)."""
    import re
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})", name)
    if m:
        return f"{m.group(1)} - {m.group(2)}"
    return name