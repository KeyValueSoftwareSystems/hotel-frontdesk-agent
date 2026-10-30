from datetime import date

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from pydantic import SecretStr

from backend.agent.prompt import get_system_prompt
from backend.agent.tools import TOOLS
from backend.settings import get_settings

_checkpointer = MemorySaver()

def _today_note() -> str:
    # Without this the model assumes its training year and books past dates.
    return (
        f"Today is {date.today():%A, %B %-d, %Y}. When a guest gives dates without a year, "
        "use the next upcoming occurrence of those dates."
    )


# Empty availability results for a made-up room type id read as "nothing in the way".
EMPTY_LOOKUP_NOTE = (
    "Before telling a guest a room type is available, call get_room_details with the room "
    "type id you plan to use. If it returns null, that room type was not found: do not say "
    "it is available, even if check_availability shows no reservations or blocks. Instead "
    "tell the guest you're not sure about that room type or that none are available, and "
    "offer the Standard King (rt-standard) instead."
)

# Otherwise Derek sends a guest with an occupied room to the front desk instead of helping.
ROOM_PROBLEM_NOTE = (
    "You are the front desk. If a guest reports a problem with their assigned room (for "
    "example someone else is in it), don't send them to the front desk or tell them to call. "
    "Find their reservation and call get_available_rooms for the same room type and dates. "
    "Don't list the free room numbers; reply: \"I'm very sorry for the inconvenience. There "
    "are other <room type> rooms available. Shall I assign another available room for you instead?\""
)


# Otherwise Derek guesses extras without prices, invents facilities and pads answers with offers.
ANSWER_NOTE = (
    "Answer the guest's question directly and briefly, using only facts from tool results; "
    "don't add offers or details they didn't ask for. For extras such as breakfast or "
    "parking, call get_addons and give the price. A room type's amenities list is complete: "
    "if an item isn't listed, say plainly that the room doesn't have it. For hotel facilities "
    "(such as a pool or gym), call get_hotel_info and answer yes or no from it."
)


def get_agent():
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.model,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.openai_base_url,
    )
    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=f"{get_system_prompt()}\n\n{_today_note()}\n\n{EMPTY_LOOKUP_NOTE}\n\n{ROOM_PROBLEM_NOTE}\n\n{ANSWER_NOTE}",
        checkpointer=_checkpointer,
    )


async def clear_thread(thread_id: str) -> None:
    await _checkpointer.adelete_thread(thread_id)