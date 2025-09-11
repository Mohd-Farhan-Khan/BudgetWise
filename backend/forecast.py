# Simple forecasting stub - replace with real ML model later
from typing import List

def forecast_next_month(expenses: List[dict]) -> float:
    """Return a naive forecast: average monthly spend."""
    if not expenses:
        return 0.0
    total = sum(e.get("amount", 0) for e in expenses)
    months = 1
    return total / months
