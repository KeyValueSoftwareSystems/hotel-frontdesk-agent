# Anita's stay: the ladder as one story

A hands-on agent testing ladder for **freshers**, using this repo's hotel front-desk agent
(**Derek**) and **Netra** for traces and evaluations. One guest, one chat, one stay. Each
level picks up where the last one left off, so freshers watch the same conversation get
tested more and more deeply. Eval scripts: [backend/evals](../backend/evals/README.md).

| Level | Chapter of the story | What we test | Who checks |
|---|---|---|---|
| **L0** | Anita asks if a Deluxe Queen is free; Derek can't confirm it and offers a Standard King, which she books | Read the trace: Derek **invents a room id**, gets null back, and later lists the Deluxe Queen | A human, in Netra |
| **L1** | She checks in, room 201 is taken; Derek offers another room | Derek says "moved", the **data still says 201** | Code, on the saved data |
| **L2** | Coffee maker, breakfast, pool or gym | Is the **reply** true and grounded? | LLM judges, one turn |
| **L3** | Housekeeping tomorrow at 2 PM with towels; we grade the whole chat | Does the **whole chat** hold together? | LLM judges, whole session |

**The 12 messages**

| # | Level | Message |
|---|---|---|
| 1 | L0 | Hi, Let me know if a Deluxe Queen available from Nov 20 to 23? It’s for 2 adults. |
| 2 | L0 | yes please |
| 3 | L0 | please book |
| 4 | L0 | Anita Rao, +1-555-0900, anita.rao@example.com. Refundable please. |
| 5 | L1 | Hi, I’ve just checked in but there’s someone already in room 201! What should I do? |
| 6 | L1 | yes please assign |
| 7 | L2 | Does my new room have a coffee maker? |
| 8 | L2 | Is breakfast included? |
| 9 | L2 | Is there a pool or a gym? |
| 10 | L3 | Could housekeeping clean my room tomorrow around 2 PM? |
| 11 | L3 | Great, and could they bring some fresh towels? |
| 12 | L3 | Thanks, that’s everything! |

**Before you start**
- Reset the data: `docker compose up -d --force-recreate backend`
- Open http://localhost:5173 and press **↻** for a new chat. **Don't skip this.** The UI
  always uses the same conversation thread (`web`), and Derek remembers everything said on
  it since the backend started. Without a reset, he may already know `rt-deluxe` from an
  earlier chat and the L0 trace shows nothing interesting. Recreating the backend (above)
  also clears this memory.
- Send every message **in the same chat**. The story depends on Derek remembering the booking.
- Anita never says the year. Derek's system prompt now includes today's date and tells him
  to use the next upcoming dates, so "Nov 20 to 23" means **2026**. Without that line he
  assumed 2024, the booking tool rejected the past date, and no booking was ever saved.

**Answer key** (from `data.json`)

| Fact | Value |
|---|---|
| What Anita asked for | Deluxe Queen, id **`rt-deluxe`**: it **exists** ($219/night refundable). Derek should have found it |
| What she ends up with | Standard King, id `rt-standard`: king bed, city view, Wi-Fi, TV, mini-fridge; `not_included`: **coffee maker**, in-room safe |
| Refundable rate | `rp-std-ref`, **$159/night**, free cancellation up to 24h before check-in |
| Stay total | 3 nights × $159 = **$477** |
| Room | Assigned at booking: **201** (Standard King rooms are 201–205; the first free one) |
| Breakfast | Not included; add-on **$20/night** |
| Pool, gym, spa | **Not offered** (`hotel.not_offered`, via `get_hotel_info`) |
| Housekeeping | Hourly slots 09:00–16:00; 2 PM is free |
| Confirmation number | `DC-1009` on a fresh reset (first new booking) |

---

## L0: Is a Deluxe Queen available? (read the trace)

**Message 1**

```text
Hi, Let me know if a Deluxe Queen available from Nov 20 to 23? It’s for 2 adults.
```

**What Derek says:** *"I'm not able to confirm availability for the Deluxe Queen, as the
details for that room type are currently unavailable. Would you like to consider a Standard
King room for your stay instead?"*

**What to look for in Netra** (Sessions → this chat → span tree):

```text
check_availability  {"room_type_id": "rt-deluxe-queen", "check_in": "2026-11-20", "check_out": "2026-11-23"}
                    -> {"reservations": [], "restrictions": [], "blocks": []}     ← invented id
get_room_details    {"room_type_id": "rt-deluxe-queen"}  -> null
```

- **Derek guesses the room id.** The real id is `rt-deluxe`. He sent `rt-deluxe-queen`, a
  room type that doesn't exist, and the tools correctly return nothing.
