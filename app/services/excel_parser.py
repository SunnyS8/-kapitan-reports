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
    "client": ["клиент", "покупатель", "контрагент", "договор", "партнер", "партнёр"],
    "contractor": ["контрагент"],
    "manager": ["менеджер", "основной менеджер", "ответственный"],
    "organization": ["организация"],
    "product": ["номенклатура", "товар", "позиция", "артикул", "наименование"],
    "category": ["категория", "вид номенклатуры", "вид", "номенклатура.вид", "номенклатура.вид "],
    "warehouse": ["склад", "место хранения"],
    "city": ["город", "бизнес-регион", "бизнес регион", "регион"],
    "address": ["адрес"],
    "phone": ["телефон"],
    "payer": ["плательщик"],
    "invoice_number": ["накладная", "накладн", "номер накладн", "номер"],
    "state": ["состояние"],
    "stopped": ["остановлен"],
    "quantity": ["кол-во", "количество", "колво", "шт", "объём", "объем", "количество м2", "количество м²", "кол-во,шт", "кол-во шт"],
    "quantity_m2": ["количество м2", "количество м²", "метраж", "кв.м", "кв. м", "м2", "м²"],
    "sum": ["сумма выручки", "выручка", "сумма", "итого", "стоимость"],
    "price": ["цена", "стоимость за"],
    "date": ["дата", "период", "месяц"],
    "period": ["период", "месяц", "неделя"],
    "deferral": ["отсрочка", "дней отсрочки", "отсрочк"],
    "start_balance": ["нач.остаток", "начальный остаток", "нач остаток", "начальный приход"],
    "income": ["приход", "поступление"],
    "outcome": ["расход", "продажи", "отгрузка"],
    "end_balance": ["кон.остаток", "конечный остаток", "кон остаток", "остаток на день"],
    "reserve": ["резерв", "зарезервировано", "зарезервир"],
    "characteristic": ["характеристика", "цвет", "ширина", "фактура"],
    "debt_total": ["долг клиента", "общий долг", "задолженность", "всего", "долг"],
    "debt_deferral_days": ["дней отсрочки", "отсрочка"],
    "debt_bucket_1_10": ["от 1 до 10"],
    "debt_bucket_11_15": ["от 11 до 15"],
    "debt_bucket_16_29": ["от 16 до 29"],
    "debt_bucket_over_30": ["свыше 30", "от 30", "свыше 30 дней"],
    "invoice": ["счёт", "счет", "номер счёта", "номер счета"],
    "plan": ["план"],
    "fact": ["факт"],
}


def _is_filter_row(df: pd.DataFrame, idx: int) -> bool:
    """Проверяет, является ли строка строкой-фильтром (Отбор: ...)."""
    first_val = str(df.iloc[idx, 0]).lower() if pd.notna(df.iloc[idx, 0]) else ""
    return "отбор" in first_val or "фильтр" in first_val or "условие" in first_val


