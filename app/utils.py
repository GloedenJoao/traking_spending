from datetime import date, timedelta


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
    for offset in range(days + 1):
        yield start + timedelta(days=offset)
