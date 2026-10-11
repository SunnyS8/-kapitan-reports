"""Внутренние контрагенты (для НДС): общий помощник для отчётов.

Список берётся из переменной окружения INTERNAL_CLIENTS (см. .env.example).
Каждый элемент сравнивается как ПОДСТРОКА нормализованного имени.
Практическое следствие: если в базе «Ромашка ООО», а в переменной указано
«Ромашка ООО» — совпадёт. Если в базе «ООО Ромашка» — не совпадёт, потому
что порядок слов другой. При смене контрагентов проверяйте на реальной
выгрузке.
"""
from app.config import INTERNAL_CLIENTS


def is_internal_client(value) -> bool:
    """True, если контрагент — внутренний (для НДС), нормализуя пробелы/регистр."""
    if value is None:
        return False
    name = " ".join(str(value).strip().replace("\u00a0", " ").split()).lower()
    return any(token in name for token in INTERNAL_CLIENTS)