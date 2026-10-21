# -*- coding: utf-8 -*-
"""Генератор демо-выгрузок 1С для inbox/ (фикстивные данные)."""
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

INBOX = Path(__file__).resolve().parent / "inbox"
INBOX.mkdir(exist_ok=True)

CLIENTS = [
    "ООО «Домашний уют»", "ООО «Строймир Юг»", "ИП Ковалёв А.А.",
    "ООО «Интерьер-Плюс»", "ТД «Ремстрой»", "ООО «Альтаир»",
    "ИП Мартынова Е.В.", "ООО «Гранд Потолки»", "ООО «Веста Строй»",
    "ИП Абрамов Д.С.", "ООО «Лига Отделки»", "ООО «Форма Пространства»",
    "ИП Ткаченко М.И.", "ООО «Северный Ветер»", "ООО «Дом Комфорт»",
    "ИП Гусева О.П.", "ООО «Мегастрой»", "ООО «ТехноДом»",
    "ИП Романенко С.В.", "ООО «Профиль-Юг»",
]
CITIES = ["Ростов-на-Дону", "Краснодар", "Ставрополь", "Волгоград", "Воронеж", "Москва", "Сочи", "Астрахань"]
MANAGERS = ["Смирнова А.", "Петров И.", "Кузнецова Л.", "Орлов Д.", "Фёдорова Н.", "Гаврилов К."]
WAREHOUSES = ["Основной склад", "Склад Ростов", "Склад Краснодар"]

# (категория, товар, характеристика, цена)
PRODUCTS = [
    ("Потолочные панели", "Панель ПВХ Глянец 250х2700 Белый", "Белый глянец", 465),
    ("Потолочные панели", "Панель ПВХ Матовая 250х2700 Шампань", "Шампань матовая", 445),
    ("Потолочные панели", "Панель ПВХ Мозаика 250х2700 Серая", "Серая мозаика", 520),
    ("Потолочные панели", "Панель ПВХ Глянец 250х2700 Золото", "Золото глянец", 490),
    ("Плинтус", "Плинтус потолочный П-14 Белый", "Белый", 128),
    ("Плинтус", "Плинтус потолочный П-14 Шампань", "Шампань", 138),
    ("Светильники", "Светильник LED 12Вт круглый белый", "Круглый 12Вт", 720),
    ("Светильники", "Светильник LED 18Вт квадратный", "Квадратный 18Вт", 980),
    ("Фурнитура", "Соединитель угловой", "Универсальный", 55),
    ("Фурнитура", "Уголок наружный", "Белый", 48),
    ("Молдинги", "Молдинг потолочный декоративный", "303-3, 1.4м (100)", 210),
    ("Молдинги", "Фриз декоративный ПВХ", "2.7м (120)", 185),
]

START = date(2025, 10, 1)
END = date(2026, 10, 20)
DAYS = (END - START).days

# ---------- 1. Продажи ----------
rows = []
for _ in range(850):
    d = START + timedelta(days=random.randint(0, DAYS))
    cat, prod, char, price = random.choice(PRODUCTS)
    qty = random.randint(1, 45)
    rows.append({
        "Дата": d.strftime("%d.%m.%Y"),
        "Партнёр": random.choice(CLIENTS),
        "Город": random.choice(CITIES),
        "Менеджер": random.choice(MANAGERS),
        "Вид номенклатуры": cat,
        "Номенклатура": prod,
        "Характеристика": char,
        "Склад": random.choice(WAREHOUSES),
        "Кол-во": qty,
        "Цена": price,
        "Сумма выручки": round(qty * price, 2),
    })
df = pd.DataFrame(rows).sort_values("Дата")
df.to_excel(INBOX / "Выгрузка продаж 2026.xlsx", index=False)
print("sales:", len(df))

# ---------- 2. План продаж (для План vs Факт) ----------
plan_rows = []
months = [(2025, m) for m in range(10, 13)] + [(2026, m) for m in range(1, 13)]
for y, m in months:
    for cat, prod, char, price in PRODUCTS[:8]:
        plan_rows.append({
            "Дата": date(y, m, 1).strftime("%d.%m.%Y"),
            "Клиент": random.choice(CLIENTS),
            "Город": random.choice(CITIES),
            "Менеджер": random.choice(MANAGERS),
            "Номенклатура": prod,
            "Количество": random.randint(60, 260),
            "Сумма плана": round(random.randint(60, 260) * price, 2),
        })
pd.DataFrame(plan_rows).to_excel(INBOX / "План продаж 2026.xlsx", index=False)
print("plan:", len(plan_rows))

# ---------- 3. Остатки (generic-формат) ----------
stock_rows = []
for wh in WAREHOUSES:
    for cat, prod, char, price in PRODUCTS:
        start_q = random.randint(5, 120)
        inc = random.randint(0, 200)
        out = random.randint(0, min(start_q + inc, 180))
        stock_rows.append({
            "Дата": "21.10.2026",
            "Склад": wh,
            "Номенклатура": prod,
            "Характеристика": char,
            "Нач.остаток": start_q,
            "Приход": inc,
            "Расход": out,
            "Кон.остаток": start_q + inc - out,
            "Цена": price,
        })
pd.DataFrame(stock_rows).to_excel(INBOX / "Остатки на 21.10.2026.xlsx", index=False)
print("stock:", len(stock_rows))

