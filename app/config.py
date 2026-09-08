from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
_default_data_path = "/app/data" if os.environ.get("RAILWAY_ENVIRONMENT") else str(BASE_DIR)
DATA_DIR = Path(os.environ.get("DATA_DIR", _default_data_path))
UPLOADS_DIR = DATA_DIR / "uploads"
REPORTS_DIR = DATA_DIR / "reports"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# --- База знаний ---
# Локально используется каталог базы знаний, а на Railway путь задаётся
# переменной BASE_KNOWLEDGE и должен указывать на Persistent Volume.
_default_knowledge_path = (
    str(DATA_DIR)
    if os.environ.get("RAILWAY_ENVIRONMENT")
    else r"C:\Users\User\Desktop\Моя база знаний"
)
_knowledge_path = os.environ.get("BASE_KNOWLEDGE", _default_knowledge_path)
BASE_KNOWLEDGE = Path(_knowledge_path)
KNOWLEDGE_ANALYTICS = BASE_KNOWLEDGE / "06 - Аналитика и отчёты"
KNOWLEDGE_MONTHLY = BASE_KNOWLEDGE / "07 - Ежемесячные отчёты"

for _d in (BASE_KNOWLEDGE, KNOWLEDGE_ANALYTICS, KNOWLEDGE_MONTHLY):
    _d.mkdir(parents=True, exist_ok=True)

# Папка входных выгрузок из 1С + справочники. На Railway она находится
# на Persistent Volume вместе с загруженными отчётами.
INBOX_DIR = DATA_DIR / "inbox"
REF_DIR = INBOX_DIR / "Справочники"

for _d in (INBOX_DIR, REF_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Куда писать результат по каждому типу отчёта (подпапка в 06 - Аналитика и отчёты)
REPORT_OUT_DIRS = {
    "sales_clients": "ABC анализ",
    "sales_products": "ABC анализ",
    "top_clients": "ABC анализ",
    "top_products": "ABC анализ",
    "sales_detailed": "ABC анализ",
    "sales_client_detail": "ABC анализ",
    "debt": "Дебиторка",
    "debt_manager": "Дебиторка",
    "nelikvid": "Неликвиды",
    "inventory": "Остатки по складам",
    "stock_dynamics": "Остатки по складам",
    "dynamics": "Динамика продаж",
    "forecast": "Динамика продаж",
    "clients": "Реестр клиентов",
    "edo": "ЭДО",
}

# Отчёты, которые дополнительно пишутся в 07 - Ежемесячные отчёты
MONTHLY_REPORTS = {
    "sales_clients",
    "sales_products",
    "top_clients",
    "top_products",
    "sales_detailed",
    "sales_client_detail",
    "debt",
    "debt_manager",
}

REPORT_TYPES = {
    "sales_clients": "Продажи по клиентам",
    "sales_products": "Продажи по товарам",
    "inventory": "Остатки на складах",
    "dynamics": "Динамика продаж",
    "forecast": "План vs Факт",
    "debt": "Неоплаченные счета",
    "debt_manager": "Задолженность клиента",
    "stock_dynamics": "Динамика по складу",
    "edo": "Незавершённые ЭДО",
    "clients": "Реестр клиентов",
    "nelikvid": "Неликвиды",
    "top_clients": "Топ клиенты в разрезе номенклатуры",
    "top_products": "Топ продаж по номенклатуре",
}

# Внутренние контрагенты (используются для НДС), не входят в общие продажи.
# Выводятся отдельной строкой с пометкой, в общих результатах не учитываются.
# Строго: «СТ СЛАВА ООО» и «ИДЕАЛ ООО».
INTERNAL_CLIENTS = {
    "ст слава ооо",
    "идеал ооо",
}

# Подпись, которой помечаются внутренние контрагенты в отчётах
INTERNAL_CLIENT_TAG = "ВНУТР (НДС)"

SCHEDULE_DEFAULTS = {
    "hour": 8,
    "minute": 0,
    "day_of_week": "mon-fri",
}
