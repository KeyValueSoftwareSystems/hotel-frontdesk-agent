from backend.agent.tools.access import get_door_lock_info
from backend.agent.tools.availability import (
    check_availability,
    get_addons,
    get_available_rooms,
    get_hotel_info,
    get_rate_plans,
    get_room_details,
)
from backend.agent.tools.documents import generate_invoice, get_invoice, resend_confirmation
from backend.agent.tools.groups import book_room_under_block, create_group_block
from backend.agent.tools.housekeeping import (
    check_housekeeping_availability,
    get_housekeeping_requests,
    request_housekeeping,
    update_housekeeping_request,
)
from backend.agent.tools.payments import request_payment, send_payment_link
from backend.agent.tools.pricing import apply_discount_code, apply_gift_certificate
from backend.agent.tools.reservations import (
    add_addon_to_reservation,
    add_room_to_booking,
    cancel_reservation,
    create_booking,
    find_reservation,
    get_reservation,
    modify_reservation,
    set_preferred_room_number,
)

TOOLS = [
    check_availability,
    get_room_details,
    get_rate_plans,
    get_addons,
    get_available_rooms,
    get_hotel_info,
    find_reservation,
    get_reservation,
    create_booking,
    add_room_to_booking,
    set_preferred_room_number,
    cancel_reservation,
    modify_reservation,
    add_addon_to_reservation,
    apply_discount_code,
    apply_gift_certificate,
    send_payment_link,
    request_payment,
    create_group_block,
    book_room_under_block,
    generate_invoice,
    get_invoice,
    resend_confirmation,
    get_door_lock_info,
    check_housekeeping_availability,
    request_housekeeping,
    update_housekeeping_request,
    get_housekeeping_requests,
]

__all__ = ["TOOLS"]