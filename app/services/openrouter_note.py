"""Аналитическая записка «от аналитика» через OpenRouter API (совместимый с OpenAI).

Вызов синхронный (httpx), поэтому в FastAPI-эндоинте оборачивается в asyncio.to_thread.
"""
import json
import os
import httpx
from datetime import datetime

from app.config import REPORT_TYPES

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
_TIMEOUT_S = 120
_MAX_PROMPT_CHARS = 12000


def _fmt_number(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


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
        num_cols = _NUM_COLUMNS(report_type)
        def _sort_key(d):
            vals = [_num(d.get(c)) for c in num_cols if isinstance(d.get(c), (int, float))]
            return max(vals) if vals else 0
        top = sorted(data, key=_sort_key, reverse=True)[:15]
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
    """Возвращает Markdown-записку от аналитика через OpenRouter API."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY не задан. Задайте переменную окружения."
        )

    prompt = build_prompt(report_type, result)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://kapitan-reports-production.up.railway.app",
        "X-Title": "Kapitan Reports",
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.3,
    }

    with httpx.Client(timeout=_TIMEOUT_S) as client:
        resp = client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    out = (data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
    if not out:
        raise RuntimeError("OpenRouter вернул пустой ответ")

    # Отрезаем лишние markdown-блоки, если модель обернула
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
        pass
    else:
        lines = body.splitlines()
        first_title = lines[0].lstrip("# ").strip()
        if first_title.lower() in ("аналитическая записка", "аналитическая записка к отчёту"):
            body = "\n".join(lines[1:]).strip()
    return header + body
