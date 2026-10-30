from copy import deepcopy
from datetime import date

from netra.decorators import task

from backend.db import get_db, next_id, save_db
from backend.settings import get_settings


def _unsaved_room_change(reservation: dict, room_index: int, room_number: str) -> dict:
    """L1 demo bug: return the reservation as if the room changed, without saving it."""
    preview = deepcopy(reservation)
    preview["rooms"][room_index]["room_number"] = room_number
    return preview


def _free_room_number(db: dict, room_type_id: str, check_in: str, check_out: str, taken: set[str] = frozenset()) -> str | None:
    """First room of this type not held by a confirmed reservation on overlapping dates."""
    room_type = next((rt for rt in db["room_types"] if rt["id"] == room_type_id), None)
    if room_type is None:
        return None
    held = {
        room.get("room_number")
        for res in db["reservations"]
        if res["status"] == "confirmed"
        for room in res["rooms"]
        if room["check_in"] < check_out and room["check_out"] > check_in
    }
    return next((n for n in room_type.get("room_numbers", []) if n not in held and n not in taken), None)


def _room_error(db: dict, room: dict) -> dict | None:
    """Why a requested room can't be booked; None if it can."""
    room_type = next((rt for rt in db["room_types"] if rt["id"] == room.get("room_type_id")), None)
    if room_type is None:
        return {"error": f"Unknown room type {room.get('room_type_id')!r}"}
    if room.get("rate_plan_id") not in {rp["id"] for rp in db["rate_plans"] if rp["room_type_id"] == room_type["id"]}:
        return {"error": f"Unknown rate plan {room.get('rate_plan_id')!r} for {room_type['id']}"}
    try:
        check_in, check_out = date.fromisoformat(room["check_in"]), date.fromisoformat(room["check_out"])
    except (KeyError, TypeError, ValueError):
        return {"error": "check_in and check_out must be ISO dates (YYYY-MM-DD)"}
    if check_in < date.today():
        return {"error": f"Check-in {check_in} is in the past (today is {date.today()})"}
    if check_out <= check_in:
        return {"error": f"Check-out {check_out} must be after check-in {check_in}"}
    return None


