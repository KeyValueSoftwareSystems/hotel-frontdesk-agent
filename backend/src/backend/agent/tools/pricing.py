from copy import deepcopy

from netra.decorators import task

from backend.db import get_db, save_db
from backend.settings import get_settings


def discounted_total(db: dict, reservation: dict) -> float:
    """The reservation's total after its discount code, worked out from the code's terms."""
    total = reservation.get("total", 0)
    discount = reservation.get("discount") or {}
    code = next((c for c in db["discount_codes"] if c["code"] == discount.get("code")), None)
    if discount.get("type") != "discount_code" or code is None:
        return total
    if code["type"] == "percent":
        return round(total * (1 - code["value"] / 100), 2)
    return max(round(total - code["value"], 2), 0)


@task
def apply_discount_code(reservation_id: str, code: str) -> dict | None:
    """Apply a discount code to a reservation and return it with the discounted total.

    Args:
        reservation_id: Reservation id or confirmation number.
        code: The discount code.
    """
    db = get_db()
    reservation = next(
        (r for r in db["reservations"] if reservation_id in (r["id"], r.get("confirmation_number"))),
        None,
    )
    if reservation is None:
        return None
    discount_code = next((c for c in db["discount_codes"] if c["code"] == code), None)
    if discount_code is None:
        return {"error": f"Discount code {code} not found"}
    reservation["discount"] = {"type": "discount_code", "code": code}
    new_total = discounted_total(db, reservation)
    if get_settings().demo_discount_bug:
        # L1 demo bug: only the code is saved. The new total is returned but never stored, and
        # the code is never marked used, so the saved total stays at the full price.
        save_db(db)
        return {**deepcopy(reservation), "total": new_total}
    reservation["total"] = new_total
    discount_code["used"] = True
    discount_code["used_by"] = reservation["id"]
    save_db(db)
    return reservation


@task
def apply_gift_certificate(reservation_id: str, code: str) -> dict | None:
    """Stamp a gift certificate onto a reservation."""
    db = get_db()
    reservation = next((r for r in db["reservations"] if r["id"] == reservation_id), None)
    if reservation is None:
        return None
    reservation["discount"] = {"type": "gift_certificate", "code": code}
    save_db(db)
    return reservation