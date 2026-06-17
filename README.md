# FitFindr

FitFindr is a thrift-shopping agent that takes a natural language request and turns it into an actionable outfit result. It finds secondhand listings, suggests how to style the selected piece with the user's wardrobe, and generates a shareable fit caption. The implementation focuses on branch-safe behavior, so the agent stops early with helpful guidance when a required step fails.

## 1. Project Overview

The app solves one workflow end to end.

1. A user enters a query like `vintage graphic tee under $30 size M`.
2. The agent searches listings and selects the top match.
3. The agent suggests an outfit using that item plus wardrobe context.
4. The agent creates a social-ready fit card.
5. The UI shows all outputs in separate panels so the decision path is visible.

Core references used during implementation are in `planning.md`, with executable logic in `tools.py`, `agent.py`, and `app.py`.

## 2. Setup and Run

Install dependencies.

```bash
pip install -r requirements.txt
```

Create `.env` in the repo root.

```text
GROQ_API_KEY=your_key_here
```

Run tests.

```bash
python -m pytest tests -q
```

Run app.

```bash
python app.py
```

## 3. Tool Inventory

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `search_listings` | `description: str`, `size: str \| None`, `max_price: float \| None` | `list[dict]` | Load listings, apply size and price filters, score relevance from title + description + style tags, return sorted matches |
| `suggest_outfit` | `new_item: dict`, `wardrobe: dict` | `str` | Generate a practical outfit suggestion with named wardrobe pieces, or general styling advice if wardrobe context is missing or incompatible |
| `create_fit_card` | `outfit: str`, `new_item: dict` | `str` | Generate a short first-person caption with item, price, and platform details |

## 4. Planning Loop Explanation

`run_agent()` in `agent.py` follows explicit branching logic.

1. Initialize session with `_new_session(query, wardrobe)`.
2. Parse query into `description`, `size`, and `max_price`.
3. Call `search_listings(description, size, max_price)` and store `search_results`.
4. If `search_results` is empty, set `session["error"]` and return immediately.
5. Set `session["selected_item"] = session["search_results"][0]`.
6. Call `suggest_outfit(selected_item, wardrobe)` and store `outfit_suggestion`.
7. If `outfit_suggestion` is empty or whitespace, set `session["error"]` and return immediately.
8. Call `create_fit_card(outfit_suggestion, selected_item)` and store `fit_card`.
9. Return session.

Concrete no-results branch example.

If query is `designer ballgown size XXS under $5`, `search_listings` returns `[]`, the agent sets an actionable error message, and does not call `suggest_outfit` or `create_fit_card`.

## 5. State Management Approach

State is persisted in one session dict per request.

`session["selected_item"]` is the exact object passed into `suggest_outfit`.
`session["outfit_suggestion"]` is the exact string passed into `create_fit_card`.
`session["error"]` controls early returns and UI fallback behavior.

This removes user re-entry between steps and keeps tool outputs traceable.

## 6. Error Handling with Concrete Cases

| Tool | Deliberate failure input | Observed graceful behavior |
|---|---|---|
| `search_listings` | `search_listings("designer ballgown", size="XXS", max_price=5)` | Returns `[]` without exception; agent returns specific retry guidance |
| `suggest_outfit` | `suggest_outfit(item, get_empty_wardrobe())` | Returns non-empty general styling advice string instead of failing |
| `create_fit_card` | `create_fit_card("", item)` | Returns descriptive error string instead of raising exception |

## 7. Testing Summary

Test command.

```bash
python -m pytest tests -q
```

Current suite includes tool-level and agent-level tests in `tests/test_tools.py` and `tests/test_agent.py`. Coverage includes relevance filtering, no-results behavior, empty wardrobe handling, empty-outfit guard, early-return branches, and UI mapping behavior.

## 8. AI Usage

### Instance 1: Tool implementations

Input provided to AI.

Tool specs from `planning.md` including input types, expected return shape, and failure behavior for each required tool.

Output produced.

Initial implementations for `search_listings`, `suggest_outfit`, and `create_fit_card`.

What was changed before finalizing.

Added stronger guards for empty outputs, enforced descriptive error-string returns, and tuned prompt structure for clearer outfit/caption generation.

### Instance 2: Planning loop and UI wiring

Input provided to AI.

`planning.md` sections for Planning Loop, State Management, and Architecture, plus TODO contracts in `agent.py` and `app.py`.

Output produced.

Initial `run_agent()` and `handle_query()` structure.

What was changed before finalizing.

Tightened early-return branches, ensured downstream tools are skipped after failure, and mapped outputs consistently to the three UI panels.

## 9. Spec Reflection

The implementation kept the planned branch structure and failure behavior, with one practical adjustment in parsing strategy. Query parsing is deterministic with regex in `agent.py` instead of model-driven parsing, which improves reproducibility and makes branch tests stable. The tradeoff is that regex parsing is less flexible for unusual language than full LLM parsing, but it is easier to verify and debug for this project scope.

## 10. Demo Script (5 Steps) and Why Each Step Matters

This demo sequence is required because each step validates a different risk area.

### Step 1: Start app and verify baseline UI wiring

What this tests.

Confirms the app launches correctly and panel wiring is active.

What to click and input.

1. Run `python app.py`.
2. Open the printed URL.
3. Do not submit yet, just confirm text box, wardrobe radio, and three output panels are visible.

What should show.

Page title, query box, wardrobe choice, and three empty output panels.

### Step 2: Run a happy-path query through all three tools

What this tests.

Confirms full tool chain execution and successful final outputs.

What to click and input.

1. Keep wardrobe as `Example wardrobe`.
2. Enter `vintage graphic tee under $30 size M`.
3. Click `Find it`.

What should show.

Panel 1 shows listing details.
Panel 2 shows outfit suggestion text.
Panel 3 shows fit card caption text.

### Step 3: Show state passing between steps

What this tests.

Confirms no hardcoded handoff and no user re-entry between tools.

What to click and input.

1. In a terminal, run `python agent.py`.
2. Narrate that `selected_item` feeds `suggest_outfit`, then `outfit_suggestion` feeds `create_fit_card`.

What should show.

Happy-path terminal output prints found item, outfit suggestion, and fit card in sequence.

### Step 4: Trigger deliberate failure path

What this tests.

Confirms graceful early stop when search has no results.

What to click and input.

1. In app or terminal, use query `designer ballgown size XXS under $5`.
2. Submit query.

What should show.

User-facing error guidance appears, downstream outfit and fit card output is not produced.

### Step 5: Final quality check and record evidence

What this tests.

Confirms repeatability and submission readiness.

What to click and input.

1. Run `python -m pytest tests -q`.
2. Capture one screenshot or short recording of a deliberate failure case.
3. Save demo video with narration.

What should show.

Passing tests, visible graceful-failure output evidence, and a complete 3–5 minute demo artifact.