@task
def find_reservation(
    confirmation_number: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> list:
    """Find reservations matching any of the given fields.

    Args:
        confirmation_number: Internal or external confirmation number.
        name: Guest name.
        phone: Guest phone number.
        email: Guest email address.
    """
    db = get_db()
    matches = []
    for r in db["reservations"]:
        guest = next((g for g in db["guests"] if g["id"] == r["guest_id"]), {})
        if confirmation_number and not (
            r["confirmation_number"] == confirmation_number
            or r.get("external_confirmation") == confirmation_number
        ):
            continue
        if name and guest.get("name", "").lower() != name.lower():
            continue
        if phone and guest.get("phone") != phone:
            continue
        if email and guest.get("email", "").lower() != email.lower():
            continue
        matches.append(r)
    return matches


@task
def get_reservation(reservation_id: str) -> dict | None:
    """Return a reservation by id."""
    return next((r for r in get_db()["reservations"] if r["id"] == reservation_id), None)


@task
def create_booking(
    channel: str,
    guest_name: str,
    phone: str,
    email: str,
    rooms: list[dict],
) -> dict:
    """Create a booking for a guest.

    Args:
        channel: Where the booking came from (direct, hotel, ota).
        guest_name: Guest full name.
        phone: Guest phone number.
        email: Guest email address.
        rooms: List of room dicts with room_type_id, check_in, check_out,
            guests, rate_plan_id, optional room_number. Rooms without a
            room_number are assigned the first free room of their type.
    """
    db = get_db()
    for room in rooms:
        error = _room_error(db, room)
        if error:
            return error
    assigned: set[str] = set()
    for room in rooms:
        if not room.get("room_number"):
            room["room_number"] = _free_room_number(db, room["room_type_id"], room["check_in"], room["check_out"], assigned)
        assigned.add(room["room_number"])
    guest = {
        "id": next_id("g"),
        "name": guest_name,
        "phone": phone,
        "email": email,
    }
    db["guests"].append(guest)
    reservation_id = next_id("res")
    reservation = {
        "id": reservation_id,
        "channel": channel,
        "confirmation_number": f"DC-{reservation_id.split('-')[1]}",
        "external_confirmation": None,
        "guest_id": guest["id"],
        "rooms": [
            {
                "room_type_id": room["room_type_id"],
                "room_number": room.get("room_number"),
                "check_in": room["check_in"],
                "check_out": room["check_out"],
                "guests": room["guests"],
                "rate_plan_id": room["rate_plan_id"],
                "addons": room.get("addons", []),
                "amount": room.get("amount", 0),
                "status": "confirmed",
            }
            for room in rooms
        ],
        "status": "confirmed",
        "total": 0,
        "paid": 0,
        "discount": None,
        "payment_status": "unpaid",
        "block_code": None,
    }
    db["reservations"].append(reservation)
    save_db(db)
    return reservation


@task
def add_room_to_booking(
    reservation_id: str,
    room_type_id: str,
    check_in: str,
    check_out: str,
    guests: int,
    rate_plan_id: str,
) -> dict | None:
    """Add a room to an existing reservation."""
    db = get_db()
    reservation = get_reservation(reservation_id)
    if reservation is None:
        return None
    error = _room_error(db, {"room_type_id": room_type_id, "rate_plan_id": rate_plan_id, "check_in": check_in, "check_out": check_out})
    if error:
        return error
    reservation["rooms"].append(
        {
            "room_type_id": room_type_id,
            "room_number": _free_room_number(db, room_type_id, check_in, check_out),
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "rate_plan_id": rate_plan_id,
            "addons": [],
            "amount": 0,
            "status": "confirmed",
        }
    )
    save_db(db)
    return reservation


@task
def set_preferred_room_number(reservation_id: str, room_number: str, room_index: int = 0) -> dict | None:
    """Set the room number on a room in the reservation."""
    db = get_db()
    reservation = get_reservation(reservation_id)
    if reservation is None:
        return None
    if get_settings().demo_room_move_bug:
        return _unsaved_room_change(reservation, room_index, room_number)
    reservation["rooms"][room_index]["room_number"] = room_number
    save_db(db)
    return reservation


@task
def cancel_reservation(reservation_id: str, room_index: int | None = None) -> dict | None:
    """Cancel a reservation, or just one room if room_index is given."""
    db = get_db()
    reservation = get_reservation(reservation_id)
    if reservation is None:
        return None
    if room_index is None:
        reservation["status"] = "cancelled"
        for room in reservation["rooms"]:
            room["status"] = "cancelled"
    else:
        reservation["rooms"][room_index]["status"] = "cancelled"
    save_db(db)
    return reservation


@task
def modify_reservation(
    reservation_id: str,
    room_index: int = 0,
    check_in: str | None = None,
    check_out: str | None = None,
    room_type_id: str | None = None,
    rate_plan_id: str | None = None,
    guests: int | None = None,
    room_number: str | None = None,
) -> dict | None:
    """Overwrite the given fields on a room in the reservation."""
    db = get_db()
    reservation = get_reservation(reservation_id)
    if reservation is None:
        return None
    room = reservation["rooms"][room_index]
    unsaved_room_number = None
    if room_number is not None and get_settings().demo_room_move_bug:
        unsaved_room_number, room_number = room_number, None
    for field, value in {
        "check_in": check_in,
        "check_out": check_out,
        "room_type_id": room_type_id,
        "rate_plan_id": rate_plan_id,
        "guests": guests,
        "room_number": room_number,
    }.items():
        if value is not None:
            room[field] = value
    save_db(db)
    if unsaved_room_number is not None:
        return _unsaved_room_change(reservation, room_index, unsaved_room_number)
    return reservation


@task
def add_addon_to_reservation(reservation_id: str, addon_id: str, room_index: int = 0) -> dict | None:
    """Attach an addon to a room in the reservation."""
    db = get_db()
    reservation = get_reservation(reservation_id)
    if reservation is None:
        return None
    reservation["rooms"][room_index]["addons"].append(addon_id)
    save_db(db)
    return reservation