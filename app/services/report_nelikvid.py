"""Отчёт: Неликвиды (по формуле Ирины)."""
import pandas as pd
import re
from pathlib import Path


def parse_length_width(characteristic: str) -> tuple[float, float]:
    """
    Парсинг длины и ширины из строки характеристики.
    Пример: "303-3, 1.4м (100)" -> (1.4, 100)
    """
    if not characteristic or pd.isna(characteristic):
        return 0.0, 0.0
    match = re.search(r'(\d+[.,]?\d*)\s*м\s*\((\d+)\)', str(characteristic))
    if match:
        length = float(match.group(1).replace(',', '.'))
        width = float(match.group(2))
        return length, width
    return 0.0, 0.0


def normalize(text: str) -> str:
    """Нормализация текста для сравнения."""
    if not text or pd.isna(text):
        return ""
    return str(text).strip().lower()


def generate_nelikvid(filepaths: list[Path], threshold_days: int = 180) -> dict:
    """
    Отчёт по неликвидам.
    Формула: Сумма = Цена_за_м² × длина(м) × ширина(см) × кол-во_рулонов
    """
    if not filepaths:
        return {"summary": {}, "data": [], "chart": {}}

    # Читаем все файлы
    nelikvid_list = None
    stock_df = None
    prices_df = None

    for fp in filepaths:
        try:
            df = pd.read_excel(fp, header=None, engine="openpyxl")
            if df.empty:
                continue

            # Определяем тип файла по содержимому
            first_rows = " ".join(str(v).lower() for v in df.iloc[0].values if pd.notna(v))

            if "склад" in first_rows or "остаток" in first_rows:
                stock_df = df
            elif "цена" in first_rows:
                prices_df = df
            elif len(df.columns) <= 3 and len(df) > 10:
                # Список неликвидов (2 колонки: наименование, бренд)
                nelikvid_list = df
        except Exception:
            continue

    data = []

    # Если есть файл неликвидов и остатков — работаем по формуле Ирины
    if nelikvid_list is not None and stock_df is not None:
        # Список неликвидов
        nl_names = set()
        for _, row in nelikvid_list.iterrows():
            name = normalize(row.iloc[0]) if len(row) > 0 else ""
            if name:
                nl_names.add(name)

        # Цены
        price_map = {}
        if prices_df is not None:
            for _, row in prices_df.iterrows():
                if len(row) >= 4:
                    name = normalize(row.iloc[2]) if pd.notna(row.iloc[2]) else ""
                    char = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ""
                    price = float(row.iloc[9]) if len(row) > 9 and pd.notna(row.iloc[9]) else 0
                    key = f"{name}|{char}"
                    price_map[key] = price

        # Парсинг остатков
        try:
            from app.services.excel_parser import find_header_row, HEADER_KEYWORDS
            all_kws = []
            for kws in HEADER_KEYWORDS.values():
                all_kws.extend(kws)
            header_row = find_header_row(stock_df, all_kws)

            if header_row is not None:
                headers = [str(stock_df.iloc[header_row, i]) for i in range(len(stock_df.columns))]
                data_rows = stock_df.iloc[header_row + 1:]
            else:
                headers = [str(stock_df.iloc[0, i]) for i in range(len(stock_df.columns))]
                data_rows = stock_df.iloc[1:]

            current_warehouse = ""
            current_clean = ""

            for _, row in data_rows.iterrows():
                c1 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                c4 = str(row.iloc[3]) if len(row) > 3 and pd.notna(row.iloc[3]) else ""

                # Определение склада
                if any(kw in c1.lower() for kw in ["склад", "серпухов", "ставрополь", "набережные"]):
                    current_warehouse = c1
                    continue

                # Очистка
                if any(kw in c1.lower() for kw in ["номенклатура", "итого", "тип ширины", "на склад"]):
                    continue

                # Характеристика найдена — это детальная строка
                if c4 and c1:
                    clean_n = normalize(c1)
                    length, width = parse_length_width(c4)

                    # Остатки
                    end_balance = 0
                    if len(row) > 8 and pd.notna(row.iloc[8]):
                        try:
                            end_balance = float(row.iloc[8])
                        except (ValueError, TypeError):
                            pass

                    # Цена
                    price_key = f"{clean_n}|{c4}"
                    price = price_map.get(price_key, 0)

                    # Сумма по формуле Ирины
                    sum_val = price * length * width * end_balance if end_balance > 0 else 0

                    # Категория по дням (упрощённо — без даты последней продажи)
                    category = "Без данных"

                    data.append({
                        "product": c1,
                        "characteristic": c4,
                        "warehouse": current_warehouse,
                        "end_balance": round(end_balance, 0),
                        "price_per_m2": round(price, 2),
                        "length": length,
                        "width": width,
                        "sum": round(sum_val, 2),
                        "category": category,
                        "territory": str(row.get("city", "")) if "city" in stock_df.columns else "",
                    })
        except Exception:
            pass
    else:
        # Упрощённый режим — просто читаем что есть
        for fp in filepaths:
            try:
                df = pd.read_excel(fp, header=0, engine="openpyxl")
                for _, row in df.iterrows():
                    item = {}
                    for col in df.columns:
                        val = row[col]
                        if pd.isna(val):
                            item[str(col)] = ""
                        elif isinstance(val, (int, float)):
                            item[str(col)] = round(float(val), 2)
                        else:
                            item[str(col)] = str(val)
                    item["territory"] = str(row.get("city", "")) if "city" in df.columns else ""
                    data.append(item)
            except Exception:
                continue

    # Summary
    total_sum = sum(d.get("sum", 0) for d in data)
    total_items = len(data)

    category_sums = {}
    for d in data:
        cat = d.get("category", "Без данных")
        category_sums[cat] = category_sums.get(cat, 0) + d.get("sum", 0)

    warehouse_sums = {}
    for d in data:
        wh = d.get("warehouse", "")
        warehouse_sums[wh] = warehouse_sums.get(wh, 0) + d.get("sum", 0)

    summary = {
        "total_items": total_items,
        "total_sum": round(total_sum, 2),
        "categories": category_sums,
        "warehouses": warehouse_sums,
    }

    chart_category = {
        "labels": list(category_sums.keys()),
        "values": [round(v, 2) for v in category_sums.values()],
    }

    chart_warehouse = {
        "labels": list(warehouse_sums.keys()),
        "values": [round(v, 2) for v in warehouse_sums.values()],
    }

    return {"summary": summary, "data": data, "chart_category": chart_category, "chart_warehouse": chart_warehouse}
