import re
from datetime import date


def validate_phone(phone: str) -> bool:
    return bool(re.match(r"^1[3-9]\d{9}$", phone))


def validate_date_range(start: date, end: date) -> bool:
    return start <= end


def validate_positive_number(value) -> bool:
    try:
        return float(value) >= 0
    except (ValueError, TypeError):
        return False


def sanitize_string(value: str, max_length: int = 200) -> str:
    if not value:
        return ""
    return value.strip()[:max_length]
