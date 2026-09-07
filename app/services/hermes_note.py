"""Аналитическая записка «от аналитика» через Hermes (профиль analyst, one-shot -z).

Вызов синхронный (subprocess), поэтому в FastAPI-эндоинте оборачивается
в asyncio.to_thread. Промпт получает данные текстом (не файлом) — так
обходится ограничение Hermes на чтение локальных файлов Windows.
"""
import json
import os
import subprocess
from datetime import datetime

from app.config import REPORT_TYPES

HERMES_EXE = r"C:\Users\User\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
HERMES_PROFILE = "analyst"
_TIMEOUT_S = 180
_MAX_PROMPT_CHARS = 12000


def _fmt_number(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


def _compact_payload(report_type: str, result: dict) -> str:
    """Компактное текстовое представление result для промпта."""
    summary = result.get("summary") or {}
    data = result.get("data") or []

    lines = [f"Тип отчёта: {REPORT_TYPES.get(report_type, report_type)}  ({report_type})"]

    if summary.get("error"):
        lines.append("ОШИБКА ПРИ ФОРМИРОВАНИИ: " + str(summary.get("error")))
        return "\n".join(lines)

    s = {}
    for k, v in summary.items():
        if k == "debug":
            continue
        if isinstance(v, (int, float)):
            s[k] = _fmt_number(v)
        elif isinstance(v, dict):
            s[k] = "; ".join(f"{ki}: {_fmt_number(vi) if isinstance(vi,(int,float)) else vi}"
                             for ki, vi in v.items())
        elif isinstance(v, list):
            s[k] = json.dumps(v, ensure_ascii=False)[:500]
        elif isinstance(v, str):
            s[k] = v
    if s:
        lines.append("ИТОГОВЫЕ ПОКАЗАТЕЛИ:")
        for k, v in s.items():
            lines.append(f"  {k} = {v}")

    if data:
        top = sorted(data, key=lambda d: max(_num(d.get(c)) for c in _NUM_COLUMNS(report_type) if isinstance(d.get(c), (int, float))) or 0,
                     reverse=True)[:15]
        lines.append("\nВЫБОРКА ПО ДАННЫМ (топ строк):")
        if top:
            cols = list(top[0].keys())[:7]
            lines.append("  | " + " | ".join(cols))
            for d in top:
                values = []
                for c in cols:
                    v = d.get(c)
                    if isinstance(v, (int, float)):
                        values.append(_fmt_number(v))
                    else:
                        values.append(str(v)[:40])
                lines.append("  | " + " | ".join(values))

    return "\n".join(lines)[:_MAX_PROMPT_CHARS]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _NUM_COLUMNS(report_type: str) -> list[str]:
    mapping = {
        "sales_clients": ["revenue"],
        "sales_products": ["revenue"],
        "top_clients": ["Сумма"],
        "top_products": ["Сумма"],
        "debt": ["sum"],
        "debt_manager": ["Общий долг"],
        "stock_dynamics": ["Остаток"],
        "inventory": ["end_balance"],
        "dynamics": ["revenue"],
        "forecast": ["fact"],
        "edo": ["Сумма"],
        "nelikvid": ["sum"],
        "clients": [],
    }
    return mapping.get(report_type, [])


def build_prompt(report_type: str, result: dict) -> str:
    payload = _compact_payload(report_type, result)
    instruction = (
        "Ты — финансовый аналитик компании «Капитан» (текстиль, мягкий инвентарь, обои, ламинат, отрезы).\n"
        "По данным отчёта составь КРАТКУЮ аналитическую записку для руководителя на русском языке "
        "в формате Markdown по структуре:\n"
        "## Ключевые показатели\n## Что в динамике / структуре\n## Риски\n## Рекомендации (2-3 пункта)\n\n"
        "Используй конкретные цифры из данных. Не выдумывай то, чего нет в данных. "
        "Не пиши «по данным отчёта видно» — сразу по делу. Объём: не более 250 слов.\n\n"
    )
    return instruction + "-" * 40 + "\nДАННЫЕ ОТЧЁТА:\n" + payload


def build_ai_note(report_type: str, result: dict) -> str:
    """Возвращает Markdown-записку от аналитика (raw текст из Hermes)."""
    prompt = build_prompt(report_type, result)
    env = dict(os.environ)
    env["HERMES_PROFILE"] = HERMES_PROFILE
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        [HERMES_EXE, "-z", prompt, "--yolo"],
        capture_output=True,
        timeout=_TIMEOUT_S,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-800:]
        raise RuntimeError(f"Hermes завершился с кодом {proc.returncode}: {tail}")

    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError("Hermes вернул пустой ответ")

    # Отрезаем служебный мусор, если Hermes печатает больше финального ответа
    if "```" in out and out.count("```") >= 2:
        parts = out.split("```")
        if len(parts) >= 3 and "markdown" not in parts[1][:80]:
            out = parts[1].strip()
    return out


def note_to_markdown(report_type: str, ai_text: str, generated_at: str | None = None) -> str:
    header = (
        "# Аналитическая записка\n\n"
        f"*От аналитика · {REPORT_TYPES.get(report_type, report_type)} · "
        f"{generated_at or datetime.now().strftime('%d.%m.%Y %H:%M')}*\n\n"
    )
    body = ai_text.strip()
    if not body.startswith("#"):
        body = body
    else:
        # убираем свой заголовок, чтобы не дублировать
        lines = body.splitlines()
        first_title = lines[0].lstrip("# ").strip()
        if first_title.lower() in ("аналитическая записка", "аналитическая записка к отчёту"):
            body = "\n".join(lines[1:]).strip()
    return header + body