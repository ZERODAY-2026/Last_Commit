import re
from decimal import Decimal
from typing import Any


NUMBER = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?%?")


def answer_numbers_are_grounded(answer: str, rows: list[dict[str, Any]]) -> bool:
    values = set()
    for row in rows:
        for value in row.values():
            if isinstance(value, (int, float, Decimal)):
                values.add(str(value))
                values.add(f"{float(value):.2f}")
    for token in NUMBER.findall(answer):
        token = token.replace(",", "").rstrip("%")
        if token not in values and f"{float(token):.2f}" not in values:
            return False
    return True
