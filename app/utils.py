from datetime import date, timedelta
from typing import List


def is_business_day(check_date: date) -> bool:
    return check_date.weekday() < 5


def adjust_to_previous_business_day(target_date: date) -> date:
    adjusted = target_date
    while not is_business_day(adjusted):
        adjusted -= timedelta(days=1)
    return adjusted


def penultimate_business_day(year: int, month: int) -> date:
    # start from last day of month
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)

    business_days = []
    current = last_day
    while len(business_days) < 2:
        if is_business_day(current):
            business_days.append(current)
        current -= timedelta(days=1)
    return business_days[-1]


def daterange(start: date, days: int):
    for offset in range(days):
        yield start + timedelta(days=offset)


def expand_date_ranges(date_starts: List[str], date_ends: List[str]) -> List[date]:
    dates: List[date] = []
    for index, start_str in enumerate(date_starts):
        if not start_str:
            continue
        start = date.fromisoformat(start_str)
        end_str = date_ends[index] if index < len(date_ends) and date_ends[index] else None
        end = date.fromisoformat(end_str) if end_str else start
        if end < start:
            start, end = end, start

        current = start
        while current <= end:
            if current not in dates:
                dates.append(current)
            current += timedelta(days=1)
    return dates
