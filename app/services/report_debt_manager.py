"""Отчёт: Задолженность клиента по менеджерам с бакетами (4.1)."""
import math
import pandas as pd
from typing import Optional
from pathlib import Path
from datetime import datetime


def _num(v, default: float = 0.0) -> float:
    """Безопасное число: NaN -> default."""
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def generate_debt_manager(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """Задолженность по менеджерам/клиентам.
    Формат «как у Сергея»: Менеджер | Клиент | Организация | Отсрочка |
    Общий долг | Долг 1-10 | 11-15 | 16-29 | свыше 30."""
    from app.services.excel_parser import read_invoice_excel, _filter_by_date

    frames = []
    debug_all = []
    for fp in filepaths:
        try:
            df, debug = read_invoice_excel(fp)
            frames.append(df)
            debug_all.append(debug)
        except Exception as e:
            debug_all.append({"filename": fp.name, "error": str(e)})
            continue

    if not frames:
        return {"summary": {"error": "Не удалось распарсить файлы", "debug": debug_all}, "data": [], "chart": {}}

    df = pd.concat(frames, ignore_index=True)
    df = _filter_by_date(df, date_from, date_to)
    now = datetime.now()

    if "date" in df.columns and "debt_total" not in df.columns:
        days = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
        if df.get("deferral") is not None:
            df["overdue_days"] = df["deferral"].fillna(0).astype(float)
            has_deferral = True
        else:
            df["overdue_days"] = (now - days).dt.days.fillna(0)
            has_deferral = False
    elif "debt_total" not in df.columns:
        df["debt_total"] = df.get("sum", 0)
        has_deferral = df.get("deferral") is not None
        if has_deferral:
            df["overdue_days"] = df["deferral"].fillna(0).astype(float)
        else:
            df["overdue_days"] = 0
    else:
        has_deferral = df.get("deferral") is not None
        if has_deferral:
            df["overdue_days"] = df["deferral"].fillna(0).astype(float)

    def _bucket_total(row):
        return (_num(row.get("debt_bucket_1_10", 0)) +
                _num(row.get("debt_bucket_11_15", 0)) +
                _num(row.get("debt_bucket_16_29", 0)) +
                _num(row.get("debt_bucket_over_30", 0)))

    has_buckets = any(
        c in df.columns for c in ("debt_bucket_1_10", "debt_bucket_11_15",
                                  "debt_bucket_16_29", "debt_bucket_over_30"))

    data = []
    for _, row in df.iterrows():
        client = str(row.get("client", "")) if pd.notna(row.get("client")) else "Без имени"
        if has_buckets:
            total = _bucket_total(row)
        else:
            total = _num(row.get("debt_total", row.get("sum", 0)))
        data.append({
            "Менеджер": str(row.get("manager", "")) if pd.notna(row.get("manager", None)) else "",
            "Клиент": client,
            "Организация": str(row.get("organization", "")) if pd.notna(row.get("organization", None)) else "",
            "Отсрочка, дн": round(_num(row.get("deferral", 0)), 0) if pd.notna(row.get("deferral", None)) else 0,
            "Общий долг": round(total, 2),
            "Долг 1-10": round(_num(row.get("debt_bucket_1_10", 0)), 2),
            "Долг 11-15": round(_num(row.get("debt_bucket_11_15", 0)), 2),
            "Долг 16-29": round(_num(row.get("debt_bucket_16_29", 0)), 2),
            "Долг свыше 30": round(_num(row.get("debt_bucket_over_30", 0)), 2),
            "territory": str(row.get("city", "")) if "city" in df.columns else "",
        })

    data.sort(key=lambda x: x["Общий долг"], reverse=True)

    total_debt = sum(d["Общий долг"] for d in data)
    b1 = sum(d["Долг 1-10"] for d in data)
    b2 = sum(d["Долг 11-15"] for d in data)
    b3 = sum(d["Долг 16-29"] for d in data)
    b4 = sum(d["Долг свыше 30"] for d in data)

    summary = {
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "total_debt": round(total_debt, 2),
        "bucket_1_10": round(b1, 2),
        "bucket_11_15": round(b2, 2),
        "bucket_16_29": round(b3, 2),
        "bucket_over_30": round(b4, 2),
        "clients": len(data),
        "debug": debug_all,
    }

    chart = {
        "labels": ["1-10 дн", "11-15 дн", "16-29 дн", "свыше 30"],
        "values": [round(b1, 2), round(b2, 2), round(b3, 2), round(b4, 2)],
    }

    _add_date_to_data(data, df)

    return {"summary": summary, "data": data, "chart": chart}