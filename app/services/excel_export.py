"""Экспорт отчётов в Excel и в папки базы знаний."""
import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime


def export_to_excel(data: list[dict], report_type: str, reports_dir: Path,
                    extra_sheets: dict[str, list[dict]] | None = None) -> str:
    """
    Экспорт данных отчёта в Excel-файл.
    Возвращает имя файла.
    extra_sheets — дополнительные листы (например, внутренние контрагенты).
    """
    if not data and not extra_sheets:
        return ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_{timestamp}.xlsx"
    filepath = reports_dir / filename

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        if data:
            df = pd.DataFrame(data)
            df.to_excel(writer, index=False, sheet_name="Данные")
            _autofit(writer.sheets["Данные"])

        if extra_sheets:
            for sheet_name, sheet_data in extra_sheets.items():
                if not sheet_data:
                    continue
                sdf = pd.DataFrame(sheet_data)
                ws_name = sheet_name[:31]
                sdf.to_excel(writer, index=False, sheet_name=ws_name)
                _autofit(writer.sheets[ws_name])

    return filename


def _autofit(ws) -> None:
    """Автоподбор ширины колонок листа."""
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
                _autofit(writer.sheets[sheet_name[:31]])

    return filename


def write_summary_md(report_type: str, data: list[dict], summary: dict, out_dir: Path,
                     internal: list[dict] | None = None) -> str:
    """Пишет сводку отчёта в markdown-файл. Возвращает имя файла.
    internal — отдельный блок (внутренние контрагенты для НДС)."""
    title = {
        "sales_clients": "Продажи по клиентам",
        "sales_products": "Продажи по товарам",
        "inventory": "Остатки на складах",
        "dynamics": "Динамика продаж",
        "forecast": "План vs Факт",
        "debt": "Неоплаченные счета",
        "nelikvid": "Неликвиды",
        "top_clients": "Топ клиенты в разрезе номенклатуры",
        "top_products": "Топ продаж по номенклатуре",
        "stock_dynamics": "Динамика по складу",
        "clients": "Реестр клиентов",
        "edo": "Незавершённые ЭДО",
        "sales_detailed": "Отчёт по продажам (развёрнутый)",
        "sales_client_detail": "Отчёт по продажам (клиентский)",
        "debt_manager": "Задолженность клиента",
    }.get(report_type, report_type)

    now = datetime.now()
    lines = [f"# {title} — {now.strftime('%d.%m.%Y %H:%M')}", ""]

    if summary:
        lines.append("## Сводка")
        lines.append("")
        for k, v in summary.items():
            if k in ("debug",) or isinstance(v, (list, dict)):
                continue
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    if data:
        lines.append("## Данные")
        lines.append("")
        # Убираем технические колонки col_* (сырые безымянные)
        headers = [h for h in list(data[0].keys()) if not str(h).startswith("col_")]
        if not headers:
            headers = list(data[0].keys())
        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")
        for row in data[:200]:
            lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")

    if internal:
        lines.append("")
        lines.append("## Внутренние контрагенты (НДС)")
        lines.append("")
        lines.append("Выводятся отдельно и не входят в общие результаты.")
        lines.append("")
        in_headers = [h for h in list(internal[0].keys()) if not str(h).startswith("col_")]
        if not in_headers:
            in_headers = list(internal[0].keys())
        lines.append("| " + " | ".join(str(h) for h in in_headers) + " |")
        lines.append("|" + "|".join("---" for _ in in_headers) + "|")
        for row in internal:
            lines.append("| " + " | ".join(str(row.get(h, "")) for h in in_headers) + " |")

    filename = f"{report_type}_{now.strftime('%Y%m%d')}_сводка.md"
    (out_dir / filename).write_text("\n".join(lines), encoding="utf-8")
    return filename


def save_report_to_knowledge(report_type: str, data: list[dict], summary: dict,
                             xlsx_name: str, config_module,
                             internal: list[dict] | None = None) -> None:
    """Записывает результат отчёта в папку базы знаний (xlsx + md сводку),
    а для месячных отчётов — дополнительную копию в 07 - Ежемесячные отчёты.
    internal — отдельный блок (внутренние контрагенты для НДС)."""
    out_sub = getattr(config_module, "REPORT_OUT_DIRS", {}).get(report_type)
    if not out_sub:
        return

    base_out = config_module.KNOWLEDGE_ANALYTICS / out_sub
    base_out.mkdir(parents=True, exist_ok=True)

    # Копия Excel, если он сгенерирован внутри Kapitan
    if xlsx_name:
        src = config_module.REPORTS_DIR / xlsx_name
        if src.exists():
            shutil.copy2(src, base_out / xlsx_name)

    write_summary_md(report_type, data, summary, base_out, internal=internal)

    # Дублирование в месячные
    if report_type in getattr(config_module, "MONTHLY_REPORTS", set()):
        monthly_dir = config_module.KNOWLEDGE_MONTHLY
        monthly_dir.mkdir(parents=True, exist_ok=True)
        if xlsx_name:
            src = config_module.REPORTS_DIR / xlsx_name
            if src.exists():
                shutil.copy2(src, monthly_dir / xlsx_name)
        write_summary_md(report_type, data, summary, monthly_dir, internal=internal)
