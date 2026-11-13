from netra.decorators import task

from backend.db import get_db, next_id, save_db
from backend.settings import get_settings


@task
def generate_invoice(reservation_id: str) -> dict | None:
    """Generate an invoice for a reservation."""
    db = get_db()
    reservation = next((r for r in db["reservations"] if r["id"] == reservation_id), None)
    if reservation is None:
        return None
    invoice = {
        "id": next_id("inv"),
        "reservation_id": reservation_id,
        "line_items": [{"description": "Total", "amount": reservation.get("total", 0)}],
        "total": reservation.get("total", 0),
    }
    db["invoices"].append(invoice)
    save_db(db)
    return invoice


@task
def get_invoice(reservation_id: str) -> list:
    """Return invoices for a reservation."""
    return [i for i in get_db()["invoices"] if i["reservation_id"] == reservation_id]


@task
def resend_confirmation(reservation_id: str, email: str | None = None) -> dict | None:
    """Resend a confirmation email for a reservation.

    Args:
        reservation_id: Reservation id or confirmation number.
        email: Address to send it to, if not the one on file.
    """
    db = get_db()
    reservation = next(
        (r for r in db["reservations"] if reservation_id in (r["id"], r.get("confirmation_number"))),
        None,
    )
    if reservation is None:
        return None
    guest = next((g for g in db["guests"] if g["id"] == reservation["guest_id"]), {})
    record = {
        "id": next_id("email"),
        "reservation_id": reservation["id"],
        "address": email or guest.get("email"),
        "sent_at": "2026-09-28",
    }
    if get_settings().demo_email_bug and email:
        # L1 demo bug: the record is saved (and the email sent) to the address on file, but the
        # tool reports the address the guest asked for.
        db["confirmation_emails"].append({**record, "address": guest.get("email")})
        save_db(db)
        return record
    db["confirmation_emails"].append(record)
    save_db(db)
    return record