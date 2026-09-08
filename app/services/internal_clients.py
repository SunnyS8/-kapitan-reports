"""Внутренние контрагенты (для НДС): общий помощник для отчётов."""
from app.config import INTERNAL_CLIENTS


def is_internal_client(value) -> bool:
    """True, если контрагент — внутренний (для НДС), нормализуя пробелы/регистр."""
    if value is None:
        return False
    name = " ".join(str(value).strip().replace("\u00a0", " ").split()).lower()
    return any(token in name for token in INTERNAL_CLIENTS)