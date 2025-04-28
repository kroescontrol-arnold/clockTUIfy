# week_utils.py

from datetime import datetime, timedelta

def get_week_dates(offset_weeks=0):
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week += timedelta(weeks=offset_weeks)
    return [start_of_week + timedelta(days=i) for i in range(7)]

def is_future_date(date):
    today = datetime.utcnow().date()
    return date > today
