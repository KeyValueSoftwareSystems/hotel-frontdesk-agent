from netra.decorators import task

from backend.agent.tools.pricing import discounted_total
from backend.db import get_db, next_id, save_db
from backend.settings import get_settings


@task
def send_payment_link(reservation_id: str, phone: str, landline_check: bool = False) -> dict:
    """Send a payment link to a phone number.

    Args:
        reservation_id: The reservation to collect payment for.
        phone: Phone number to send the link to.
        landline_check: Whether the number was verified not to be a landline.
    """
    db = get_db()
    link = {
        "id": next_id("plink"),
        "reservation_id": reservation_id,
        "phone": phone,
        "status": "pending",
    }
    db["payment_links"].append(link)
    save_db(db)
    return link


@task
def request_payment(reservation_id: str) -> dict | None:
    """Return the amount due for a reservation.

    Args:
        reservation_id: Reservation id or confirmation number.
    """
    reservation = next(
        (
            r
            for r in get_db()["reservations"]
            if reservation_id in (r["id"], r.get("confirmation_number"))
        ),
        None,
    )
    if reservation is None:
        return None
    total = reservation.get("total", 0)
    if get_settings().demo_discount_bug:
        # L1 demo bug: the amount due is worked out from the discount code on the fly, so the
        # guest sees the discounted total even though the saved total was never changed.
        total = discounted_total(get_db(), reservation)
    paid = reservation.get("paid", 0)
    return {
        "reservation_id": reservation_id,
        "total": total,
        "paid": paid,
        "balance_due": total - paid,
    }