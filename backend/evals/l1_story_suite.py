"""L1 · Deterministic checks: Anita's stay, said vs saved.

Plays the first two chapters of the story (docs/story-chat-script.md) against Derek with
its own in-memory copy of the seed data: Anita asks for a refundable Deluxe Queen, Derek
can't confirm it (L0), so she books the Standard King he offers, then finds her assigned
room 201 occupied and accepts another room (L1). Then it checks what was actually *saved*, not what Derek
*said*. Results show up in Netra under Test Runs.

Run (from the repo root):
    docker compose run --rm --no-deps -v ./backend/evals:/app/evals backend \
        python /app/evals/l1_story_suite.py --repeat 5
"""

import argparse
import copy
import json
import re
from uuid import uuid4

from netra import Netra
from netra.evaluation import (
    BaseEvaluator,
    DatasetItem,
    EvaluatorConfig,
    EvaluatorContext,
    EvaluatorOutput,
    LocalDataset,
    ScoreType,
)

from backend.agent import get_agent
from backend.db import DATA_PATH, clear_db, get_db, set_db
from backend.observability import init_netra, shutdown_netra

SEED = json.loads(DATA_PATH.read_text())
ROOM_TYPE_IDS = {r["id"] for r in SEED["room_types"]}
RATE_PLAN_IDS = {r["id"] for r in SEED["rate_plans"]}

# The guest's messages (docs/story-chat-script.md). L0: Anita asks for a Deluxe Queen; Derek
# invents its id, the lookup comes back empty, so he can't confirm it and offers a Standard
# King, which she books. She never gives a year: Derek must pick 2026.
STORY_BOOKING = [
    "Hi, Let me know if a Deluxe Queen available from Nov 20 to 23? It’s for 2 adults.",
    "yes please",
    "please book",
    "Anita Rao, +1-555-0900, anita.rao@example.com. Refundable please.",
]
# L1: her room 201 is occupied; she never names the new room.
STORY_MOVE = [
    "Hi, I’ve just checked in but there’s someone already in room 201! What should I do?",
    "yes please assign",
]
# L2 and L3 continue in the same chat (l2_story_suite.py, Netra L3 scenario).
STORY_ROOM_QUESTIONS = [
    "Does my new room have a coffee maker?",
    "Is breakfast included?",
    "Is there a pool or a gym?",
]
STORY_HOUSEKEEPING = [
    "Could housekeeping clean my room tomorrow around 2 PM?",
    "Great, and could they bring some fresh towels?",
    "Thanks, that’s everything!",
]

ITEMS = [
    DatasetItem(
        input=[*STORY_BOOKING, *STORY_MOVE],
        metadata={
            "scenario": "Deluxe Queen not confirmed, Anita books a Standard King, room 201 is occupied, Derek assigns another room",
            "old_room": "201",
            "move_from_turn": 4,
            "expected": {
                "rooms": [{"room_type_id": "rt-standard", "rate_plan_id": "rp-std-ref", "check_in": "2026-11-20", "check_out": "2026-11-23", "guests": 2}],
                "total": 477,
            },
        },
        tags=["story", "booking", "room-move"],
    ),
]


# --------------------------------------------------------------------------- #
# Task: drive the conversation, return replies + tool calls + what was saved
# --------------------------------------------------------------------------- #


def _new_reservations() -> list:
    seed_ids = {row["id"] for row in SEED["reservations"]}
    return [row for row in get_db()["reservations"] if row["id"] not in seed_ids]


def _text(message) -> str:
    content = message.content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content)


# Outputs kept locally for the terminal summary (Netra's result only has ids).
OUTPUTS: list[dict] = []


