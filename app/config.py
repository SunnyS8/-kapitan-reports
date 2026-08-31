from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"

UPLOADS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

REPORT_TYPES = {
    "sales_clients": "Продажи по клиентам",
    "sales_products": "Продажи по товарам",
    "inventory": "Остатки на складах",
    "dynamics": "Динамика продаж",
    "forecast": "План vs Факт",
    "debt": "Неоплаченные счета",
    "nelikvid": "Неликвиды",
}

SCHEDULE_DEFAULTS = {
    "hour": 8,
    "minute": 0,
    "day_of_week": "mon-fri",
}
