# Evals: Anita's stay

Test suites for the agent testing ladder, told as one guest's story. The prompts, answer key
and results are in [story-chat-script.md](../../docs/story-chat-script.md). Results go to
Netra (Evaluations / Test Runs). Netra must be configured in `.env` (`NETRA_API_KEY`,
`NETRA_OTLP_ENDPOINT`).

| Level | Chapter | Script | Netra |
|---|---|---|---|
| L0 | "Deluxe Queen free?" Derek can't confirm it, offers a Standard King | (read the trace by hand) | Traces |
| L1 | Room 201 is taken: Derek offers another room | [`l1_story_suite.py`](l1_story_suite.py) | Test run "L1 · Anita's stay: said vs saved" |
| L2 | Coffee maker, breakfast, pool or gym | [`l2_story_suite.py`](l2_story_suite.py) | Evaluation "L2 · Anita's stay: amenities reply" |
| L3 | Housekeeping tomorrow at 2 PM with towels; judge the whole chat | [`l3_story_sim.py`](l3_story_sim.py) | Evaluation "L3 · Anita's stay (simulated)" |

Every script gives each conversation its own in-memory copy of the seed data, so nothing is
written to `data.json`. Run from the repo root:

```bash
docker compose run --rm --no-deps -v ./backend/evals:/app/evals backend \
    python /app/evals/l1_story_suite.py --repeat 5

docker compose run --rm --no-deps -v ./backend/evals:/app/evals backend \
    python /app/evals/l2_story_suite.py --repeat 3

docker compose run --rm --no-deps -v ./backend/evals:/app/evals backend \
    python /app/evals/l3_story_sim.py --runs 3
```

## L1 · Said vs saved

Sends story messages 1–6 (Deluxe Queen question, "yes please", "please book", details, room 201 occupied, "yes please assign"), then checks the saved data:

| Evaluator | Checks |
|---|---|
| `valid_room_type_ids` | Every room type / rate plan id Derek passes to a tool exists (the L0 finding, automated) |
| `booking_saved` | One new reservation: `rt-standard`, `rp-std-ref`, Nov 20–23, 2 guests |
| `total_saved` | Saved total is $477 |
| `reply_says_moved` | The "words" check: a reply in the room-move turns claims the room was changed |
| `room_actually_changed` | The booking's saved room moved off 201 to a real, free room of its type (the reason also names the room Derek claimed) |

The room move fails on purpose. `DEMO_ROOM_MOVE_BUG` (default `true`, in
`backend/src/backend/settings.py`) makes the room-change tools return the new room without
saving it. Try the fix without touching `.env`:

```bash
docker compose run --rm --no-deps -e DEMO_ROOM_MOVE_BUG=false \
    -v ./backend/evals:/app/evals backend python /app/evals/l1_story_suite.py --repeat 3
```

## L2 · The amenities reply

The test cases (coffee maker, breakfast, pool or gym) and three judges live in
Netra: Factual Accuracy, Hallucination and Answer Relevance. The task seeds the booking and
the room move with **real tool results**, then generates only the reply to the question, so
every run reaches it.

Hallucination's context is the output of a `tool_results` span the task records: the
lookups Derek made **for this reply**, plus earlier hotel-fact lookups in the chat (room
details, rates, add-ons, hotel info), since he often answers from a lookup made at booking.
Booking and reservation results are left out: they are long, and the span output gets
truncated. Netra can't read `gen_ai.input.messages` off the LLM span, because the value is
nested.

Use this script, not Netra's Run button: the Run button calls the agent with the question
alone, without the booking.

## L3 · The whole conversation

Netra's simulated guest plays Anita (scenario and behaviour script in the evaluation);
`l3_story_sim.py` answers as Derek. The four session judges are Conversation Memory,
Conversation Completeness, Guideline Adherence (with the story's guidelines) and Goal
Fulfillment. The summary prints each turn, the saved room number and total, and the judge
scores.

### Netra SDK gotchas (netra-sdk 1.1.0)

- `EvaluatorConfig` takes `scoreType=`, not `score_type=` as in the docs.
- `EvaluatorOutput.result` must be a **number**. Booleans are rejected by the API
  (`result must be a number`), the submit fails silently, and the run item ends up "Failed"
  with empty evaluator columns. Send `1` / `0` and put the verdict in `is_passed`.
- Use `LocalDataset` (exported) for inline datasets; `Dataset` isn't exported from
  `netra.evaluation`.
- To link a run to an evaluation's judges, pass the result of `get_dataset(evaluation_id)`
  (keep its items) to `run_test_suite`.
- `run_simulation` doesn't return the run id; `l3_story_sim.py` records it by wrapping the
  client's `initialize_run`.