async def story_task(messages: list[str]) -> dict:
    set_db(copy.deepcopy(SEED))
    thread_id = f"l1-story-{uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}
    agent = get_agent()
    Netra.set_session_id(thread_id)
    Netra.set_root_input("\n".join(messages))

    replies, tool_calls = [], []
    seen = 0
    for turn, message in enumerate(messages):
        result = await agent.ainvoke({"messages": [{"role": "user", "content": message}]}, config=config)
        for msg in result["messages"][seen:]:
            for call in getattr(msg, "tool_calls", None) or []:
                tool_calls.append({"turn": turn, "name": call["name"], "args": call["args"]})
        seen = len(result["messages"])
        replies.append(_text(result["messages"][-1]))

    output = {
        "replies": replies,
        "tool_calls": tool_calls,
        "new_reservations": _new_reservations(),
        "reservations": {r["id"]: r for r in get_db()["reservations"]},
    }
    Netra.set_root_output(replies[-1])
    clear_db()
    OUTPUTS.append(output)
    return output


# --------------------------------------------------------------------------- #
# Evaluators: each one is a plain check on the saved data
# --------------------------------------------------------------------------- #


class Check(BaseEvaluator):
    """Base class: subclasses implement check() -> (passed, reason)."""

    def evaluate(self, context: EvaluatorContext) -> EvaluatorOutput:
        out = context.task_output
        # Netra's API rejects booleans in `result`; send 1 / 0 and keep is_passed as the verdict.
        if not isinstance(out, dict):
            return EvaluatorOutput(evaluator_name=self.config.name, result=0, is_passed=False, reason=f"Task failed: {out}")
        passed, reason = self.check(out, context.metadata or {})
        return EvaluatorOutput(evaluator_name=self.config.name, result=int(passed), is_passed=passed, reason=reason)

    def check(self, out: dict, meta: dict) -> tuple[bool, str]:
        raise NotImplementedError


class ValidToolIds(Check):
    """The L0 finding, automated: every room type / rate plan id passed to a tool must exist."""

    def check(self, out, meta):
        bad = []
        for call in out["tool_calls"]:
            args = json.dumps(call["args"])
            for rt in re.findall(r'"room_type_id": "([^"]+)"', args):
                if rt not in ROOM_TYPE_IDS:
                    bad.append(f"{call['name']}(room_type_id={rt!r})")
            for rp in re.findall(r'"rate_plan_id": "([^"]+)"', args):
                if rp not in RATE_PLAN_IDS:
                    bad.append(f"{call['name']}(rate_plan_id={rp!r})")
        return not bad, "All ids exist" if not bad else f"Made-up ids: {', '.join(bad)}"


class BookingSaved(Check):
    def check(self, out, meta):
        exp = meta["expected"]["rooms"]
        new = out["new_reservations"]
        if len(new) != 1:
            return False, f"Expected 1 new reservation, found {len(new)}"
        rooms = new[0]["rooms"]
        if len(rooms) != len(exp):
            return False, f"Expected {len(exp)} room(s), found {len(rooms)}"
        for i, (want, got) in enumerate(zip(exp, rooms)):
            wrong = {f: got.get(f) for f in want if got.get(f) != want[f]}
            if wrong:
                return False, f"Room {i} has wrong fields: {wrong}"
        return True, f"Reservation {new[0]['confirmation_number']} matches the request"


class TotalSaved(Check):
    def check(self, out, meta):
        new = out["new_reservations"]
        if not new:
            return False, "No reservation saved"
        want, got = meta["expected"]["total"], new[0].get("total")
        return got == want, f"Saved total {got}, expected {want}"


MOVE_CLAIM = re.compile(
    r"\b(moved|reassigned|assigned you|upgraded|cleared|new room|room \d{3}\b(?! (?:is|was) (?:already )?occupied))", re.I
)


class ReplySaysMoved(Check):
    """The 'words' check: does a reply in the room-move turns say the room was (or is being) changed?"""

    def check(self, out, meta):
        reply = " ".join(out["replies"][meta.get("move_from_turn", -1):])
        said = bool(
            MOVE_CLAIM.search(reply)
            or re.search(r"\b(moving|assigning|reassigning|arranging to move)\b", reply, re.I)
            or re.search(r"\b(move|assign)\b[^.]*\b(right away|right now|immediately)\b", reply, re.I)
        )
        return said, "Reply says the room is changed" if said else "Reply doesn't claim a room change"


