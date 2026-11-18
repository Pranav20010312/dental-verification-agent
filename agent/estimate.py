"""Patient cost estimate for one appointment.

Order of checks per procedure line:
  1. plan inactive        -> patient pays the full fee
  2. frequency limit hit  -> not covered (benefit year = calendar year)
  3. major waiting period -> not covered
  4. deductible (basic and major only), then coverage %, then annual max cap
Simplifications: office fee = allowed amount, no alternate-benefit
downgrades, no coordination of benefits.
"""
import calendar
from datetime import date
from typing import Any

from .models import Appointment, Estimate, FeeItem, LineEstimate


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def estimate(appt: Appointment, benefits: dict[str, Any],
             fees: dict[str, FeeItem]) -> Estimate:
    """benefits maps flat field keys (e.g. 'coverage.basic') to plain values."""
    deductible = float(benefits.get("deductible_remaining") or 0)
    max_left = float(benefits.get("annual_max_remaining") or 0)
    year = appt.appt_date.year
    used: dict[str, int] = {}
    for key, dates in benefits.items():
        if key.startswith("hist."):
            used[key[5:]] = sum(1 for d in dates or [] if date.fromisoformat(d).year == year)

    lines = []
    for code in appt.cdt_codes:
        item = fees[code]
        group = item.frequency_group
        limit = benefits.get(f"freq.{group}") if group else None
        covered, note = True, ""

        if not benefits.get("active", False):
            covered, note = False, "plan inactive"
        elif limit is not None and used.get(group, 0) >= limit:
            covered, note = False, f"frequency limit {int(limit)}/yr reached"
        elif item.category == "major":
            start = benefits.get("effective_date")
            wait = int(benefits.get("major_wait_months") or 0)
            if start and wait:
                eligible = add_months(date.fromisoformat(start), wait)
                if appt.appt_date < eligible:
                    covered, note = False, f"major waiting period until {eligible}"

        insurance = 0.0
        if covered:
            if group:
                used[group] = used.get(group, 0) + 1
            ded_part = 0.0 if item.category == "preventive" else min(deductible, item.fee)
            deductible -= ded_part
            pct = float(benefits.get(f"coverage.{item.category}") or 0)
            insurance = round((item.fee - ded_part) * pct / 100, 2)
            if insurance > max_left:
                insurance, note = round(max_left, 2), "annual max reached"
            max_left -= insurance

        lines.append(LineEstimate(cdt_code=code, fee=item.fee, covered=covered,
                                  insurance=insurance,
                                  patient=round(item.fee - insurance, 2), note=note))
    return Estimate(lines=lines)
