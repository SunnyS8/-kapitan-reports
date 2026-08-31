"""
Универсальный парсер выгрузок из 1С.
Поддерживает разные форматы: продажи, остатки, счета.
Автопоиск заголовков по ключевым словам.
"""
import pandas as pd
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


class ParseError(Exception):
    pass


@dataclass
class ParsedData:
    """Результат парсинга одного Excel-файла."""
    filename: str
    raw: pd.DataFrame
    headers: dict[int, str] = field(default_factory=dict)
    data_rows: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    meta: dict = field(default_factory=dict)


# Ключевые слова для автопоиска заголовков
HEADER_KEYWORDS = {
    "client": ["клиент", "покупатель", "контрагент", "договор"],
    "product": ["номенклатура", "товар", "позиция", "артикул", "наименование"],
    "warehouse": ["склад", "место хранения"],
    "quantity": ["кол-во", "количество", "колво", "шт"],
    "sum": ["сумма", "выручка", "итого", "стоимость"],
    "price": ["цена", "цена за", " стоимость за"],
    "date": ["дата", "период", "месяц"],
    "start_balance": ["нач.остаток", "начальный остаток", "нач остаток"],
    "income": ["приход", "поступление"],
    "outcome": ["расход", "продажи", "отгрузка"],
    "end_balance": ["кон.остаток", "конечный остаток", "кон остаток"],
    "invoice": ["счёт", "счет", "номер счёта", "номер счета"],
    "plan": ["план", "план продаж"],
    "fact": ["факт", "факт продаж"],
    "days": ["дней", "дней без продаж", "дата последней продажи"],
}


def find_header_row(df: pd.DataFrame, required_keywords: list[str]) -> Optional[int]:
    """Ищет строку-заголовок по ключевым словам."""
    for idx in range(min(20, len(df))):
        row_text = " ".join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        matches = sum(1 for kw in required_keywords if kw.lower() in row_text)
        if matches >= 2:
            return idx
    return None


def normalize_col(name: str) -> str:
    """Нормализует имя колонки."""
    if pd.isna(name):
        return ""
    s = str(name).strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s


def detect_columns(df: pd.DataFrame) -> dict[str, Optional[int]]:
    """Автоопределение колонок по ключевым словам."""
    mapping = {}
    for col_idx in range(len(df.columns)):
        val = str(df.iloc[0, col_idx]).lower() if len(df) > 0 else ""
        for key, keywords in HEADER_KEYWORDS.items():
            if any(kw in val for kw in keywords):
                if key not in mapping:
                    mapping[key] = col_idx
    return mapping


def read_excel_auto(filepath: Path) -> ParsedData:
    """
    Универсальное чтение Excel-файла из 1С.
    Автоматически определяет структуру и извлекает данные.
    """
    try:
        df_raw = pd.read_excel(filepath, header=None, engine="openpyxl")
    except Exception as e:
        raise ParseError(f"Не удалось прочитать {filepath.name}: {e}")

    if df_raw.empty:
        raise ParseError(f"Файл {filepath.name} пуст")

    result = ParsedData(filename=filepath.name, raw=df_raw)

    # Поиск заголовков
    all_keywords = []
    for kws in HEADER_KEYWORDS.values():
        all_keywords.extend(kws)

    header_row = find_header_row(df_raw, all_keywords)

    if header_row is not None:
        result.headers = {i: str(df_raw.iloc[header_row, i]) for i in range(len(df_raw.columns))
                          if pd.notna(df_raw.iloc[header_row, i])}
        result.data_rows = df_raw.iloc[header_row + 1:].copy()
        result.data_rows.columns = df_raw.iloc[header_row].values
        result.data_rows.reset_index(drop=True, inplace=True)
    else:
        result.data_rows = df_raw.copy()

    return result