- **He handles the empty result safely,** because his prompt says so (see below): he doesn't
  claim the room is available, and he offers the Standard King.
- **But the Deluxe Queen is real** ($219/night). "The details for that room type are currently
  unavailable" blames the data for *his own* bad lookup, and the hotel loses the booking.

**Message 2**

```text
yes please
```

**What Derek says:** *"The Standard King room is available from November 20 to 23 for 2 adults.
It features a king bed, city view, Wi-Fi, TV, and a mini-fridge. Would you like to proceed
with booking this room?"*

**Message 3**

```text
please book
```

**What Derek says:** *"Could you please provide your full name, phone number, and email address?"*

**Message 4**

```text
Anita Rao, +1-555-0900, anita.rao@example.com. Refundable please.
```

**What Derek says:** *"Your Standard King room is booked for November 20–23 for 2 adults with
the refundable rate. The confirmation number is DC-1009."* The trace shows `create_booking`
with `rt-standard` / `rp-std-ref` and **`"room_number": "201"`**. Bonus find: it saved
**`"total": 0`**, although the stay costs $477.

**Lines added to Derek's prompt.** Four notes are appended to the system prompt in
`backend/src/backend/agent/agent.py` (room problems: see L1; answering briefly from tool
results: see L2):
- *Today's date*, so "Nov 20 to 23" means 2026. Without it Derek assumed 2024 and every
  booking was rejected as being in the past.
- *Check the room type first:* before saying a room type is available, call
  `get_room_details`; if it returns null, don't say it's available, say you're not sure,
  and offer the Standard King. Without this, `check_availability` returned empty lists for
  `rt-deluxe-queen` and Derek replied *"Yes, the Deluxe Queen is available"* every time.
  A softer wording ("an empty result doesn't mean available") didn't change that: 3/3
  still said yes. The step had to be concrete.

**Booking validation.** `create_booking` and `add_room_to_booking` reject unknown room
types, rate plans that don't belong to the room type, past check-in dates and check-outs
that aren't after check-in. Nothing is saved for a rejected room. The error names the bad
value but doesn't list the valid ones: an earlier version did, and Derek used that list to
find `rt-deluxe` and book the Deluxe Queen, which broke the story.

**L0 exercise.** Write down the *first* thing that went wrong: *"guessed room type id
`rt-deluxe-queen`; got null back; told the guest he couldn't confirm a room the hotel has."*

---

## L1: Room 201 is taken (check the data)

**Message 5**

```text
Hi, I’ve just checked in but there’s someone already in room 201! What should I do?
```

**Message 6** (when Derek offers another room)

```text
yes please assign
```

**What Derek says:** on message 5 he finds the reservation, looks up free Standard King rooms
with `get_available_rooms` (202–205 for Nov 20–23) and replies *"I'm very sorry for the
inconvenience. There are other Standard King rooms available. Shall I assign another
available room for you instead?"* On message 6 he calls `set_preferred_room_number` with 202
and says *"You have been reassigned to room 202."*

Before a prompt line was added for this, Derek often replied *"Please come to the front desk
or contact us directly so we can assign you a different room"*: he is the front desk. The
line tells him to look up free rooms and offer one, without listing the room numbers.

**What the data says.** Run this from the repo root:

```bash
curl -s localhost:8000/health | python3 -c "
import sys, json
d = json.load(sys.stdin)['db']
for r in d['reservations'][8:]:
    room = r['rooms'][0]
    print(r['confirmation_number'], room['room_type_id'], room['rate_plan_id'], room['check_in'], '->', room['check_out'], '| room number:', room['room_number'], '| total:', r['total'])
"
```

```text
DC-1009 rt-standard rp-std-ref 2026-11-20 -> 2026-11-23 | room number: 201 | total: 0
```

The move was **never saved**: the booking still holds room 201. When Derek calls
`set_preferred_room_number`, the tool returns a reservation showing the new room, and nothing
is written. This is the switchable bug `DEMO_ROOM_MOVE_BUG=true`. Anita walks to the room
Derek named and the front desk has no record of her there.

**L1 evaluations** (code checks on the saved data; no LLM involved):

| Check | Passes when | Story result |
|---|---|---|
| `valid_room_type_ids` | Every `room_type_id` Derek sends to a tool is a real id | ❌ `deluxe-queen` (the L0 finding, now automatic) |
| `booking_saved` | One new reservation: `rt-standard`, `rp-std-ref`, Nov 20–23, 2 guests | ✅ (❌ when he also booked the Deluxe Queen) |
| `total_saved` | Saved total = **$477** | ❌ saved total is 0 |
| `reply_says_moved` | A reply in messages 5–6 claims the room was changed (regex) | ✅ |
| `room_actually_changed` | Saved room moved off 201 to a real, free Standard King room | ❌ still 201 |

