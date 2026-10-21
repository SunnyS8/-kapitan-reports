# -*- coding: utf-8 -*-
"""Дампит ответы API в site/api/ в сеансовом режиме:
для каждого типа отчёта в inbox кладутся только его выгрузки."""
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import httpx

BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
API = SITE / "api"
INBOX = ROOT / "inbox"
SOURCES = ROOT / "demo_sources"

(API / "generate").mkdir(parents=True, exist_ok=True)
(API / "analyze").mkdir(parents=True, exist_ok=True)

SALES = "Выгрузка продаж 2026.xlsx"
PLAN = "План продаж 2026.xlsx"
STOCK = "Остатки на 21.10.2026.xlsx"
INVOICES = "Счета покупателей.xlsx"
CLIENTS = "База клиентов.xlsx"
EDO = "Выгрузка ЭДО.xlsx"
PVH = "ПВХ дебиторка.xlsx"
NELIKVID = "Неликвид.xlsx"

# сеанс: набор файлов -> какие типы генерировать
SESSIONS = [
    ([SALES], ["sales_clients", "sales_products", "top_products", "top_clients", "dynamics"]),
    ([SALES, PLAN], ["forecast"]),
    ([STOCK], ["inventory", "stock_dynamics"]),
    ([STOCK, NELIKVID], ["nelikvid"]),
    ([INVOICES], ["debt", "debt_manager"]),
    ([CLIENTS], ["clients"]),
    ([EDO], ["edo"]),
    ([PVH], ["pvh"]),
]

# сохраняем исходники
SOURCES.mkdir(exist_ok=True)
for f in INBOX.glob("*.xlsx"):
    shutil.copy2(f, SOURCES / f.name)


def set_inbox(names):
    for f in INBOX.glob("*.xlsx"):
        f.unlink()
    for n in names:
        shutil.copy2(SOURCES / n, INBOX / n)


client = httpx.Client(base_url=BASE, timeout=180)

for names, types in SESSIONS:
    set_inbox(names)
    for t in types:
        try:
            r = client.post(f"/api/generate/{t}", json={})
            if r.status_code == 200:
                (API / "generate" / f"{t}.json").write_bytes(r.content)
                data = r.json()
                rows = len(data.get("data") or [])
                print(f"generate {t}: OK rows={rows} [{', '.join(names)}]")
            else:
                print(f"generate {t}: HTTP {r.status_code} {r.text[:150]}")
        except Exception as e:
            print(f"generate {t}: EXC {e}")
    for t in types:
        try:
            r = client.post(f"/api/analyze/{t}?mode=auto")
            if r.status_code == 200:
                (API / "analyze" / f"{t}.json").write_bytes(r.content)
        except Exception:
            pass

# восстанавливаем полный inbox и его список
set_inbox([SALES, PLAN, STOCK, INVOICES, CLIENTS, EDO, PVH, NELIKVID])
r = client.get("/api/inbox/files")
if r.status_code == 200:
    (API / "inbox.json").write_bytes(r.content)

print("DONE")
