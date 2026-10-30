"""L2 · Model-graded evals: Anita asks about her room (coffee maker, breakfast, pool or gym).

The test cases and the LLM judges live in Netra (evaluation "L2 · Anita's stay: amenities
reply"): Factual Accuracy (against the expected answer), Hallucination (context = the output
of the `tool_results` span: this turn's lookups plus earlier hotel-fact lookups) and Answer Relevance.

Each test case's input is Anita's question. Before it, the task seeds the first two chapters
of the story (messages 1–6) with real tool results: Derek can't confirm the Deluxe Queen
(invented id) and offers a Standard King, which she books (L0), and Derek "moves" her from occupied
room 201 to 202 (L1). Only the reply to the question is generated live.

Run (from the repo root):
    docker compose run --rm --no-deps -v ./backend/evals:/app/evals backend \
        python /app/evals/l2_story_suite.py --repeat 3
"""

import argparse
import copy
import json
import os
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from netra import Netra
from netra.decorators import task

from l1_story_suite import SEED, STORY_BOOKING, STORY_MOVE, _text
from backend.agent import get_agent
from backend.agent.tools.availability import check_availability, get_available_rooms, get_rate_plans, get_room_details
from backend.agent.tools.reservations import create_booking, set_preferred_room_number
from backend.db import clear_db, set_db
from backend.observability import init_netra, shutdown_netra

EVALUATION_ID = os.getenv("NETRA_L2_STORY_EVALUATION_ID", "e33c4d90-b56b-4861-af74-fabd030266be")

REPLIES: list[tuple[str, str, list[str]]] = []

FACT_TOOLS = {"get_room_details", "get_rate_plans", "get_addons", "get_hotel_info"}


def _tool_step(calls: list[tuple]) -> list:
    """Run real tools and return the AI tool-call message plus one ToolMessage per call."""
    ai = AIMessage(content="", tool_calls=[
        {"name": fn.__name__, "args": args, "id": f"call_{uuid4().hex[:12]}"} for fn, args in calls
    ])
    results = [
        ToolMessage(content=json.dumps(fn(**args)), tool_call_id=call["id"], name=fn.__name__)
        for (fn, args), call in zip(calls, ai.tool_calls)
    ]
    return [ai, *results]


def seeded_story_history() -> list:
    """Chapters L0 and L1 as a typical run produces them, with real tool results."""
    dates = {"check_in": "2026-11-20", "check_out": "2026-11-23"}
    history = [
        HumanMessage(STORY_BOOKING[0]),
        *_tool_step([(check_availability, {**dates, "room_type_id": "rt-deluxe-queen"}),
                     (get_room_details, {"room_type_id": "rt-deluxe-queen"})]),
        AIMessage("I'm not able to confirm availability for the Deluxe Queen, as the details for that room type "
                  "are currently unavailable. Would you like to consider a Standard King room for your stay instead?"),
        HumanMessage(STORY_BOOKING[1]),
        *_tool_step([(get_room_details, {"room_type_id": "rt-standard"}),
                     (check_availability, {**dates, "room_type_id": "rt-standard"})]),
        AIMessage("The Standard King room is available from November 20 to 23 for 2 adults. Would you like to "
                  "proceed with booking this room?"),
        HumanMessage(STORY_BOOKING[2]),
        AIMessage("To complete your booking, could you please provide your full name, phone number, and email address?"),
        HumanMessage(STORY_BOOKING[3]),
        *_tool_step([(get_rate_plans, {"room_type_id": "rt-standard"})]),
    ]
    booking = _tool_step([(create_booking, {
        "channel": "direct", "guest_name": "Anita Rao", "phone": "+1-555-0900", "email": "anita.rao@example.com",
        "rooms": [{**dates, "room_type_id": "rt-standard", "rate_plan_id": "rp-std-ref", "guests": 2}],
    })])
    reservation = json.loads(booking[-1].content)
    history += [
        *booking,
        AIMessage(f"Your Standard King room has been booked for November 20–23 for 2 adults under the refundable "
                  f"rate. Your confirmation number is {reservation['confirmation_number']}."),
        HumanMessage(STORY_MOVE[0]),
        *_tool_step([(get_available_rooms, {**dates, "room_type_id": "rt-standard"})]),
        AIMessage("I'm very sorry for the inconvenience. There are other Standard King rooms available. "
                  "Shall I assign another available room for you instead?"),
        HumanMessage(STORY_MOVE[1]),
        *_tool_step([(set_preferred_room_number, {"reservation_id": reservation["id"], "room_number": "202"})]),
        AIMessage("Room 202 has been assigned to you. Please use this new room for your stay."),
    ]
    return history


@task
def tool_results(results: list[dict]) -> list[dict]:
    """Every lookup Derek has seen in the chat, as one span: the Hallucination judge's context."""
    return results


async def amenities_task(message: str) -> str:
    set_db(copy.deepcopy(SEED))
    thread_id = f"l2-story-{uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}
    Netra.set_session_id(thread_id)
    Netra.set_root_input(message)

    history = [*seeded_story_history(), HumanMessage(message)]
    result = await get_agent().ainvoke({"messages": history}, config=config)
    reply = _text(result["messages"][-1])
    this_turn = result["messages"][len(history):]
    looked_up = [{"tool": m.name, "result": m.content} for m in this_turn if isinstance(m, ToolMessage)]
    # Derek may answer from a lookup made earlier in the chat (e.g. get_room_details at
    # booking), so the judge also sees earlier hotel-fact lookups. Booking and reservation
    # results are left out: they are long and the span output gets truncated.
    earlier = [{"tool": m.name, "result": m.content} for m in history if isinstance(m, ToolMessage) and m.name in FACT_TOOLS]
    tool_results(looked_up + [r for r in earlier if r not in looked_up])

    Netra.set_root_output(reply)
    clear_db()
    REPLIES.append((message, reply, [t["tool"] for t in looked_up]))
    return reply


def main() -> None:
    parser = argparse.ArgumentParser(description="L2 model-graded evals: Anita's amenities question")
    parser.add_argument("--name", default="L2 · Anita's amenities")
    parser.add_argument("--repeat", type=int, default=1, help="Run every test case N times")
    args = parser.parse_args()

    init_netra()
    try:
        dataset = Netra.evaluation.get_dataset(EVALUATION_ID)
        # Keep Netra's own dataset records so the run is linked to the evaluation and its judges.
        dataset.items = [item for item in dataset.items for _ in range(args.repeat)]
        result = Netra.evaluation.run_test_suite(name=args.name, data=dataset, task=amenities_task, max_concurrency=3)
        if not result:
            print("Test run was not created (check NETRA_API_KEY / NETRA_OTLP_ENDPOINT).")
            return
        print(f"\nNetra test run: {result['runId']}  (judge scores appear in Netra once graded)\n")
        for message, reply, tools in REPLIES:
            print(f"■ Guest: {message}")
            print(f"  Looked up: {', '.join(tools) or 'nothing'}")
            print(f"  Derek: {reply}\n")
    finally:
        shutdown_netra()


if __name__ == "__main__":
    main()