# ---------- 4. Счета (задолженность) ----------
inv_rows = []
for i in range(48):
    d = START + timedelta(days=random.randint(0, DAYS))
    total = round(random.uniform(15000, 480000), 2)
    paid = round(total * random.choice([0, 0.3, 0.5, 0.8, 1.0]), 2)
    debt = round(total - paid, 2)
    # раскладываем долг по ведрам старения
    buckets = [0.0] * 6
    rest = debt
    edges = [10, 30, 60, 90, 180, 4000]
    for b in range(6):
        if rest <= 0:
            break
        take = round(rest * random.uniform(0.2, 0.8), 2) if b < 5 else rest
        buckets[b] = min(take, rest)
        rest = round(rest - buckets[b], 2)
    inv_rows.append({
        "Дата": d.strftime("%d.%m.%Y"),
        "Номер": f"РН-{10000 + i}",
        "Контрагент": random.choice(CLIENTS),
        "Сумма документа": total,
        "Оплачено": paid,
        "Долг": debt,
        "От 1 до 10 дней": buckets[0],
        "От 11 до 30 дней": buckets[1],
        "От 31 до 60 дней": buckets[2],
        "От 61 до 90 дней": buckets[3],
        "От 91 до 180 дней": buckets[4],
        "Более 180 дней": buckets[5],
    })
pd.DataFrame(inv_rows).to_excel(INBOX / "Счета покупателей.xlsx", index=False)
print("invoices:", len(inv_rows))

# ---------- 5. База клиентов ----------
cli_rows = []
for c in CLIENTS:
    cli_rows.append({
        "Клиент": c,
        "Телефон": f"8(863){random.randint(200, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
        "Город": random.choice(CITIES),
        "Почта": f"info{random.randint(1, 99)}@example.ru",
        "Последняя активность": (END - timedelta(days=random.randint(0, 340))).strftime("%d.%m.%Y"),
        "Менеджер": random.choice(MANAGERS),
    })
pd.DataFrame(cli_rows).to_excel(INBOX / "База клиентов.xlsx", index=False)
print("clients:", len(cli_rows))

# ---------- 6. ЭДО ----------
states = ["Актуальные (Отпечатанные)", "Актуальные (Отпечатанные)", "Реализация (не актуальные)",
          "Печать", "Стоп-лист", "Отклонён"]
edo_rows = []
for i in range(60):
    d = END - timedelta(days=random.randint(0, 120))
    edo_rows.append({
        "Контрагент": random.choice(CLIENTS),
        "Накладная": f"ЭДО-{20000 + i}",
        "Сумма документа": round(random.uniform(20000, 350000), 2),
        "Состояние": random.choice(states),
        "Дата": d.strftime("%d.%m.%Y"),
    })
pd.DataFrame(edo_rows).to_excel(INBOX / "Выгрузка ЭДО.xlsx", index=False)
print("edo:", len(edo_rows))

# ---------- 7. ПВХ (дебиторка) — позиционный формат выгрузки ----------
# read_pvh_excel ждёт: строки 0-3 шапка, строка 4 заголовки, 5+ данные;
# колонки по позициям: 0 код, 3 тип, 4 дата, 5 город, 6 статус, 7 серия,
# 9 номенклатура, 10 описание, 11 цена, 12 кол-во, 13 площадь, 14 сумма
pvh_header = [
    ["Период:", "01.10.2025 — 21.10.2026"],
    ["Отчёт:", "Дебиторка по ПВХ"],
    ["Организация:", "Торговый дом (демо)"],
    [],
]
pvh_cols = ["Код", "Категория", "Ед.изм.", "Тип", "Дата", "Город", "Состояние",
            "Серия", "Скидка", "Номенклатура", "Описание", "Цена", "Количество",
            "Площадь, м²", "Сумма"]
pvh_rows = [pvh_header + [pvh_cols]]
for i in range(55):
    cat, prod, char, price = random.choice(PRODUCTS)
    qty = random.randint(1, 40)
    paid = i % 3 != 0
    pvh_rows.append([
        f"ПВХ-{30000 + i}",   # 0 код
        "",                   # 1 (свободная)
        "",                   # 2 (свободная)
        "Реализация",         # 3 тип
        (END - timedelta(days=random.randint(0, 300))).strftime("%d.%m.%Y"),  # 4 дата
        random.choice(CITIES),  # 5 город
        "Оплачено" if paid else "Не оплачено",  # 6 статус
        "IDEAL",              # 7 серия
        "",                   # 8 (свободная)
        prod,                 # 9 номенклатура
        char,                 # 10 описание
        price,                # 11 цена
        qty,                  # 12 количество
        round(qty * 1.5, 2),  # 13 площадь
        round(qty * price, 2),  # 14 сумма
    ])
df_pvh = pd.DataFrame(pvh_rows)
df_pvh.to_excel(INBOX / "ПВХ дебиторка.xlsx", index=False, header=False)
print("pvh:", len(pvh_rows) - 1)

# ---------- 8. Неликвид (список, без заголовка) ----------
nl = pd.DataFrame([(prod, char) for cat, prod, char, price in random.sample(PRODUCTS, 8)]
                  + [("Панель ПВХ Глянец 250х2700 Зелёный", "Зелёный глянец"),
                     ("Плинтус потолочный П-14 Серый", "Серый"),
                     ("Молдинг потолочный ПВХ кручёный", "Кручёный (80)"),
                     ("Светильник LED 9Вт круглый", "Круглый 9Вт"),
                     ("Панель ПВХ Реечная 100х4000", "Рейка белая"),
                     ("Уголок потолочный", "Универсальный"),
                     ("Соединитель прямой", "Прямой"),
                     ("Фриз ПВХ узорчатый", "Узор (90)")])
nl.to_excel(INBOX / "Неликвид.xlsx", index=False, header=False)
print("nelikvid list:", len(nl))

print("DONE ->", INBOX)
