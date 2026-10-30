from netra import Netra

from backend.settings import get_settings

PROMPT_NAME = "Front Desk Assistant"

SYSTEM_PROMPT = """You are Default, the front desk assistant for a hotel.

You help guests check room availability and rates, book and find reservations,
cancel or change bookings, apply discounts, handle payments, generate invoices,
resend confirmations, arrange housekeeping, and answer questions about door
access.

Use the provided tools to look up and update information. Keep responses
concise and accurate.
"""


def get_system_prompt() -> str:
    prompt = Netra.prompts.get_prompt(
        name=PROMPT_NAME,
        label=get_settings().netra_prompt_label,
    )
    for message in prompt.get("messages", []):
        if message.get("role") == "system" and message.get("content"):
            return message["content"]
    return SYSTEM_PROMPT