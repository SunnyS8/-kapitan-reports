"""
Универсальный парсер выгрузок из 1С.
Поддерживает разные форматы: продажи, остатки, счета.
Автопоиск заголовков по ключевым словам + fallback на первую строку.
"""
import pandas as pd
import re
from pathlib import Path
from typing import Optional


class ParseError(Exception):
    pass


HEADER_KEYWORDS = {
    "client": ["клиент", "покупатель", "контрагент", "договор", "partner"],
    "product": ["номенклатура", "товар", "позиция", "артикул", "наименование", "номенклатур"],
    "warehouse": ["склад", "место хранения"],
    "quantity": ["кол-во", "количество", "колво", "шт", "объём", "объем"],
    "sum": ["сумма", "выручка", "итого", "стоимость", "сумм"],
    "price": ["цена", "стоимость за"],
    "date": ["дата", "период", "месяц"],
    "start_balance": ["нач.остаток", "начальный остаток", "нач остаток"],
    "income": ["приход", "поступление"],
    "outcome": ["расход", "продажи", "отгрузка"],
    "end_balance": ["кон.остаток", "конечный остаток", "кон остаток"],
    "invoice": ["счёт", "счет", "номер счёта", "номер счета"],
    "plan": ["план"],
    "fact": ["факт"],
}


def _find_header_row(df: pd.DataFrame) -> Optional[int]:
    """Ищет строку-заголовок: ищет строку, где хотя бы 2 колонки содержат ключевые слова."""
    all_kws = []
    for kws in HEADER_KEYWORDS.values():
        all_kws.extend(kws)

    for idx in range(min(30, len(df))):
        row_vals = [str(v).lower() for v in df.iloc[idx].values if pd.notna(v)]
        row_text = " ".join(row_vals)
        matches = sum(1 for kw in all_kws if kw.lower() in row_text)
        if matches >= 2:
            return idx

    # Fallback: ищем строку где много текстовых не-пустых значений (похоже на заголовки)
    for idx in range(min(10, len(df))):
        non_empty = sum(1 for v in df.iloc[idx].values if pd.notna(v) and str(v).strip())
        if non_empty >= 3:
            vals = [str(v).lower() for v in df.iloc[idx].values if pd.notna(v)]
            has_number = any(re.search(r'\d', v) for v in vals)
            has_text = any(len(v) > 2 and not re.search(r'^\d+[.,]?\d*$', v) for v in vals)
            if has_text and not has_number:
                return idx

    return None


def _map_columns(df: pd.DataFrame, target_map: dict) -> dict[str, str]:
    """
    Маппинг колонок df -> целевые имена.
    target_map = {"client": ["клиент", "покупатель"], "product": ["товар", ...]}
    """
    col_map = {}
    used_targets = set()

    for col in df.columns:
        c = str(col).strip().lower() if pd.notna(col) else ""
        if not c:
            continue

        for target, keywords in target_map.items():
            if target in used_targets:
                continue
            if any(kw in c for kw in keywords):
                col_map[col] = target
                used_targets.add(target)
                break

    return col_map


def _smart_read(filepath: Path) -> pd.DataFrame:
    """Читает Excel с автопоиском заголовков."""
    try:
        df_raw = pd.read_excel(filepath, header=None, engine="openpyxl")
    except Exception as e:
        raise ParseError(f"Не удалось прочитать {filepath.name}: {e}")

    if df_raw.empty:
        raise ParseError(f"Файл {filepath.name} пуст")

    header_row = _find_header_row(df_raw)

    if header_row is not None:
        headers = []
        for i in range(len(df_raw.columns)):
            val = df_raw.iloc[header_row, i]
            if pd.isna(val) or str(val).strip() == "":
                headers.append(f"col_{i}")
            else:
                headers.append(str(val).strip())

        df = df_raw.iloc[header_row + 1:].copy()
        df.columns = headers
        df.reset_index(drop=True, inplace=True)
        # Убираем полностью пустые строки
        df = df.dropna(how="all")
        return df
    else:
        # Fallback: первая строка как заголовки
        df = df_raw.copy()
        headers = []
        for i in range(len(df.columns)):
            val = df.iloc[0, i] if len(df) > 0 else f"col_{i}"
            if pd.isna(val) or str(val).strip() == "":
                headers.append(f"col_{i}")
            else:
                headers.append(str(val).strip())
        df.columns = headers
        df = df.iloc[1:].copy()
        df.reset_index(drop=True, inplace=True)
        df = df.dropna(how="all")
        return df


def _debug_columns(df: pd.DataFrame) -> list[dict]:
    """Возвращает информацию о колонках для отладки."""
    info = []
    for col in df.columns:
        non_null = df[col].notna().sum()
        sample = ""
        for v in df[col].head(3):
            if pd.notna(v) and str(v).strip():
                sample = str(v)[:50]
                break
        info.append({"name": str(col), "non_null": int(non_null), "sample": sample})
    return info


def read_sales_excel(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """
    Чтение выгрузки продаж из 1С.
    Возвращает (DataFrame, debug_info).
    """
    df = _smart_read(filepath)

    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, {
        "client": ["клиент", "покупатель", "контрагент", "договор", "partner"],
        "product": ["номенклатура", "товар", "наименование", "артикул", "номенклатур"],
        "quantity": ["кол-во", "количество", "колво", "шт", "объём", "объем"],
        "sum": ["сумма", "выручка", "стоимость", "сумм"],
        "price": ["цена", "стоимость за"],
        "date": ["дата", "период", "месяц"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    for num_col in ["quantity", "sum", "price"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    return df, debug


def read_stock_excel(filepath: Path) -> tuple[pd.DataFrame, dict]:
    df = _smart_read(filepath)
    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, {
        "warehouse": ["склад"],
        "product": ["номенклатура", "товар", "наименование"],
        "start_balance": ["нач.остаток", "начальный остаток", "нач остаток"],
        "income": ["приход", "поступление"],
        "outcome": ["расход", "продажи"],
        "end_balance": ["кон.остаток", "конечный остаток", "кон остаток"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    for num_col in ["start_balance", "income", "outcome", "end_balance"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    return df, debug


def read_invoice_excel(filepath: Path) -> tuple[pd.DataFrame, dict]:
    df = _smart_read(filepath)
    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, {
        "client": ["клиент", "покупатель", "контрагент"],
        "invoice_number": ["счёт", "счет", "номер"],
        "date": ["дата"],
        "sum": ["сумма"],
        "overdue_days": ["дней", "просроч"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    for num_col in ["sum", "overdue_days"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df, debug


def read_plan_excel(filepath: Path) -> tuple[pd.DataFrame, dict]:
    df = _smart_read(filepath)
    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, {
        "client": ["клиент", "покупатель"],
        "product": ["номенклатура", "товар"],
        "plan": ["план"],
        "fact": ["факт"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    for num_col in ["plan", "fact"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    return df, debug
