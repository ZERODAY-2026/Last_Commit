import re
from decimal import Decimal
from typing import Any


NUMBER = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?%?")


def answer_numbers_are_grounded(answer: str, rows: list[dict[str, Any]], question: str = "") -> bool:
    values = set()
    for row in rows:
        for value in row.values():
            if isinstance(value, (int, float, Decimal)):
                values.add(str(value))
                values.add(f"{float(value):.2f}")
    if question:
        for q_token in NUMBER.findall(question):
            clean_q = q_token.replace(",", "").rstrip("%")
            values.add(clean_q)
            try:
                values.add(f"{float(clean_q):.2f}")
            except ValueError:
                pass
    for token in NUMBER.findall(answer):
        token = token.replace(",", "").rstrip("%")
        try:
            if token not in values and f"{float(token):.2f}" not in values:
                return False
        except ValueError:
            pass
    return True
