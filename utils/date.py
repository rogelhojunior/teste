from datetime import datetime, timedelta
from typing import Optional

import holidays
from dateutil.relativedelta import relativedelta
from django.utils import timezone


def get_next_weekday(
    current_date: Optional[datetime.date] = None,
    excluded_weekdays: tuple = (5, 6),
    holiday_calendar: Optional[holidays.HolidayBase] = None,
) -> datetime.date:
    """
    Gets next weekday based on start datetime.
    Avoid specified weekdays and holidays.
    Args:
        current_date: Optional start date (default localdate())
        excluded_weekdays: Excluded weekdays, default (5- Saturday, 6- Sunday)
        holiday_calendar: Optional holiday calendar, default BR holidays
    Returns:
        New date available.

    """
    if not current_date:
        current_date = timezone.localdate()
    if not holiday_calendar:
        holiday_calendar = holidays.country_holidays('BR')
    while True:
        current_date += timedelta(days=1)
        if (
            current_date.weekday() not in excluded_weekdays
            and current_date not in holiday_calendar
        ):
            return current_date


def get_valid_disbursement_day() -> datetime.date:
    """
    Returns valid disbursment day based on current calling.

    Returns:
        datetime.date: Date object with valid day info

    """
    now = timezone.localtime()
    if now.weekday() not in (5, 6) and 7 < now.hour < 17:
        return timezone.localdate()
    return get_next_weekday()


def calculate_end_date_by_months(months: int, initial_date=None) -> datetime.date:
    """
    Calculates end date, based on initial date and months

    Args:
        months: Number of months to end date
        initial_date: Initial date to count (default: timezone.localdate(None)

    Returns:

    """
    return timezone.localdate(initial_date) + relativedelta(months=months)
