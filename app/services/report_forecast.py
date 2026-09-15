"""Отчёт: План vs Факт."""
import pandas as pd
from typing import Optional
from pathlib import Path

from app.services.internal_clients import is_internal_client
from app.config import INTERNAL_CLIENT_TAG


def generate_forecast(filepaths: list[Path], date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    from app.services.excel_parser import read_plan_excel, read_sales_excel, _filter_by_date

    plan_df = None
    fact_df = None
    debug_all = []

    for fp in filepaths:
        try:
            df, debug = read_plan_excel(fp)
            debug_all.append(debug)
            if "plan" in df.columns and plan_df is None:
                plan_df = df
            elif "fact" in df.columns and fact_df is None:
                fact_df = df
            elif fact_df is None:
                fact_df = df
        except Exception:
            try:
                df, debug = read_sales_excel(fp)
                debug_all.append(debug)
                if fact_df is None:
                    fact_df = df
            except Exception as e:
                debug_all.append({"filename": fp.name, "error": str(e)})

    if fact_df is None:
        return {"summary": {"error": "Нет данных о факте продаж", "debug": debug_all}, "data": [], "chart": {}}

    # Territory and Manager mapping from fact_df
    city_map = {}
    manager_map = {}
    if "city" in fact_df.columns:
        city_map = fact_df.groupby("client", dropna=False)["city"].agg(lambda x: next((v for v in x if pd.notna(v) and str(v).strip() and str(v).lower() not in ("nan", "none", "")), ""))
    if "manager" in fact_df.columns:
        manager_map = fact_df.groupby("client", dropna=False)["manager"].agg(lambda x: next((v for v in x if pd.notna(v) and str(v).strip() and str(v).lower() not in ("nan", "none", "")), ""))

    # Внутренние контрагенты (для НДС) — отдельным блоком, из факта исключаются.
    internal_rows = []
    if "client" in fact_df.columns and "sum" in fact_df.columns:
        fact_df["is_internal"] = fact_df["client"].map(is_internal_client)
        internal_df = fact_df[fact_df["is_internal"]]
        fact_df = fact_df[~fact_df["is_internal"]].drop(columns=["is_internal"], errors="ignore")
        if not internal_df.empty:
            ig = internal_df.groupby("client", dropna=False)["sum"].sum().reset_index()
            ig = ig.sort_values("sum", ascending=False)
            for _, row in ig.iterrows():
                territory = str(city_map.get(row["client"], "")) if row["client"] in city_map.index else ""
                manager = str(manager_map.get(row["client"], "")) if row["client"] in manager_map.index else ""
                internal_rows.append({
                    "Клиент": str(row["client"]) if pd.notna(row["client"]) else "Без имени",
                    "Факт": round(float(row["sum"]), 2),
                    "Пометка": INTERNAL_CLIENT_TAG,
                    "territory": territory,
                    "manager": manager,
                })

    data = []

    if "client" in fact_df.columns and "sum" in fact_df.columns:
        fact_by_client = fact_df.groupby("client", dropna=False)["sum"].sum().reset_index()

        if plan_df is not None and not plan_df.empty and "client" in plan_df.columns and "plan" in plan_df.columns:
            plan_by_client = plan_df.groupby("client", dropna=False)["plan"].sum().reset_index()
            merged = fact_by_client.merge(plan_by_client, on="client", how="outer").fillna(0)

            for _, row in merged.iterrows():
                client = str(row["client"]) if pd.notna(row["client"]) else "Без имени"
                plan_val = float(row.get("plan", 0))
                fact_val = float(row.get("sum", 0))
                pct = (fact_val / plan_val * 100) if plan_val else 0
                status = "ok" if pct >= 100 else "warn" if pct >= 70 else "danger"
                territory = str(city_map.get(row["client"], "")) if row["client"] in city_map.index else ""
                manager = str(manager_map.get(row["client"], "")) if row["client"] in manager_map.index else ""
                data.append({"name": client, "plan": round(plan_val, 2), "fact": round(fact_val, 2), "pct": round(pct, 1), "status": status, "territory": territory, "manager": manager})
        else:
            for _, row in fact_by_client.iterrows():
                territory = str(city_map.get(row["client"], "")) if row["client"] in city_map.index else ""
                manager = str(manager_map.get(row["client"], "")) if row["client"] in manager_map.index else ""
                data.append({"name": str(row["client"]) if pd.notna(row["client"]) else "Без имени", "plan": 0, "fact": round(float(row.get("sum", 0)), 2), "pct": 0, "status": "no_plan", "territory": territory, "manager": manager})

    total_plan = sum(d["plan"] for d in data)
    total_fact = sum(d["fact"] for d in data)
    total_pct = (total_fact / total_plan * 100) if total_plan else 0

    summary = {"total_plan": round(total_plan, 2), "total_fact": round(total_fact, 2), "total_pct": round(total_pct, 1), "items_count": len(data), "internal_total": round(float(sum(r["Факт"] for r in internal_rows)), 2), "internal_count": len(internal_rows), "debug": debug_all}
    chart = {"labels": [d["name"][:20] for d in data[:10]], "plan": [d["plan"] for d in data[:10]], "fact": [d["fact"] for d in data[:10]]}

    return {"summary": summary, "data": data, "chart": chart,
            "internal": internal_rows if internal_rows else []}
