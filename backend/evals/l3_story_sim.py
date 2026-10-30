"""L3 · Conversation-level evals: Netra plays Anita through the whole story.

The scenario and the session-level judges live in Netra (evaluation "L3 · Anita's stay
(simulated)"): Conversation Memory, Conversation Completeness, Guideline Adherence and Goal
Fulfillment. Netra's simulated guest writes every message (is a Deluxe Queen available, the
Standard King Derek offers, room 201 occupied → another room, coffee maker, breakfast, pool or
gym, then housekeeping tomorrow at 2 PM with fresh towels); this script answers as Derek with a private copy of the seed data per conversation
(DaisyTask from simulation.py).

After each turn it also records what was saved for Anita's booking and her housekeeping
request, so the summary shows the new room in Derek's words next to the saved room number,
total, and the room housekeeping will actually go to. Run the simulation
several times to get a pass rate instead of a single verdict.

Run (from the repo root):
    docker compose run --rm --no-deps -v ./backend/evals:/app/evals backend \
        python /app/evals/l3_story_sim.py --runs 3
"""

import argparse
import os
import time
from collections import defaultdict

from netra import Netra

from backend import simulation
from backend.db import clear_db, get_db
from backend.observability import init_netra, shutdown_netra
from backend.simulation import DaisyTask

EVALUATION_ID = os.getenv("NETRA_L3_STORY_EVALUATION_ID", "6bf667f1-a00d-4279-b951-9c2dca11b501")

TRANSCRIPTS: dict[str, list[dict]] = defaultdict(list)


class TrackedDaisyTask(DaisyTask):
    """DaisyTask that records each turn and what is saved for the new booking after it."""

    async def run(self, message, session_id=None, files=None, setup_context=None):
        result = await super().run(message, session_id, files, setup_context)
        seed_ids = {r["id"] for r in simulation._SEED["reservations"]}
        booked = [
            f"{r['confirmation_number']} (saved room {r['rooms'][0]['room_number']}, saved total {r['total']})"
            for r in get_db()["reservations"] if r["id"] not in seed_ids
        ]
        housekeeping = [
            f"{r['id']} (room {r['room_number']}, {r['date']} {r['time']}, extras {r['extras']})"
            for r in get_db()["housekeeping_requests"]
        ]
        TRANSCRIPTS[result.session_id].append(
            {"guest": message, "derek": result.message, "booked": booked, "housekeeping": housekeeping}
        )
        return result


def summarise(transcript: list[dict]) -> str:
    if not transcript:
        return "  (no turns recorded)"
    lines = []
    for i, t in enumerate(transcript):
        lines.append(f"    {i + 1}. Guest: {t['guest'][:90]!r}")
        lines.append(f"       Derek: {t['derek'][:140]!r}")
    booked, housekeeping = transcript[-1]["booked"], transcript[-1]["housekeeping"]
    lines.append(f"    → {'booking: ' + ', '.join(booked) if booked else 'nothing booked'}")
    lines.append(f"    → {'housekeeping: ' + ', '.join(housekeeping) if housekeeping else 'no housekeeping request saved'}")
    return "\n".join(lines)


RUN_IDS: list[str] = []


def _capture_run_ids() -> None:
    """run_simulation doesn't return the run id; record it when the run is initialised."""
    client_cls = type(Netra.simulation._client)
    initialize_run = client_cls.initialize_run

    def wrapped(self, *args, **kwargs):
        result = initialize_run(self, *args, **kwargs)
        if result and result.get("run_id"):
            RUN_IDS.append(result["run_id"])
        return result

    client_cls.initialize_run = wrapped


def print_judge_scores(run_id: str, timeout: float = 240) -> None:
    """Wait for Netra's session judges to finish, then print their scores."""
    deadline = time.time() + timeout
    while True:
        results = Netra.evaluation.get_run_results(run_id) or {}
        if results.get("evaluationStatus") == "completed" or time.time() > deadline:
            break
        time.sleep(5)
    for item in results.get("items", []):
        print(f"  Judges [{item.get('evalStatus')}]")
        for name, verdict in (item.get("evaluatorResults") or {}).items():
            mark = "PASS" if verdict.get("isPassed") else "FAIL"
            print(f"    {mark} {name.rsplit('-', 1)[0]}: {verdict.get('score')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="L3 simulated conversation: Anita's stay")
    parser.add_argument("--runs", type=int, default=3, help="How many times to run the simulation")
    parser.add_argument("--max-turns", type=int, default=14)
    parser.add_argument("--name", default="L3 · Anita's stay")
    args = parser.parse_args()

    simulation._load_seed()
    init_netra()
    _capture_run_ids()
    try:
        for i in range(1, args.runs + 1):
            TRANSCRIPTS.clear()
            result = Netra.simulation.run_simulation(
                name=f"{args.name} · run {i}",
                dataset_id=EVALUATION_ID,
                task=TrackedDaisyTask(),
                max_concurrency=1,
                max_turns=args.max_turns,
            )
            ok = bool(result and result.get("success", True))
            run_id = RUN_IDS[-1] if RUN_IDS else None
            print(f"\n■ Run {i}/{args.runs} ({'ok' if ok else 'failed'}), Netra test run: {run_id or 'see Netra → Test Runs'}")
            for transcript in TRANSCRIPTS.values():
                print(summarise(transcript))
            if run_id:
                print_judge_scores(run_id)
    finally:
        simulation._SCENARIO_DBS.clear()
        clear_db()
        shutdown_netra()


if __name__ == "__main__":
    main()