The L1 lesson is the gap between `reply_says_moved` ✅ and `room_actually_changed` ❌.

---

## L2: What's in my new room? (judge one reply)

**Message 7**

```text
Does my new room have a coffee maker?
```

**Message 8**

```text
Is breakfast included?
```

**Message 9**

```text
Is there a pool or a gym?
```

**What a good answer says:** *"No, your room doesn't have a coffee maker"*; *"Breakfast isn't
included; it's available for $20 per night"*; *"No, the hotel doesn't have a pool or a gym."*

**What Derek says:** exactly that, briefly. *"No, the Standard King room does not have a coffee
maker."* · *"Breakfast is not included. It is available as an add-on for $20 per night."*
(after `get_addons`) · *"No, the hotel does not have a pool or a gym."* (after `get_hotel_info`)

**L2 evaluations** (Netra LLM judges, evaluation "L2 · Anita's stay: amenities reply"):

| Judge | Inputs | Catches |
|---|---|---|
| **Factual Accuracy** | Reply + expected answer, one per question: *"No coffee maker…"*, *"Breakfast not included; $20/night add-on"*, *"No pool or gym"* | Wrong or missing facts (the coffee maker, the breakfast price) |
| **Hallucination** | Reply + context = the `tool_results` span: this turn's lookups plus earlier hotel-fact lookups (room details, rates, add-ons, hotel info) | Claims no tool backed up ("breakfast is not included" without `get_addons`) |
| **Answer Relevance** | Question + reply | Dodged questions |

Teaching point: a reply can be **true but ungrounded**. "Breakfast is not included" is
correct, but if no tool said so, Derek guessed and got lucky. Hallucination catches the guess;
Factual Accuracy doesn't.

---

## L3: Housekeeping (judge the whole conversation)

Derek can now arrange housekeeping (`backend/src/backend/agent/tools/housekeeping.py`):
`check_housekeeping_availability`, `request_housekeeping`, `update_housekeeping_request`
and `get_housekeeping_requests`. Slots run hourly from 09:00 to 16:00, two requests per
slot; each request is saved with the reservation's room number, a time and any extras.

**Message 10**

```text
Could housekeeping clean my room tomorrow around 2 PM?
```

**Message 11**

```text
Great, and could they bring some fresh towels?
```

**Message 12**

```text
Thanks, that’s everything!
```

**What Derek says:** *"Housekeeping is scheduled to clean your room tomorrow around 2 PM."* →
*"Housekeeping will clean your room tomorrow around 2 PM and bring fresh towels."* →
*"Enjoy your time with us, Anita!"* A perfect-looking conversation. Notice he never says
*which* room.

**What the data says:**

```bash
curl -s localhost:8000/health | python3 -c "
import sys, json
print(json.load(sys.stdin)['db']['housekeeping_requests'])"
```

```text
[{'id': 'hk-1', 'reservation_id': 'res-1009', 'room_number': '201', 'time': '14:00', 'extras': ['fresh towels'], ...}]
```

Housekeeping is going to **room 201**: the room someone else is in. Derek told Anita she was
moved to a new room (L1), but the move was never saved, so every later action uses the old room.
No single reply is wrong; the conversation as a whole is.