def _find_header_row(df: pd.DataFrame) -> Optional[int]:
    """Ищет строку-заголовок: пропускает фильтры, ищет строку с ключевыми словами.

    Из строк с >=2 совпадениями выбирает ту, у которой совпадений БОЛЬШЕ ВСЕГО —
    реальный заголовок данных (например «Артикул | Номенклатура, Характеристика |
    Ед.изм. | Нач.остаток | Приход | Расход | Кон.остаток») обычно содержит больше
    ключевых слов, чем промежуточная шапка («Склад | Количество»).
    """
    all_kws = []
    for kws in HEADER_KEYWORDS.values():
        all_kws.extend(kws)

    best_idx = None
    best_score = 0
    for idx in range(min(30, len(df))):
        if _is_filter_row(df, idx):
            continue
        row_vals = [str(v).lower() for v in df.iloc[idx].values if pd.notna(v)]
        row_text = " ".join(row_vals)
        matches = sum(1 for kw in all_kws if kw.lower() in row_text)
        if matches >= 2 and matches > best_score:
            best_score = matches
            best_idx = idx

    if best_idx is not None:
        return best_idx

    # Fallback: первая не-фильтровая строка с 3+ текстовыми значениями
    for idx in range(min(15, len(df))):
        if _is_filter_row(df, idx):
            continue
        non_empty = sum(1 for v in df.iloc[idx].values if pd.notna(v) and str(v).strip())
        if non_empty >= 3:
            vals = [str(v).strip() for v in df.iloc[idx].values if pd.notna(v) and str(v).strip()]
            has_number = any(re.search(r'^\d+[.,]?\d*$', v) for v in vals)
            if not has_number:
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
        seen = set()
        for i in range(len(df_raw.columns)):
            val = df_raw.iloc[header_row, i]
            if pd.isna(val) or str(val).strip() == "":
                name = f"col_{i}"
            else:
                name = str(val).strip()
            # Дедупликация
            if name in seen:
                name = f"{name}_{i}"
            seen.add(name)
            headers.append(name)

        df = df_raw.iloc[header_row + 1:].copy()
        df.columns = headers
        df.reset_index(drop=True, inplace=True)
        df = df.dropna(how="all")
        return df
    else:
        df = df_raw.copy()
        headers = []
        seen = set()
        for i in range(len(df.columns)):
            val = df.iloc[0, i] if len(df) > 0 else f"col_{i}"
            if pd.isna(val) or str(val).strip() == "":
                name = f"col_{i}"
            else:
                name = str(val).strip()
            if name in seen:
                name = f"{name}_{i}"
            seen.add(name)
            headers.append(name)
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
    Чтение выгрузки продаж из 1С (развёрнутый отчёт по продажам).
    Возвращает (DataFrame, debug_info).
    """
    df = _smart_read(filepath)

    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, SALES_COLUMN_MAP)

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    for num_col in ["quantity", "quantity_m2", "sum", "price", "weight"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    if "date" in df.columns:
        # Даты в выгрузках 1С в формате «день.месяц.год» (например 01.08.2026).
        # dayfirst=True, чтобы 01.08.2026 читалось как 1 августа, а не 8 января.
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

    # Убираем итоговые строки отчёта: строки без номенклатуры (сводные «Итого»/«Всего»)
    # с агрегированной суммой, которые не являются позициями продаж.
    if "product" in df.columns:
        mask = df["product"].astype(str).str.strip()
        df = df[~mask.isin(["", "nan", "None", "Итого", "Всего", "Итог", "Итого:"])]
        df.reset_index(drop=True, inplace=True)

    return df, debug


SALES_COLUMN_MAP = {
    # Порядок важен: «Вид номенклатуры» должен попасть в category раньше, чем
    # «Номенклатура» в product (иначе col «Вид номенклатуры» перехватывает product).
    "category": ["вид номенклатуры", "категория"],
    "product": ["номенклатура", "товар", "наименование", "артикул"],
    "client": ["партнёр", "партнер", "клиент", "покупатель", "контрагент", "договор", "partner"],
    "city": ["бизнес-регион", "бизнес регион", "регион", "город"],
    "warehouse": ["склад", "место хранения"],
    "characteristic": ["характеристика", "цвет", "ширина", "фактура"],
    "manager": ["менеджер", "подразделение", "ответственный", "основной менеджер"],
    "organization": ["организация"],
    "address": ["адрес"],
    "quantity_m2": ["количество м2", "количество м²", "метраж", "кв.м", "кв. м", "м2", "м²"],
    "quantity": ["кол-во", "количество", "колво", "объём", "объем"],
    "weight": ["вес"],
    "sum": ["сумма выручки", "выручка", "сумма", "стоимость"],
    "price": ["цена", "стоимость за"],
    "date": ["дата", "месяц", "период"],
}


def compute_date_period(df: pd.DataFrame) -> dict:
    """Считает период отчёта по колонке дат и дату формирования.

    Возвращает:
      generated_at  — дата/время формирования отчёта (строка DD.MM.YYYY HH:MM)
      period_start  — минимальная дата продаж (DD.MM.YYYY) или ""
      period_end    — максимальная дата продаж (DD.MM.YYYY) или ""
    """
    from datetime import datetime

    out = {"generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")}

    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce", dayfirst=True).dropna()
        if not dates.empty:
            out["period_start"] = dates.min().strftime("%d.%m.%Y")
            out["period_end"] = dates.max().strftime("%d.%m.%Y")
        else:
            out["period_start"] = ""
            out["period_end"] = ""
    else:
        out["period_start"] = ""
        out["period_end"] = ""

    return out


def read_stock_excel(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """Читает остатки по складам, автоматически определяя формат:
    - «Ведомость по товарам на складах» (склад в заголовках секций, forward-fill)
    - «Остатки с себестоимостью по складам» (иерархия склады/типы ширины)
    - generic-формат (колонка «Склад» на каждой строке)
    """
    fmt = _detect_stock_format(filepath)
    if fmt == "vedomost":
        return _read_stock_vedomost(filepath)
    if fmt == "sebestoimost":
        return _read_stock_sebestoimost(filepath)
    # generic path
    df = _smart_read(filepath)
    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, {
        "warehouse": ["склад"],
        "product": ["номенклатура", "товар", "наименование"],
        "characteristic": ["характеристика", "цвет", "ширина", "фактура"],
        "start_balance": ["нач.остаток", "начальный остаток", "нач остаток"],
        "income": ["приход", "поступление"],
        "outcome": ["расход", "продажи"],
        "end_balance": ["кон.остаток", "конечный остаток", "кон остаток"],
        "reserve": ["резерв", "зарезервировано"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    for num_col in ["start_balance", "income", "outcome", "end_balance", "reserve"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    # Если отдельной колонки «Характеристика» нет, но есть объединённая колонка
    # вида «Номенклатура, Характеристика, Серия», пытаемся разбить её.
    if "characteristic" not in df.columns and "product" in df.columns:
        _split_product_characteristic(df)

    # Убираем итоговые строки по складу: строка без товара, но с каким-либо остатком
    if "product" in df.columns:
        mask = df["product"].astype(str).str.strip()
        df = df[~mask.isin(["", "nan", "None", "Итого", "Всего", "Итог"])]
        df.reset_index(drop=True, inplace=True)

    return df, debug


# --- Специализированные парсеры для поскладских форматов 1С ---

_SKIP_COL0_TOKENS = {
    "склад", "артикул", "номенклатура", "характеристика", "серия", "тип ширины",
    "параметры:", "отбор:", "итого", "всего", "итог", "ед. изм.",
    "наименование", "количество", "начальный остаток", "приход", "расход",
    "конечный остаток", "конечный остаток м2", "кол-во", "товар",
}
_WIDTH_TOKENS = {"узкий", "широкий"}


def _is_empty(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v))


def _detect_stock_format(filepath: Path) -> str:
    """Определяет формат файла остатков по структуре сырого листа."""
    try:
        raw = pd.read_excel(filepath, header=None, engine="openpyxl")
    except Exception:
        return "generic"

    # Поиск первой строки, содержащей «Начальный остаток» в любой колонке
    for _, row in raw.head(40).iterrows():
        texts = [str(v).lower() for v in row.values if pd.notna(v)]
        joined = " ".join(texts)
        if "начальный остаток" in joined or "нач.остаток" in joined or "конечный остаток" in joined or "кон.остаток" in joined:
            # Ведомость: в шапке есть «Ед. изм.» и «Номенклатура, Характеристика»
            if any("ед. изм" in t for t in texts):
                return "vedomost"
            # Остатки с себестоимостью: есть «Тип ширины»/«Серия» и «Конечный остаток м2»
            if any("м2" in t or "м²" in t or "тип ширины" in t for t in texts):
                return "sebestoimost"
    return "generic"


def _numerify(df: pd.DataFrame, cols: list[str]) -> None:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)


def _split_nomen_char(cell: str) -> tuple[str, str]:
    """Разбивает строку «Номенклатура, Характеристика, Серия» из одной ячейки.

    Разделитель — «, » (запятая+пробел), чтобы не ломать десятичные запятые
    в названиях типа «16,5_Закладная ...». Пустые сегменты отбрасываются.
    Возвращает (product, characteristic).
    """
    cell = cell.strip()
    if ", " not in cell:
        return cell, ""
    parts = [p.strip() for p in cell.split(", ")]
    product = parts[0]
    # Пустые «слоты» и одиночные запятые-разделители (…, , ) отбрасываем
    rest = [p for p in parts[1:] if p and p != ","]
    return product, ", ".join(rest) if rest else ""


def _read_stock_vedomost(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """Формат «Ведомость по товарам на складах»:
    - Шапка на ~R7: Артикул(0) | Номенклатура,Характеристика,Серия(2) | Ед.изм.(10)
      | Начальный остаток(12) | Приход(13) | Расход(14) | Конечный остаток(15)
    - Склад указывается только в заголовочной строке секции (col0), пуст в деталях.
    """
    raw = pd.read_excel(filepath, header=None, engine="openpyxl")

    # find header row: row containing both «Номенклатура» (col2) and «Конечный остаток»
    header_idx = None
    for i in range(min(40, len(raw))):
        row = raw.iloc[i]
        text_col2 = str(row[2]).lower() if pd.notna(row[2]) else ""
        text_col12 = str(row[12]).lower() if len(row) > 12 and pd.notna(row[12]) else ""
        if "номенклатура" in text_col2 and ("остаток" in text_col12 or "остаток" in (str(row[15]).lower() if len(row) > 15 else "")):
            header_idx = i
            break
    if header_idx is None:
        # fallback: _smart_read
        return _read_stock_generic_raw(raw, filepath, "vedomost")

    records = []
    cur_warehouse = None
    header_row = raw.iloc[header_idx]

    for i in range(header_idx + 1, len(raw)):
        row = raw.iloc[i]
        col0 = str(row[0]).strip() if pd.notna(row[0]) else ""
        col2 = str(row[2]).strip() if pd.notna(row[2]) else ""
        col12 = row[12] if len(row) > 12 else None
        col15 = row[15] if len(row) > 15 else None

        # Строка-склад: col0 непустой, col2 пуст, и это не служебная строка
        if col0 and not col2 and col0.lower() not in _SKIP_COL0_TOKENS:
            cur_warehouse = col0
            continue

        # Служебные/итоговые строки
        if not col2 or col2.lower() in ("итого", "всего", "итог"):
            continue
        if col0.lower() in _SKIP_COL0_TOKENS:
            continue

        product, characteristic = _split_nomen_char(col2)

        records.append({
            "warehouse": cur_warehouse or "",
            "product": product,
            "characteristic": characteristic,
            "start_balance": col12,
            "income": row[13] if len(row) > 13 else None,
            "outcome": row[14] if len(row) > 14 else None,
            "end_balance": col15,
        })

    df = pd.DataFrame(records)
    _numerify(df, ["start_balance", "income", "outcome", "end_balance"])

    debug = {
        "filename": filepath.name,
        "format": "vedomost",
        "rows": len(df),
        "raw_rows": len(raw),
        "header_row": header_idx,
        "warehouses_found": sorted({w for w in df["warehouse"] if w}),
    }
    return df, debug


def _read_stock_sebestoimost(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """Формат «Остатки с себестоимостью по складам»:
    - Шапка: Номенклатура(0) | Характеристика(3) | Серия(5) | Нач(6) | Приход(7)
      | Расход(8) | Кон(9) | Кон м2(10)
    - Иерархия: склад (col0, появляется 1 раз) -> подкатегории «Узкий»/«Широкий»
      (col0), детали — тоже col0. Склад forward-fill по секциям.
    """
    raw = pd.read_excel(filepath, header=None, engine="openpyxl")

    # Найти шапку: строка с «Номенклатура»(0) и «Характеристика»(3)
    header_idx = None
    for i in range(min(40, len(raw))):
        row = raw.iloc[i]
        t0 = str(row[0]).lower() if pd.notna(row[0]) else ""
        t3 = str(row[3]).lower() if len(row) > 3 and pd.notna(row[3]) else ""
        if t0 == "номенклатура" and ("характеристика" in t3 or t3 == ""):
            header_idx = i
            break
    if header_idx is None:
        return _read_stock_generic_raw(raw, filepath, "sebestoimost")

    # Определить колонки складов: col0-значения, встречающиеся РОВНО 1 раз по всему
    # файлу и не являющиеся служебными/ширинами — это названия складов секций.
    col0_counter = {}
    for i in range(header_idx + 1, len(raw)):
        v = raw.iloc[i, 0]
        if pd.notna(v):
            s = str(v).strip()
            col0_counter[s] = col0_counter.get(s, 0) + 1

    def _is_warehouse_name(s: str) -> bool:
        s_l = s.lower()
        if s_l in _SKIP_COL0_TOKENS or s_l in _WIDTH_TOKENS or s_l in ("итого", "всего"):
            return False
        # строка-склад встречается ровно один раз по колонке 0
        return col0_counter.get(s, 0) == 1

    # Метки строк в секциях: ("warehouse", "width", "product", "has_char", "end")
    rows_meta = []          # (i, wh, width, product, has_char, end, start, income, outcome)
    cur_warehouse = None
    cur_width = ""
    for i in range(header_idx + 1, len(raw)):
        row = raw.iloc[i]
        col0 = str(row[0]).strip() if pd.notna(row[0]) else ""
        col3 = str(row[3]).strip() if len(row) > 3 and pd.notna(row[3]) else ""
        end = row[9] if len(row) > 9 else None

        if col0 and _is_warehouse_name(col0):
            cur_warehouse = col0
            cur_width = ""
            continue
        if col0.lower() in _WIDTH_TOKENS:
            cur_width = col0
            continue
        if not col0 or col0.lower() in _SKIP_COL0_TOKENS or col0.lower() in ("итого", "всего"):
            continue

        has_end = end is not None and not (isinstance(end, float) and pd.isna(end))
        rows_meta.append({
            "i": i,
            "wh": cur_warehouse or "",
            "width": cur_width,
            "product": col0,
            "has_char": bool(col3),
            "has_end": has_end,
        })

    # Множество товаров, у которых есть разбивка по характеристикам (col3).
    # Для таких товаров строки без характеристики — агрегаты (родительские итоги).
    products_with_char = {m["product"] for m in rows_meta if m["has_char"]}

    # Собираем только листовые строки:
    #  - строки с характеристикой всегда листовые;
    #  - строки без характеристики — листовые только если товар не имеет разбивки
    #    по характеристикам в этом складе (иначе это итоговая строка-агрегат).
    picked = []
    for m in rows_meta:
        if m["has_char"]:
            picked.append(m)
        elif m["product"] not in products_with_char and m["has_end"]:
            picked.append(m)

    # Дедупликация строк без характеристик: в иерархии «Товар → ширины → деталь»
    # без характеристик одна и та же строка повторяется (Товар, подытог ширины,
    # деталь) с одинаковыми значениями. Оставляем последнюю из каждой серии
    # одинаковых подряд идущих строк одного товара.
    deduped = []
    for m in picked:
        if m["has_char"]:
            deduped.append(m)
            continue
        if deduped and not deduped[-1]["has_char"] and deduped[-1]["product"] == m["product"]:
            # повторная строка того же товара без характеристики — заменяем последнюю
            deduped[-1] = m
        else:
            deduped.append(m)
    picked = deduped

    records = []
    for m in picked:
        row = raw.iloc[m["i"]]
        records.append({
            "warehouse": m["wh"],
            "product": m["product"],
            "characteristic": str(row[3]).strip() if pd.notna(row[3]) else "",
            "width": m["width"],
            "start_balance": row[6],
            "income": row[7],
            "outcome": row[8],
            "end_balance": row[9],
        })

    df = pd.DataFrame(records)
    _numerify(df, ["start_balance", "income", "outcome", "end_balance"])

    debug = {
        "filename": filepath.name,
        "format": "sebestoimost",
        "rows": len(df),
        "raw_rows": len(raw),
        "header_row": header_idx,
        "warehouses_found": sorted({w for w in df["warehouse"] if w}),
    }
    return df, debug


def _read_stock_generic_raw(raw: pd.DataFrame, filepath: Path, fmt: str) -> tuple[pd.DataFrame, dict]:
    """Fallback: читает raw-лист через generic-путь (для ведомости/sebestoimost)."""
    header_row = _find_header_row(raw)
    if header_row is None:
        raise ParseError(f"Не удалось найти заголовок в {filepath.name}")

    headers = []
    seen = set()
    for i in range(len(raw.columns)):
        val = raw.iloc[header_row, i]
        name = str(val).strip() if pd.notna(val) and str(val).strip() else f"col_{i}"
        if name in seen:
            name = f"{name}_{i}"
        seen.add(name)
        headers.append(name)

    df = raw.iloc[header_row + 1:].copy()
    df.columns = headers
    df.reset_index(drop=True, inplace=True)
    df = df.dropna(how="all")

    col_map = _map_columns(df, {
        "warehouse": ["склад"],
        "product": ["номенклатура", "товар", "наименование"],
        "characteristic": ["характеристика", "цвет", "ширина", "фактура"],
        "start_balance": ["нач.остаток", "начальный остаток"],
        "income": ["приход", "поступление"],
        "outcome": ["расход", "продажи"],
        "end_balance": ["кон.остаток", "конечный остаток"],
        "reserve": ["резерв", "зарезервировано"],
    })
    df = df.rename(columns=col_map)
    _numerify(df, ["start_balance", "income", "outcome", "end_balance", "reserve"])

    if "characteristic" not in df.columns and "product" in df.columns:
        _split_product_characteristic(df)

    debug = {
        "filename": filepath.name,
        "format": fmt + "_generic_fallback",
        "rows": len(df),
        "mapped": col_map,
    }
    return df, debug


def _split_product_characteristic(df: pd.DataFrame) -> None:
    """Разбивает объединённую колонку «Номенклатура, Характеристика, Серия» на
    product и characteristic. Первый сегмент до запятой — номенклатура,
    остальные собираются в характеристику. Хрупкий fallback для форматов,
    где колонки разделены, но данные слиты в одну ячейку.
    """
    col = "product"
    parts_col = df[col].astype(str).str.split(",", n=1, expand=True)
    if 1 in parts_col.columns:
        df["characteristic"] = parts_col[1].fillna("").str.strip()
        df[col] = parts_col[0].str.strip()


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
        "manager": ["менеджер", "ответственный"],
        "organization": ["организация"],
        "deferral": ["отсрочка", "дней отсрочки"],
        "debt_total": ["общий долг", "задолженность", "итого долг"],
        "debt_bucket_1_10": ["долг 1-10", "долг 1 - 10", "от 1 до 10"],
        "debt_bucket_11_15": ["долг 11-15", "долг 11 - 15", "от 11 до 15"],
        "debt_bucket_16_29": ["долг 16-29", "долг 16 - 29", "от 16 до 29"],
        "debt_bucket_over_30": ["долг свыше 30", "свыше 30", "от 30", "долг более 30"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    for num_col in ["sum", "overdue_days", "debt_total",
                    "debt_bucket_1_10", "debt_bucket_11_15",
                    "debt_bucket_16_29", "debt_bucket_over_30", "deferral"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

    return df, debug


def read_edo_excel(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """Читает выгрузку незавершённых ЭДО: Клиент/Адрес/Номер накладной/Сумма/Состояние/Остановлен."""
    df = _smart_read(filepath)
    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, {
        "client": ["клиент", "покупатель", "контрагент"],
        "address": ["адрес"],
        "invoice_number": ["накладная", "накладн", "номер"],
        "sum": ["сумма"],
        "state": ["состояние"],
        "stopped": ["остановлен"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

    if "sum" in df.columns:
        df["sum"] = pd.to_numeric(df["sum"], errors="coerce").fillna(0)

    return df, debug


def read_clients_excel(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """Читает реестр клиентов: Менеджер/Клиент/Город/Адрес/Телефон/Плательщик."""
    df = _smart_read(filepath)
    if df.empty:
        raise ParseError(f"Нет данных в файле {filepath.name}")

    debug = {"columns": _debug_columns(df), "rows": len(df), "filename": filepath.name}

    col_map = _map_columns(df, {
        "manager": ["менеджер", "ответственный"],
        "client": ["клиент", "покупатель", "контрагент"],
        "city": ["город", "бизнес-регион"],
        "address": ["адрес"],
        "phone": ["телефон"],
        "payer": ["плательщик"],
    })

    debug["mapped"] = col_map
    df = df.rename(columns=col_map)

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
