# Skill: Kapitan Reports — Отчёты для отдела продаж

## Цель
Веб-инструмент для отдела продаж: 7 типов отчётов с загрузкой Excel-файлов из 1С, визуализацией и экспортом.

## Запуск

```powershell
cd "C:\Users\User\Desktop\Моя база знаний\08 - 1С и проекты\kapitan-reports"
pip install -r requirements.txt
python run.py
```

Откройте http://localhost:8000

## Деплой на Railway

1. Подключите GitHub-репозиторий `SunnyS8/-kapitan-reports` в Railway и выберите Deploy.
2. В сервисе создайте **Volume** с mount path `/app/data`.
3. Добавьте переменные окружения `DATA_DIR=/app/data` и `BASE_KNOWLEDGE=/app/data`.
4. Railway использует `railway.toml` и запускает приложение через `uvicorn` на `$PORT`.

AI-режим через Hermes на Railway отключён, пока в контейнер не установлен Hermes и не задана переменная `HERMES_EXE`.

## Стек
- FastAPI + Jinja2 + Bootstrap-стили (custom CSS)
- openpyxl + pandas (парсинг Excel)
- Chart.js (графики в браузере)
- APScheduler (фоновые задачи)

## Структура

```
kapitan-reports/
├── app/
│   ├── main.py              # FastAPI приложение
│   ├── config.py            # Настройки (пути, типы отчётов)
│   ├── models.py            # Pydantic-модели
│   ├── services/
│   │   ├── excel_parser.py  # Универсальный парсер выгрузок 1С
│   │   ├── report_sales.py  # Продажи по клиентам
│   │   ├── report_products.py # ABC-анализ
│   │   ├── report_inventory.py # Остатки на складах
│   │   ├── report_dynamics.py # Динамика продаж
│   │   ├── report_forecast.py # План vs Факт
│   │   ├── report_debt.py   # Неоплаченные счета
│   │   ├── report_nelikvid.py # Неликвиды
│   │   └── excel_export.py  # Экспорт в Excel
│   ├── routers/
│   │   ├── pages.py         # HTML-страницы
│   │   ├── api.py           # REST API (POST /api/generate/{type})
│   │   └── upload.py        # Загрузка файлов
│   ├── templates/           # 9 HTML-шаблонов
│   └── static/style.css     # Стили
├── uploads/                 # Загруженные файлы
├── reports/                 # Сформированные отчёты (.xlsx)
├── requirements.txt
└── run.py                   # Точка входа
```

## 7 отчётов

| # | Тип | API | Описание |
|---|-----|-----|----------|
| 1 | `sales_clients` | `POST /api/generate/sales_clients` | Продажи по клиентам (выручка, средний чек) |
| 2 | `sales_products` | `POST /api/generate/sales_products` | ABC-анализ по товарам |
| 3 | `inventory` | `POST /api/generate/inventory` | Остатки на складах |
| 4 | `dynamics` | `POST /api/generate/dynamics` | Динамика (сравнение 2+ периодов) |
| 5 | `forecast` | `POST /api/generate/forecast` | План vs Факт |
| 6 | `debt` | `POST /api/generate/debt` | Неоплаченные счета (дебиторка) |
| 7 | `nelikvid` | `POST /api/generate/nelikvid` | Неликвиды (формула Ирины) |

## API

### Загрузка файлов
```
POST /upload/files
Content-Type: multipart/form-data
Body: files=<file1>&files=<file2>...
Response: {"files": [...], "count": 2}
```

### Генерация отчёта
```
POST /api/generate/{report_type}
Response: {
    "report_type": "...",
    "summary": {...},
    "data": [...],
    "chart": {...},
    "filename": "report_20260831.xlsx"
}
```

### Скачивание
```
GET /api/download/{filename}
Response: файл .xlsx
```

## Формула неликвидов
```
Сумма = Цена_за_м² × длина(м) × ширина(см) × кол-во_рулонов
```
Длина и ширина парсятся из характеристики: `"303-3, 1.4м (100)"` → 1.4, 100

## Парсер Excel
Универсальный парсер (`excel_parser.py`) автоматически определяет структуру выгрузки 1С:
- Ищет заголовки по ключевым словам (клиент, товар, сумма, склад и т.д.)
- Нормализует колонки
- Конвертирует числа

Поддерживаемые типы выгрузок:
- Продажи (клиент, товар, кол-во, сумма)
- Остатки (склад, товар, нач/кон остаток, приход/расход)
- Счета (клиент, номер, дата, сумма, просрочка)
- План продаж (клиент/товар, план, факт)
