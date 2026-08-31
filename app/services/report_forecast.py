"""Отчёт: План vs Факт."""
import pandas as pd
from pathlib import Path


def generate_forecast(filepaths: list[Path]) -> dict:
    """
    Сравнение плана и факта продаж.
    """
    from app.services.excel_parser import read_plan_excel, read_sales_excel

    plan_df = None
    fact_df = None

    for fp in filepaths:
        try:
            df = read_plan_excel(fp)
            if "plan" in df.columns and plan_df is None:
                plan_df = df
            elif "fact" in df.columns and fact_df is None:
                fact_df = df
        except Exception:
            continue

    # Если нет отдельного плана, пробуем прочитать как продажи
    if plan_df is None and fact_df is None:
        for fp in filepaths:
            try:
                df = read_sales_excel(fp)
                if fact_df is None:
                    fact_df = df
            except Exception:
                continue

    if fact_df is None:
        return {"summary": {"error": "Нет данных о факте продаж"}, "data": [], "chart": {}}

    # Если плана нет — создаём заглушку
    if plan_df is None:
        plan_df = pd.DataFrame()

    data = []

    # Если есть план и факт по клиентам
    if "client" in fact_df.columns:
        fact_by_client = fact_df.groupby("client", dropna=False)["sum"].sum().reset_index() if "sum" in fact_df.columns else pd.DataFrame()

        if not plan_df.empty and "client" in plan_df.columns and "plan" in plan_df.columns:
            plan_by_client = plan_df.groupby("client", dropna=False)["plan"].sum().reset_index()
            merged = fact_by_client.merge(plan_by_client, on="client", how="outer").fillna(0)

            for _, row in merged.iterrows():
                client = str(row["client"]) if pd.notna(row["client"]) else "Без имени"
                plan_val = float(row.get("plan", 0))
                fact_val = float(row.get("sum", 0))
                pct = (fact_val / plan_val * 100) if plan_val else 0
                status = "ok" if pct >= 100 else "warn" if pct >= 70 else "danger"
                data.append({
                    "name": client,
                    "plan": round(plan_val, 2),
                    "fact": round(fact_val, 2),
                    "pct": round(pct, 1),
                    "status": status,
                })
        else:
            for _, row in fact_by_client.iterrows():
                data.append({
                    "name": str(row["client"]) if pd.notna(row["client"]) else "Без имени",
                    "plan": 0,
                    "fact": round(float(row.get("sum", 0)), 2),
                    "pct": 0,
                    "status": "no_plan",
                })

    total_plan = sum(d["plan"] for d in data)
    total_fact = sum(d["fact"] for d in data)
    total_pct = (total_fact / total_plan * 100) if total_plan else 0

    summary = {
        "total_plan": round(total_plan, 2),
        "total_fact": round(total_fact, 2),
        "total_pct": round(total_pct, 1),
        "items_count": len(data),
    }

    chart = {
        "labels": [d["name"][:20] for d in data[:10]],
        "plan": [d["plan"] for d in data[:10]],
        "fact": [d["fact"] for d in data[:10]],
    }

    return {"summary": summary, "data": data, "chart": chart}