def read_sales_excel(filepath: Path) -> pd.DataFrame:
    """
    Чтение выгрузки продаж из 1С.
    Ожидаемые колонки: Клиент, Товар, Количество, Сумма, Дата (произвольный порядок).
    """
    parsed = read_excel_auto(filepath)
    df = parsed.data_rows.copy()

    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    # Нормализация колонок
    col_map = {}
    for col in df.columns:
        c = normalize_col(col)
        if any(kw in c for kw in ["клиент", "покупатель", "контрагент"]):
            col_map[col] = "client"
        elif any(kw in c for kw in ["номенклатура", "товар", "наименование", "артикул"]):
            col_map[col] = "product"
        elif any(kw in c for kw in ["кол-во", "количество", "колво", "шт"]):
            col_map[col] = "quantity"
        elif any(kw in c for kw in ["сумма", "выручка", "стоимость"]):
            col_map[col] = "sum"
        elif any(kw in c for kw in ["цена"]):
            col_map[col] = "price"
        elif any(kw in c for kw in ["дата", "период"]):
            col_map[col] = "date"

    df = df.rename(columns=col_map)

    # Числовые колонки
    for num_col in ["quantity", "sum", "price"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    return df


def read_stock_excel(filepath: Path) -> pd.DataFrame:
    """
    Чтение выгрузки остатков из 1С.
    Ожидаемые колонки: Склад, Номенклатура, Нач.остаток, Приход, Расход, Кон.остаток.
    """
    parsed = read_excel_auto(filepath)
    df = parsed.data_rows.copy()

    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    col_map = {}
    for col in df.columns:
        c = normalize_col(col)
        if any(kw in c for kw in ["склад"]):
            col_map[col] = "warehouse"
        elif any(kw in c for kw in ["номенклатура", "товар", "наименование"]):
            col_map[col] = "product"
        elif any(kw in c for kw in ["нач.остаток", "начальный остаток", "нач остаток"]):
            col_map[col] = "start_balance"
        elif any(kw in c for kw in ["приход", "поступление"]):
            col_map[col] = "income"
        elif any(kw in c for kw in ["расход", "продажи"]):
            col_map[col] = "outcome"
        elif any(kw in c for kw in ["кон.остаток", "конечный остаток", "кон остаток"]):
            col_map[col] = "end_balance"

    df = df.rename(columns=col_map)

    for num_col in ["start_balance", "income", "outcome", "end_balance"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    return df


def read_invoice_excel(filepath: Path) -> pd.DataFrame:
    """
    Чтение выгрузки счетов/дебиторки из 1С.
    Ожидаемые колонки: Клиент, Номер счёта, Дата, Сумма, Дней просрочки.
    """
    parsed = read_excel_auto(filepath)
    df = parsed.data_rows.copy()

    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    col_map = {}
    for col in df.columns:
        c = normalize_col(col)
        if any(kw in c for kw in ["клиент", "покупатель", "контрагент"]):
            col_map[col] = "client"
        elif any(kw in c for kw in ["счёт", "счет", "номер"]):
            col_map[col] = "invoice_number"
        elif any(kw in c for kw in ["дата"]):
            col_map[col] = "date"
        elif any(kw in c for kw in ["сумма"]):
            col_map[col] = "sum"
        elif any(kw in c for kw in ["дней", "просроч"]):
            col_map[col] = "overdue_days"

    df = df.rename(columns=col_map)

    for num_col in ["sum", "overdue_days"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


def read_plan_excel(filepath: Path) -> pd.DataFrame:
    """Чтение плана продаж."""
    parsed = read_excel_auto(filepath)
    df = parsed.data_rows.copy()

    col_map = {}
    for col in df.columns:
        c = normalize_col(col)
        if any(kw in c for kw in ["клиент", "покупатель"]):
            col_map[col] = "client"
        elif any(kw in c for kw in ["номенклатура", "товар"]):
            col_map[col] = "product"
        elif any(kw in c for kw in ["план"]):
            col_map[col] = "plan"
        elif any(kw in c for kw in ["факт"]):
            col_map[col] = "fact"

    df = df.rename(columns=col_map)

    for num_col in ["plan", "fact"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    return df
