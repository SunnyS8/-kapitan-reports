"""Экспорт отчётов в Excel."""
import pandas as pd
from pathlib import Path
from datetime import datetime


def export_to_excel(data: list[dict], report_type: str, reports_dir: Path) -> str:
    """
    Экспорт данных отчёта в Excel-файл.
    Возвращает имя файла.
    """
    if not data:
        return ""

    df = pd.DataFrame(data)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_{timestamp}.xlsx"
    filepath = reports_dir / filename

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Данные")

        # Автоподбор ширины колонок
        ws = writer.sheets["Данные"]
        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_length + 2, 40)

    return filename


def export_multi_sheet(sheets: dict[str, list[dict]], report_type: str, reports_dir: Path) -> str:
    """
    Экспорт multi-sheet Excel (для неликвидов — Сводная / Товары / Поскладные).
    sheets = {"Сводная": [...], "Товары": [...], ...}
    """
    if not sheets:
        return ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_{timestamp}.xlsx"
    filepath = reports_dir / filename

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sheet_name, data in sheets.items():
            if data:
                df = pd.DataFrame(data)
                df.to_excel(writer, index=False, sheet_name=sheet_name[:31])  # 31 — лимит Excel

                ws = writer.sheets[sheet_name[:31]]
                for col in ws.columns:
                    max_length = 0
                    col_letter = col[0].column_letter
                    for cell in col:
                        try:
                            if cell.value:
                                max_length = max(max_length, len(str(cell.value)))
                        except Exception:
                            pass
                    ws.column_dimensions[col_letter].width = min(max_length + 2, 40)

    return filename