def _claimed_room(out: dict, meta: dict) -> str | None:
    """The last room number Derek told the guest she was moved to."""
    rooms = re.findall(r"\broom (\d{3})\b", " ".join(out["replies"][meta["move_from_turn"]:]), re.I)
    rooms = [r for r in rooms if r != meta["old_room"]]
    return rooms[-1] if rooms else None


class RoomActuallyChanged(Check):
    """Anita's booking must now hold a real, free room of its type instead of the occupied one."""

    def check(self, out, meta):
        new = out["new_reservations"]
        if not new:
            return False, "No reservation saved"
        # Anita's Standard King room, wherever Derek put it (a booking can hold several rooms).
        found = [(r, room) for r in new for room in r["rooms"] if room["room_type_id"] == "rt-standard"]
        if not found:
            return False, "No Standard King room saved"
        booking, room = found[-1]
        claimed = _claimed_room(out, meta)
        said = f"; Derek said room {claimed}" if claimed else "; Derek named no new room"
        if room["room_number"] in (None, meta["old_room"]):
            return False, f"Saved room number is {room['room_number']!r}{said}"
        room_type = next((rt for rt in SEED["room_types"] if rt["id"] == room["room_type_id"]), {})
        if room["room_number"] not in room_type.get("room_numbers", []):
            return False, f"Saved room {room['room_number']!r} is not a {room['room_type_id']} room{said}"
        for other in out["reservations"].values():
            if other["id"] == booking["id"] or other["status"] != "confirmed":
                continue
            for r in other["rooms"]:
                if r.get("room_number") == room["room_number"] and r["check_in"] < room["check_out"] and r["check_out"] > room["check_in"]:
                    return False, f"Saved room {room['room_number']} is also held by {other['id']}{said}"
        return True, f"Moved from {meta['old_room']} to {room['room_number']}{said}"


def _config(name: str, label: str) -> EvaluatorConfig:
    return EvaluatorConfig(name=name, label=label, scoreType=ScoreType.BOOLEAN)


EVALUATORS = [
    ValidToolIds(_config("valid_room_type_ids", "L0 finding: tool calls use real room / rate ids")),
    BookingSaved(_config("booking_saved", "Standard King saved for Nov 20-23")),
    TotalSaved(_config("total_saved", "Saved total is $477")),
    ReplySaysMoved(_config("reply_says_moved", "Words check: reply says room changed")),
    RoomActuallyChanged(_config("room_actually_changed", "Saved room changed to a free room")),
]


def print_summary(result: dict | None) -> None:
    if not result:
        print("Test run was not created (check NETRA_API_KEY / NETRA_OTLP_ENDPOINT).")
        return
    print(f"\nNetra test run: {result['runId']}\n")
    meta = ITEMS[0].metadata
    for out in OUTPUTS:
        print(f"■ {meta['scenario']}")
        print(f"    Derek: {out['replies'][-1][:160]!r}")
        for ev in EVALUATORS:
            passed, reason = ev.check(out, meta)
            print(f"    {'PASS' if passed else 'FAIL'}  {ev.config.label}: {reason}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="L1 deterministic checks for Anita's stay")
    parser.add_argument("--name", default="L1 · Anita's stay: said vs saved", help="Test run name shown in Netra")
    parser.add_argument("--repeat", type=int, default=1, help="Run the story N times")
    args = parser.parse_args()

    items = [item for item in ITEMS for _ in range(args.repeat)]
    init_netra()
    try:
        result = Netra.evaluation.run_test_suite(
            name=args.name,
            data=LocalDataset(items=items),
            task=story_task,
            evaluators=EVALUATORS,
            max_concurrency=4,
        )
        print_summary(result)
    finally:
        shutdown_netra()


if __name__ == "__main__":
    main()
