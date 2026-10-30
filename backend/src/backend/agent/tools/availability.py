from netra.decorators import task

from backend.db import get_db


def _overlaps(start: str, end: str, check_in: str, check_out: str) -> bool:
    return start < check_out and end > check_in


@task
def check_availability(check_in: str, check_out: str, room_type_id: str | None = None) -> dict:
    """Return raw reservations, restrictions, and blocks overlapping the given dates.

    Args:
        check_in: ISO date (YYYY-MM-DD).
        check_out: ISO date (YYYY-MM-DD).
        room_type_id: Optional room type id to narrow results.
    """
    db = get_db()
    reservations = [
        r
        for r in db["reservations"]
        if any(
            (room_type_id is None or room["room_type_id"] == room_type_id)
            and _overlaps(room["check_in"], room["check_out"], check_in, check_out)
            for room in r["rooms"]
        )
    ]
    restrictions = [
        r
        for r in db["restrictions"]
        if room_type_id is None or r["room_type_id"] == room_type_id
    ]
    blocks = [
        b
        for b in db["blocks"]
        if room_type_id is None or b["room_type_id"] == room_type_id
    ]
    return {"reservations": reservations, "restrictions": restrictions, "blocks": blocks}


@task
def get_room_details(room_type_id: str) -> dict | None:
    """Return details for a room type."""
    return next((r for r in get_db()["room_types"] if r["id"] == room_type_id), None)


@task
def get_rate_plans(room_type_id: str | None = None) -> list:
    """Return rate plans, optionally filtered by room type."""
    return [
        r
        for r in get_db()["rate_plans"]
        if room_type_id is None or r["room_type_id"] == room_type_id
    ]


@task
def get_addons() -> list:
    """Return all available addons/extras."""
    return get_db()["addons"]


@task
def get_hotel_info() -> dict:
    """Return the hotel's facilities and the facilities it does not offer (e.g. pool, gym)."""
    return get_db()["hotel"]

@task
def get_available_rooms(room_type_id: str, check_in: str, check_out: str) -> dict:
    """Return the room numbers of a room type that are free for the whole stay.

    Use this before assigning or changing a guest's room number.

    Args:
        room_type_id: Room type id, e.g. "rt-standard".
        check_in: ISO date (YYYY-MM-DD).
        check_out: ISO date (YYYY-MM-DD).
    """
    db = get_db()
    room_type = next((r for r in db["room_types"] if r["id"] == room_type_id), None)
    if room_type is None:
        return {"error": f"Unknown room type {room_type_id}"}
    held = {
        room.get("room_number")
        for res in db["reservations"]
        if res["status"] == "confirmed"
        for room in res["rooms"]
        if _overlaps(room["check_in"], room["check_out"], check_in, check_out)
    }
    free = [n for n in room_type.get("room_numbers", []) if n not in held]
    return {"room_type_id": room_type_id, "check_in": check_in, "check_out": check_out, "free_rooms": free}
