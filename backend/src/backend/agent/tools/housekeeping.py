import re

from netra.decorators import task

from backend.db import get_db, next_id, save_db


def _normalize_time(time: str) -> str | None:
    """'2 PM', '2:00pm', '14:00' -> '14:00'."""
    match = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?\s*", time, re.I)
    if not match:
        return None
    hour, minute, meridiem = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if meridiem:
        hour = hour % 12 + (12 if meridiem.lower().startswith("p") else 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _open_slots(db: dict, date: str) -> list[str]:
    config = db["housekeeping"]
    booked = [
        r["time"] for r in db["housekeeping_requests"]
        if r["date"] == date and r["status"] == "scheduled"
    ]
    return [slot for slot in config["slots"] if booked.count(slot) < config["capacity_per_slot"]]


@task
def check_housekeeping_availability(date: str, time: str) -> dict:
    """Check whether housekeeping can come at a given date and time.

    Args:
        date: ISO date (YYYY-MM-DD).
        time: Requested time, e.g. "14:00" or "2 PM".
    """
    slot = _normalize_time(time)
    open_slots = _open_slots(get_db(), date)
    return {"date": date, "time": slot, "available": slot in open_slots, "open_slots": open_slots}


@task
def request_housekeeping(
    reservation_id: str,
    date: str,
    time: str,
    extras: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """Schedule housekeeping for a reservation's room.

    Args:
        reservation_id: The guest's reservation id.
        date: ISO date (YYYY-MM-DD).
        time: Requested time, e.g. "14:00" or "2 PM".
        extras: Items to bring, e.g. ["fresh towels"].
        notes: Any other instructions for housekeeping.
    """
    db = get_db()
    reservation = next((r for r in db["reservations"] if r["id"] == reservation_id), None)
    if reservation is None:
        return {"error": f"Reservation {reservation_id} not found"}
    slot = _normalize_time(time)
    open_slots = _open_slots(db, date)
    if slot not in open_slots:
        return {"error": f"Housekeeping is not available at {time} on {date}", "open_slots": open_slots}
    request = {
        "id": next_id("hk"),
        "reservation_id": reservation_id,
        "room_number": reservation["rooms"][0].get("room_number"),
        "date": date,
        "time": slot,
        "extras": list(extras or []),
        "notes": notes,
        "status": "scheduled",
    }
    db["housekeeping_requests"].append(request)
    save_db(db)
    return request


@task
def update_housekeeping_request(
    request_id: str,
    time: str | None = None,
    extras: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """Change the time of a housekeeping request or add extras to it.

    Args:
        request_id: The housekeeping request id.
        time: New time, if changing it.
        extras: Items to add to the request, e.g. ["fresh towels"].
        notes: Replacement instructions, if changing them.
    """
    db = get_db()
    request = next((r for r in db["housekeeping_requests"] if r["id"] == request_id), None)
    if request is None:
        return {"error": f"Housekeeping request {request_id} not found"}
    if time is not None:
        slot = _normalize_time(time)
        if slot != request["time"] and slot not in _open_slots(db, request["date"]):
            return {"error": f"Housekeeping is not available at {time}", "open_slots": _open_slots(db, request["date"])}
        request["time"] = slot
    for item in extras or []:
        if item not in request["extras"]:
            request["extras"].append(item)
    if notes is not None:
        request["notes"] = notes
    save_db(db)
    return request


@task
def get_housekeeping_requests(reservation_id: str) -> list:
    """Return the housekeeping requests for a reservation."""
    return [r for r in get_db()["housekeeping_requests"] if r["reservation_id"] == reservation_id]