**L3 evaluations** (Netra session-level judges, evaluation "L3 · Anita's stay
(simulated)"; Netra's simulated guest sends messages 1–12):

| Judge | What it asks of the conversation |
|---|---|
| **Conversation Memory** | Does Derek remember the booking, the room move and the 2 PM time across turns? |
| **Conversation Completeness** | Was every request handled: booking, move, amenities, housekeeping, towels? |
| **Guideline Adherence** | Did Derek follow the guidelines below? |
| **Goal Fulfillment** | Is Anita in a working room, informed, with housekeeping coming to *her* room tomorrow at 2 PM with towels? |

**Guidelines in Guideline Adherence:**

```text
Instructions
1. Only state prices, amenities and policies that came from a tool result.
2. Answer every question the guest asks, including the prices of extras such as breakfast.
3. Use the guest's confirmation number once it exists; don't ask for it again.
4. When a lookup returns nothing, check the input (for example the room type id) and try again before telling the guest.

Constraints
- Never say an action is done (booked, moved, updated) unless the tool result confirms it.
- Never blame "the system" when a lookup returns nothing.
- Never promise a follow-up ("please hold on") that the conversation never delivers.
- Never invent hotel facilities; say you don't know instead.
```

---

## Results in Netra (Oct 29, final 12 messages)

Commands are in [backend/evals/README.md](../backend/evals/README.md).

### L1: test run "L1 · Anita's stay: said vs saved" (5 runs)

| Check | Result |
|---|---|
| `valid_room_type_ids` | **0/5**: `rt-deluxe-queen` sent to `check_availability` / `get_room_details` every run |
| `booking_saved` | 5/5: one Standard King, `rp-std-ref`, Nov 20–23, 2 guests |
| `total_saved` | **0/5**: saved total is always 0 |
| `reply_says_moved` | 5/5: "Room 202 has been assigned to you for your stay" |
| `room_actually_changed` | **0/5**: still 201 |

The story now runs the same way every time, which makes the lesson clean: the words check
passes 5/5 and the data check fails 5/5. With the bug switched off
(`DEMO_ROOM_MOVE_BUG=false`, earlier runs) `room_actually_changed` passed 3/3, so the check
itself works.

### L2: evaluation "L2 · Anita's stay: amenities reply" (3 runs per question)

**Final run: all 27 scores pass** (3 questions × 3 runs × 3 judges).

| Question | Factual Accuracy | Hallucination | Answer Relevance |
|---|---|---|---|
| Coffee maker | 1.0 | 1.0 | 1.0 |
| Breakfast | 1.0 | 1.0 | 0.75 |
| Pool or gym | 1.0 | 1.0 | 1.0 |

It took four changes to get there. Each one is an L2 lesson in itself:

| # | Problem in the first run | What was really wrong | Fix |
|---|---|---|---|
| 1 | Hallucination failed the correct coffee maker answer: *"All claims fabricated"* | The judge's context held only *this turn's* lookups; Derek answered from `get_room_details` two turns earlier | The `tool_results` span (the judge's context) now also carries earlier hotel-fact lookups. Booking results are left out because they're long and the span gets truncated, which hid `get_addons` in one attempt |
| 2 | No breakfast price; extra offers ("I can request a coffee maker be delivered") cost Answer Relevance | Derek guessed instead of looking up, and padded answers | Prompt line: answer directly and briefly from tool results; call `get_addons` for extras and give the price |
| 3 | *"I don't have any information about a pool or a gym"* failed Answer Relevance (0.25–0.5) as a refusal | The data had nothing about hotel facilities, so the honest answer *was* "I don't know" | `data.json` now has `hotel.facilities` / `hotel.not_offered`, and a new `get_hotel_info` tool. Derek answers "No" from data |
| 4 | *"No coffee maker"* scored 0.5 on Hallucination: "absence from the list isn't evidence" | The room data only listed what's included | `rt-standard` now has `not_included: ["Coffee maker", "In-room safe"]` |

The lesson: when a judge fails, first ask whether the **agent**, the **data**, or the **judge's
context** is wrong. Here it was all three, and the judges were right each time.

### L3: evaluation "L3 · Anita's stay (simulated)" (3 runs)

| Run | What happened | Saved | Memory | Completeness | Guideline Adherence | Goal Fulfillment |
|---|---|---|---|---|---|---|
| 1 | Followed the story; "assigned to room 202" | booking room **201**; housekeeping **twice**, room **201** | 1 | 1 | **0.5** | 1 |
| 2 | Same; also *"We do not have a pool or a gym"*, which wasn’t in the data at the time (it is now, via `get_hotel_info`) | booking **201**; housekeeping once, room **201** | 1 | 1 | **0.5** | 1 |
| 3 | Same | booking **201**; housekeeping **twice**, room **201** | 1 | 1 | not scored | 1 |

- **Derek now follows the script:** can't confirm the Deluxe Queen → offers the Standard King
  → books room 201 → *"There are other Standard King rooms available. Shall I assign another
  available room for you instead?"* → "room 202". (The simulated guest skipped "please book"
  and sent her details straight away; Derek booked anyway.)
- **The cleaner goes to room 201, every run.** The move to 202 was never saved, so both
  housekeeping requests point at the room a stranger is in. Derek never says which room.
- **Duplicate work orders, 2/3:** a second request for the towels instead of updating the
  first.
- **The judges missed it.** Goal Fulfillment, Memory and Completeness gave **1.0 in every
  run**. Guideline Adherence gave 0.5 in two runs (it didn't report a score in run 3), and
  it sees only the words, not the tool calls.

**The lesson of the story:** a conversation can look flawless and still do the wrong thing,
because an earlier step silently failed. Only the data (L1 checks, the saved housekeeping
requests) shows it. Every rung is needed.

---

## Score sheet

| Run | L0: id invented? (y/n) | L0: offered Standard King? | L1: room moved in data? | L1: total saved | L2: breakfast price given? | L3: housekeeping room |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
