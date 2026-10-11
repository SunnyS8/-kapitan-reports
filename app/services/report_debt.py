"""Отчёт: Неоплаченные счета (дебиторка)."""
import pandas as pd
from typing import Optional
from pathlib import Path
from datetime import datetime


def generate_debt(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
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

    if "date" in df.columns and "overdue_days" not in df.columns:
        df["overdue_days"] = df["date"].apply(lambda x: (now - x).days if pd.notna(x) else 0)
    elif "overdue_days" not in df.columns:
        df["overdue_days"] = 0

    data = []
    for _, row in df.iterrows():
        client = str(row.get("client", "")) if pd.notna(row.get("client")) else "Без имени"
        invoice = str(row.get("invoice_number", "")) if pd.notna(row.get("invoice_number")) else ""
        date_val = row.get("date")
        date_str = date_val.strftime("%d.%m.%Y") if pd.notna(date_val) and hasattr(date_val, "strftime") else str(date_val) if pd.notna(date_val) else ""
        sum_val = float(row.get("sum", 0)) if pd.notna(row.get("sum")) else 0
        days = int(row.get("overdue_days", 0)) if pd.notna(row.get("overdue_days")) else 0
        status = "danger" if days > 180 else "warn" if days > 90 else "ok"
        data.append({"client": client, "invoice_number": invoice, "date": date_str, "sum": round(sum_val, 2), "overdue_days": days, "status": status, "territory": str(row.get("city", "")) if "city" in df.columns else "", "manager": str(row.get("manager", "")) if "manager" in df.columns else ""})

    data.sort(key=lambda x: x["overdue_days"], reverse=True)

    total_sum = sum(d["sum"] for d in data)
    overdue_sum = sum(d["sum"] for d in data if d["overdue_days"] > 90)

    summary = {"total_sum": round(total_sum, 2), "overdue_sum": round(overdue_sum, 2), "total_invoices": len(data), "overdue_count": sum(1 for d in data if d["overdue_days"] > 90), "debug": debug_all}

    categories = {"0-30": 0, "31-90": 0, "91-180": 0, ">180": 0}
    for d in data:
        days = d["overdue_days"]
        if days <= 30:
            categories["0-30"] += d["sum"]
        elif days <= 90:
            categories["31-90"] += d["sum"]
        elif days <= 180:
            categories["91-180"] += d["sum"]
        else:
            categories[">180"] += d["sum"]

    chart = {"labels": list(categories.keys()), "values": [round(v, 2) for v in categories.values()]}
    _add_date_to_data(data, df)

    return {"summary": summary, "data": data, "chart": chart}
