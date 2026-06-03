from datetime import date, datetime
import calendar


def parse_date(date_string: str) -> date:
    return datetime.strptime(date_string, "%Y-%m-%d").date()


def get_month_end(input_date: date) -> date:
    last_day = calendar.monthrange(input_date.year, input_date.month)[1]
    return date(input_date.year, input_date.month, last_day)


def generate_monthly_spine(start_str: str, end_str: str) -> list[date]:
    start = parse_date(start_str)
    end = parse_date(end_str)

    month_ends: list[date] = []
    current_year = start.year
    current_month = start.month

    while date(current_year, current_month, 1) <= end:
        month_ends.append(get_month_end(date(current_year, current_month, 1)))

        if current_month == 12:
            current_month = 1
            current_year += 1
        else:
            current_month += 1

    return month_ends


def generate_month_ranges(start_str: str, end_str: str) -> list[dict[str, date]]:
    start = parse_date(start_str)
    end = parse_date(end_str)

    ranges: list[dict[str, date]] = []
    current_year = start.year
    current_month = start.month

    while date(current_year, current_month, 1) <= end:
        month_start = date(current_year, current_month, 1)
        month_end = get_month_end(month_start)

        ranges.append(
            {
                "month_start_date": month_start,
                "month_end_date": month_end,
            }
        )

        if current_month == 12:
            current_month = 1
            current_year += 1
        else:
            current_month += 1

    return ranges