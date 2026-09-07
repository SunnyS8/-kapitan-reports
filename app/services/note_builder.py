"""Автоматическая аналитическая записка по правилам для каждого типа отчёта.

Принимает result (summary/data/chart) генератора и возвращает markdown-текст
с ключевыми показателями, динамикой и рисками. Используется для «Авто»
режима; «От аналитика» — отдельный модуль hermes_note.py.
"""
from datetime import datetime


def _num(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        if f != f:  # NaN
            return default
        return f
    except (TypeError, ValueError):
        return default


def _money(v) -> str:
    n = _num(v)
    return f"{n:,.0f}".replace(",", " ") + " ₽"


def _n(v) -> str:
    n = _num(v)
    return f"{n:,.0f}".replace(",", " ")


def _pct(v) -> str:
    n = _num(v)
    return f"{n:.1f}%"


def _top(data, key: str, n: int = 3, label_key: str | None = None) -> list:
    """Топ-n по числовому ключу. Возвращает [(label, value, share_share?)...]."""
    out = []
    items = sorted([d for d in data if _num(d.get(key)) > 0],
                   key=lambda d: _num(d.get(key)), reverse=True)[:n]
    total = sum(_num(d.get(key)) for d in data)
    for d in items:
        label = d.get(label_key) if label_key else d.get("product") or d.get("client") or d.get("name") or "—"
        out.append((str(label), _num(d.get(key)), _num(d.get(key)) / total * 100 if total else 0))
    return out


def _safe_v(s: dict, k: str, default="") -> str:
    v = s.get(k)
    if v is None:
        return default
    return str(v)


def auto_note(report_type: str, result: dict) -> str:
    summary = result.get("summary") or {}
    data = result.get("data") or []

    if summary.get("error"):
        return (
            "# Аналитическая записка\n\n"
            f"**Отчёт «{report_type}» сформировать не удалось.**\n\n"
            f"Ошибка: {summary.get('error')}\n"
        )

    builder = _BUILDERS.get(report_type)
    if builder is None:
        return _generic_note(report_type, summary, data)
    try:
        body = builder(summary, data)
    except Exception as e:
        body = f"Не удалось сформировать авто-записку: {e}"
    return (
        "# Аналитическая записка\n\n"
        f"*Сформировано автоматически по правилам · {datetime.now().strftime('%d.%m.%Y %H:%M')}*\n\n"
        f"{body}"
    )


def save_note_to_knowledge(report_type: str, text: str, config_module) -> str:
    """Сохраняет записку .md в подпапку отчёта базы знаний (06 - Аналитика и отчёты).
    Возвращает имя файла или "" при ошибке."""
    try:
        out_sub = getattr(config_module, "REPORT_OUT_DIRS", {}).get(report_type)
        if not out_sub:
            return ""
        out_dir = config_module.KNOWLEDGE_ANALYTICS / out_sub
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{report_type}_записка_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        (out_dir / filename).write_text(text, encoding="utf-8")
        return filename
    except Exception:
        return ""


# ------------------------------ по типам ------------------------------

def _sales_clients_note(s: dict, data: list) -> str:
    money = _money(s.get("total_revenue"))
    clients = _n(s.get("total_clients"))
    sales = _n(s.get("total_sales"))
    check = _n(s.get("avg_check"))
    top = _top(data, "revenue", label_key="client")
    lines = [
        f"**Итоговая выручка за период:** {money}.",
        f"**Клиентов:** {clients}, **продаж:** {sales}, **средний чек:** {check} ₽.",
        f"Период: {_safe_v(s, 'period_start', '—')} – {_safe_v(s, 'period_end', '—')}.",
    ]
    if top:
        lines.append("\n**Топ-клиенты по выручке:**")
        for label, val, share in top:
            lines.append(f"  - {label} — {_money(val)} ({_pct(share)} от выручки)")
    lines.append("\n**Вывод:** база клиентов " + (
        "диверсифицирована, если рост.TOR" if len(data) >= 10 else "небольшая, стоит расширять."))
    return "\n".join(lines)


def _sales_products_note(s: dict, data: list) -> str:
    lines = [
        f"**Выручка:** {_money(s.get('total_revenue'))}.",
        f"**Позиций товара:** {_n(s.get('total_products'))}.",
        f"ABC-структура: A — {_n(s.get('count_a'))}, B — {_n(s.get('count_b'))}, C — {_n(s.get('count_c'))}.",
        f"Период: {_safe_v(s, 'period_start', '—')} – {_safe_v(s, 'period_end', '—')}.",
    ]
    top_a = [d for d in data if d.get("category") == "A"]
    if top_a:
        lines.append("\n**Категория A (до 80% выручки):**")
        for d in top_a[:5]:
            lines.append(f"  - {d.get('product','—')} — {_money(d.get('revenue'))} ({_pct(d.get('share'))})")
    bc = _num(s.get("count_b", 0)) + _num(s.get("count_c", 0))
    lines.append(f"\n**Вывод:** хвост из B/C позиций ({_n(bc)}) даёт контрольный процент отчёта — "
                 f"стоит пересмотреть закупку неликвидных артикулов.")
    return "\n".join(lines)


def _inventory_note(s: dict, data: list) -> str:
    wh = s.get("warehouses") or {}
    lines = [
        f"**Позиций в остатках:** {_n(s.get('total_items'))}.",
        f"**Общий стоимостной остаток (end balance):** {_money(s.get('total_end_balance'))}.",
        f"**Складов в выгрузке:** {len(wh)}.",
        "\nОстатки по складам:",
    ]
    for name, st in sorted(wh.items(), key=lambda kv: -_num(kv[1].get("end_balance"))):
        lines.append(f"  - {name} — {_n(st.get('count'))} поз., {_money(st.get('end_balance'))}")
    lines.append(f"\n**Вывод:** сумма остатков {_money(s.get('total_end_balance'))} — "
                 f"{'требует контроля динамики' if _num(s.get('total_items')) > 1000 else 'в пределах нормы'}.")
    return "\n".join(lines)


def _dynamics_note(s: dict, data: list) -> str:
    r1 = _num(s.get("revenue_1"))
    r2 = _num(s.get("revenue_2"))
    diff = _num(s.get("diff"))
    pct = _num(s.get("diff_pct"))
    trend = s.get("trend", "flat")
    emoji = "📈 рост" if trend == "up" else "📉 падение" if trend == "down" else "➡️ без изменений"
    lines = [
        f"**Период 1:** {_safe_v(s, 'period_1', '—')} — {_money(r1)}.",
        f"**Период 2:** {_safe_v(s, 'period_2', '—')} — {_money(r2)}.",
        f"\n**Изменение:** {emoji}, {_money(abs(diff))} ({_pct(pct)}).",
    ]
    if trend == "up":
        lines.append("\n**Вывод:** продажи растут — закрепить драйверы, проверить запас товара под спрос.")
    elif trend == "down":
        lines.append("\n**Вывод:** продажи падают — проанализировать причины (ассортимент, цены, клиенты).")
    else:
        lines.append("\n**Вывод:** продажи стабильны, роста нет — искать новые точки роста.")
    return "\n".join(lines)


def _forecast_note(s: dict, data: list) -> str:
    plan = _num(s.get("total_plan"))
    fact = _num(s.get("total_fact"))
    pct = _num(s.get("total_pct"))
    lines = [
        f"**План:** {_money(plan)}. **Факт:** {_money(fact)}.",
        f"**Выполнение плана:** {_pct(pct)}.",
        f"**Клиентов в сравнении:** {_n(s.get('items_count'))}.",
    ]
    if pct >= 100:
        lines.append("\n**Вывод:** план выполнен — факт опережает план.")
    elif pct >= 70:
        lines.append(f"\n**Вывод:** план выполнен на {_pct(pct)} — наверстать отставание до конца периода.")
    else:
        lines.append(f"\n**Вывод:** план выполнен лишь на {_pct(pct)} — риск невыполнения, требуется пересмотр целей.")
    # Худшие клиенты
    worst = sorted([d for d in data if _num(d.get("plan")) > 0],
                   key=lambda d: _num(d.get("pct")))[:3]
    if worst:
        lines.append("\n**Клиенты с наибольшим отставанием от плана:**")
        for d in worst:
            lines.append(f"  - {d.get('name','—')} — {_pct(d.get('pct'))} (факт {_money(d.get('fact'))} / план {_money(d.get('plan'))})")
    return "\n".join(lines)


def _debt_note(s: dict, data: list) -> str:
    overdue = _num(s.get("overdue_sum"))
    share = overdue / _num(s.get("total_sum")) * 100 if _num(s.get("total_sum")) else 0
    lines = [
        f"**Сумма дебиторской задолженности:** {_money(s.get('total_sum'))}.",
        f"**Просрочено (>90 дней):** {_money(overdue)} ({_pct(share)} от общего долга).",
        f"**Счетов всего:** {_n(s.get('total_invoices'))}, из них просрочено: {_n(s.get('overdue_count'))}.",
    ]
    worst = sorted([d for d in data if d.get("overdue_days", 0) > 90],
                   key=lambda d: d["overdue_days"], reverse=True)[:3]
    if worst:
        lines.append("\n**Худшие должники по просрочке:**")
        for d in worst:
            lines.append(f"  - {d.get('client','—')} — {_money(d.get('sum'))}, просрочка {_n(d.get('overdue_days'))} дн")
    if share > 30:
        lines.append("\n**Вывод:** высокая доля просроченной задолженности — усилить работу с должниками.")
    else:
        lines.append("\n**Вывод:** доля просрочки в общем долге умеренная, держать на контроле.")
    return "\n".join(lines)


def _debt_manager_note(s: dict, data: list) -> str:
    total = _num(s.get("total_debt"))
    over30 = _num(s.get("bucket_over_30"))
    over30_share = over30 / total * 100 if total else 0
    lines = [
        f"**Общий долг:** {_money(total)} по {_n(s.get('clients'))} клиентам.",
        f"**Бакеты:** 1-10 дн — {_money(s.get('bucket_1_10'))}, 11-15 — {_money(s.get('bucket_11_15'))}, "
        f"16-29 — {_money(s.get('bucket_16_29'))}, **свыше 30 дн — {_money(over30)} ({_pct(over30_share)} от долга)**.",
    ]
    by_manager = {}
    for d in data:
        m = d.get("Менеджер") or "—"
        by_manager[m] = by_manager.get(m, 0) + _num(d.get("Общий долг"))
    lines.append("\n**Долг по менеджерам:**")
    for m, v in sorted(by_manager.items(), key=lambda kv: -kv[1]):
        lines.append(f"  - {m} — {_money(v)}")
    if over30_share > 25:
        lines.append(f"\n**Вывод:** критический бакет свыше 30 дней составляет {_pct(over30_share)} долга — "
                     f"немедленно разобрать проблемных клиентов.")
    else:
        lines.append("\n**Вывод:** большую часть долга составляет свежая задолженность (до 30 дней) — контролируемый уровень.")
    return "\n".join(lines)


def _stock_dynamics_note(s: dict, data: list) -> str:
    balance = _num(s.get("total_balance"))
    reserve = _num(s.get("total_reserve"))
    reserve_share = reserve / balance * 100 if balance else 0
    lines = [
        f"**Позиций в динамике:** {_n(s.get('total_items'))}.",
        f"**Остаток на день выгрузки:** {_money(balance)}. **Резерв:** {_money(reserve)} ({_pct(reserve_share)} от остатка).",
        "\nТоп-склады по остатку:",
    ]
    top = sorted(data, key=lambda d: _num(d.get("Остаток")), reverse=True)[:5]
    seen = set()
    for d in top:
        loc = d.get("Город склада", "—")
        if loc in seen:
            continue
        seen.add(loc)
        lines.append(f"  - {loc} — {_money(d.get('Остаток'))} (резерв {_money(d.get('Резерв', 0))})")
    if reserve_share > 50:
        lines.append(f"\n**Вывод:** высокая доля резерва ({_pct(reserve_share)}) — значительная часть остатков зарезервирована под заказы.")
    else:
        lines.append("\n**Вывод:** резерв занимает умеренную долю остатков.")
    return "\n".join(lines)


def _edo_note(s: dict, data: list) -> str:
    total = _num(s.get("total_sum"))
    stopped = _num(s.get("stopped_count"))
    docs = _num(s.get("total_docs"))
    lines = [
        f"**Документов в очереди ЭДО:** {_n(docs)}, на сумму {_money(total)}.",
        f"**Остановлено:** {_n(stopped)}.",
    ]
    if docs:
        top = sorted(data, key=lambda d: _num(d.get("Сумма")), reverse=True)[:3]
        lines.append("\n**Крупнейшие зависшие документы:**")
        for d in top:
            lines.append(f"  - {d.get('Клиент','—')} №{d.get('Номер накладной','—')} — {_money(d.get('Сумма'))}"
                         f" ({d.get('Состояние','—')}{', стоп' if str(d.get('Остановлен','')).lower() in ('да','1','true','истина') else ''})")
    if stopped > 0:
        lines.append(f"\n**Вывод:** {_n(stopped)} документов остановлено — проверить причины блокировки ЭДО.")
    else:
        lines.append("\n**Вывод:** зависших/остановленных документов нет — ЭДО в норме.")
    return "\n".join(lines)


def _clients_note(s: dict, data: list) -> str:
    lines = [
        f"**Всего клиентов в реестре:** {_n(s.get('total_clients'))}.",
        f"\n**Вывод:** реестр актуален, клиентская база составляет {_n(s.get('total_clients'))} записей."
    ]
    return "\n".join(lines)


def _nelikvid_note(s: dict, data: list) -> str:
    total = _num(s.get("total_sum"))
    items = _num(s.get("total_items"))
    cats = s.get("categories") or {}
    lines = [
        f"**Неликвидов позиций:** {_n(items)}, оценочная сумма по формуле Ирины: **{_money(total)}**.",
        "\nПо категориям:",
    ]
    for name, v in sorted(cats.items(), key=lambda kv: -_num(kv[1])):
        lines.append(f"  - {name} — {_money(v)}")
    if items == 0:
        lines.append("\n**Вывод:** неликвидов не обнаружено в выгрузке.")
    else:
        lines.append(f"\n**Вывод:** заморожено в неликвидах ≈ {_money(total)} — проработать распродажу/списание.")
    return "\n".join(lines)


def _top_clients_note(s: dict, data: list) -> str:
    share = _num(s.get("top_revenue_share"))
    lines = [
        f"**Выручка (без внутренних контрагентов):** {_money(s.get('total_revenue'))}.",
        f"**Клиентов в разрезе:** {_n(s.get('clients_in_report'))}, показано топ-{_n(s.get('top_shown'))}.",
        f"**Доля топ-{_n(s.get('top_shown'))} в выручке:** {_pct(share)}.",
    ]
    internal_total = _num(s.get("internal_total"))
    if internal_total:
        lines.append(f"\n⚠️ **Внутренние контрагенты (НДС):** {_n(s.get('internal_count'))} шт. на {_money(internal_total)} — в общие продажи не входят.")
    top = _top(data, "Сумма", label_key="Клиент")
    if top:
        lines.append("\n**Топ клиентов:**")
        for label, val, sh in top:
            lines.append(f"  - {label} — {_money(val)} ({_pct(sh)})")
    lines.append(f"\n**Вывод:** концентрация в топе составляет {_pct(share)} — "
                 f"{'высокая зависимость от ключевых клиентов' if share > 60 else 'риски концентрации умеренные'}.")
    return "\n".join(lines)


def _top_products_note(s: dict, data: list) -> str:
    share = _num(s.get("top_revenue_share"))
    lines = [
        f"**Выручка:** {_money(s.get('total_revenue'))}.",
        f"**Номенклатурных позиций:** {_n(s.get('total_products'))}, показано топ-{_n(s.get('top_shown'))}.",
        f"**Доля топ-{_n(s.get('top_shown'))} в выручке:** {_pct(share)}.",
    ]
    top = _top(data, "Сумма", label_key="Номенклатура")
    if top:
        lines.append("\n**Топ позиций:**")
        for label, val, sh in top:
            lines.append(f"  - {label} — {_money(val)} ({_pct(sh)})")
    lines.append(f"\n**Вывод:** топ-{_n(s.get('top_shown'))} даёт {_pct(share)} выручки — "
                 f"ассортимент {'сконцентрирован на бестселлерах' if share > 70 else 'распределён равномерно'}.")
    return "\n".join(lines)


def _generic_note(report_type: str, s: dict, data: list) -> str:
    try:
        total = _money(s.get("total_sum", s.get("total_revenue", s.get("total_debt", 0))))
    except Exception:
        total = "—"
    lines = [
        f"**Тип отчёта:** {report_type}. Строк в данных: {_n(len(data))}.",
        f"Ключевая сумма: {total}.",
        f"\n*Подробный авто-разбор для этого типа отчёта пока не настроен — доступна запись «От аналитика».*",
    ]
    return "\n".join(lines)


_BUILDERS = {
    "sales_clients": _sales_clients_note,
    "sales_products": _sales_products_note,
    "inventory": _inventory_note,
    "dynamics": _dynamics_note,
    "forecast": _forecast_note,
    "debt": _debt_note,
    "debt_manager": _debt_manager_note,
    "stock_dynamics": _stock_dynamics_note,
    "edo": _edo_note,
    "clients": _clients_note,
    "nelikvid": _nelikvid_note,
    "top_clients": _top_clients_note,
    "top_products": _top_products_note,
}