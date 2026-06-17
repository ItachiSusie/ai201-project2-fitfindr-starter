# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
`search_listings` loads all mock listings using `load_listings()` from the data loader, applies hard filters for price and size, then scores every remaining listing by how many of the user's keywords appear in its title, description, and style_tags. Any listing with a score of zero is dropped, and the rest are returned sorted from highest to lowest relevance.

**Input parameters:**
`description` (str) is a plain English phrase describing what the user wants, such as "vintage graphic tee" or "90s track jacket". The tool splits this into individual keywords and counts how many appear in each listing's title, description, and style_tags.

`size` (str or None) is the size string to filter by, such as "M", "S/M", or "W30". Matching is case-insensitive and uses substring matching so that "M" matches listings sized "S/M". If None, no size filtering is applied.

`max_price` (float or None) is the maximum price in dollars, inclusive. If None, no price filtering is applied.

**What it returns:**
A list of listing dicts sorted by relevance score, best match first. Each dict contains: id (str), title (str), description (str), category (str), style_tags (list of str), size (str), condition (str), price (float), colors (list of str), brand (str or None), and platform (str). Returns an empty list when nothing matches and never raises an exception.

**What happens if it fails or returns nothing:**
If the returned list is empty, the LLM reads the empty result in the messages context, writes an error reply explaining what the user can try differently (broader keywords, different size, or higher price limit), and does not call any further tools. The interaction ends there.

---

### Tool 2: suggest_outfit

**What it does:**
`suggest_outfit` sends a prompt to Groq's `llama-3.3-70b-versatile` model asking it to build 1–2 complete outfit combinations from the new thrifted item and the user's existing wardrobe. When the wardrobe contains items, the prompt lists each piece by name, category, colors, and style tags so the LLM can reference specific combinations by name. When the wardrobe is empty or has no items that share any style context with the new piece, the tool prompts the LLM for general styling advice based on the item's own style_tags and category instead.

**Input parameters:**
`new_item` (dict) is the listing dict for the thrifted item the user is considering, passed in by the LLM from the search result it received in the prior tool round.

`wardrobe` (dict) is the user's wardrobe as a dict with an "items" key containing a list of wardrobe item dicts. Each wardrobe item has id, name, category, colors, style_tags, and an optional notes field. This may be an empty wardrobe where "items" is an empty list.

**What it returns:**
A non-empty string with 1–2 outfit suggestions. When the wardrobe has items, the response names specific pieces by name. When the wardrobe is empty or has no compatible items, it gives general guidance on what type of bottoms, shoes, or outerwear would pair well with the item's vibe. If the LLM call fails at runtime, the tool returns a descriptive error message string rather than raising an exception.

**What happens if it fails or returns nothing:**
An empty wardrobe or no style-tag overlap both fall back to a general LLM suggestion rather than crashing, and the loop continues to `create_fit_card` normally. If the tool returns an empty string due to an actual LLM or runtime failure, the LLM reads that empty result in the messages context, writes a reply explaining no outfit could be suggested, and does not call `create_fit_card`.

---

### Tool 3: create_fit_card

**What it does:**
`create_fit_card` takes the outfit suggestion string and the found listing dict and asks the Groq LLM to write a short caption in the style of a real OOTD Instagram post. The prompt provides the item's title, price, and platform alongside the outfit suggestion and instructs the LLM to write something casual and first-person. The LLM temperature is set higher than in `suggest_outfit` so the output varies meaningfully each time it is called with different inputs.

**Input parameters:**
`outfit` (str) is the outfit suggestion string from `suggest_outfit`, describing the complete look. If this string is empty or whitespace-only, the tool returns a descriptive error message without calling the LLM.

`new_item` (dict) is the listing dict for the thrifted item. The tool uses its title, price, and platform fields to make the caption feel specific and grounded.

**What it returns:**
A 2–4 sentence string in casual first-person social media style. The caption names the item, mentions the price and platform once each, and captures the outfit vibe in specific terms. Each call with different inputs produces different phrasing due to the higher temperature setting.

**What happens if it fails or returns nothing:**
If the outfit parameter is empty or whitespace-only, the tool immediately returns "Unable to generate a fit card: no outfit suggestion was provided." without calling the LLM. If the LLM call itself fails, it returns a descriptive error message string. It never raises an exception.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` starts by initializing `messages` as a list and `tool_rounds` as an integer set to 0. The messages list is built with two entries in order: a `role="system"` message containing `SYSTEM_PROMPT` with the user's wardrobe serialized as JSON appended to it, then a `role="user"` message containing the user's query string.

The loop calls the Groq LLM passing `messages`, `TOOL_DEFINITIONS`, and `tool_choice="auto"`. The response is stored in `response` and the assistant message is extracted as `assistant_message = response.choices[0].message`. At the top of each iteration, check `assistant_message.tool_calls`. If it is falsy (None or empty list), break out of the loop — the LLM has produced its final text answer. If `tool_rounds >= MAX_TOOL_ROUNDS` before that happens, return a fallback string immediately without continuing.

When tool_calls are present, append the full `assistant_message` object to `messages` first — this must happen before any tool results are appended. Then iterate over each tool call in `assistant_message.tool_calls`: extract `tool_name = tool_call.function.name` and `tool_args = json.loads(tool_call.function.arguments)`, call `dispatch_tool(tool_name, tool_args)` to get a JSON string result, then append `{"role": "tool", "tool_call_id": tool_call.id, "content": tool_result}` to `messages`. After all tool calls in that round are processed, increment `tool_rounds` by 1 and loop back to call the LLM again with the updated messages.

The system prompt encodes the decision rules the LLM follows at each round. In round 1, the LLM calls `search_listings` using the description, size, and price it parses from the user query. After receiving the `role="tool"` result: if the result is an empty list, the LLM writes a final reply telling the user what to try differently and produces no further tool_calls — the loop breaks and `error` is set in the output dict. If the result contains items, the LLM calls `suggest_outfit` with `results[0]` as `new_item` and the wardrobe it read from the system prompt as `wardrobe`. After receiving the `suggest_outfit` result: if it is an empty string, the LLM writes a final reply saying no outfit could be suggested and produces no further tool_calls — the loop breaks and `error` is set. If the suggestion is a non-empty string, the LLM calls `create_fit_card` with that suggestion as `outfit` and the same item as `new_item`. After receiving the `create_fit_card` result, the LLM writes its final summary response with no further tool_calls and the loop breaks cleanly.

After the loop exits, the final text is extracted from `response.choices[0].message.content`. The code then reads back through `messages` to find every entry where `role == "tool"`, matches each one to its tool name by looking at the corresponding `tool_calls` list in the preceding assistant message using `tool_call_id`, parses the `content` field as JSON, and populates the output dict: `selected_item` gets `search_listings_result[0]`, `outfit_suggestion` gets the string from `suggest_outfit`, `fit_card` gets the string from `create_fit_card`, and `error` gets the final text content if any tool returned an empty or failure result.

---

## State Management

**How does information from one tool get passed to the next?**

State is carried by the messages list, not by a separate dictionary. When `search_listings` executes, its result is appended to `messages` as a `role="tool"` message with its `tool_call_id`. When the LLM decides to call `suggest_outfit` next, it reads the search result directly from the messages context and passes the item as an argument — the user does not re-enter anything. The same pattern repeats for `create_fit_card`: the LLM sees the `suggest_outfit` result already in context and uses it without being prompted again.

The wardrobe is injected once at the start, serialized as JSON inside the system prompt, so it is visible to the LLM for the entire interaction. There is no separate state object being maintained during the loop — the messages list is the complete record of what has happened, and the LLM uses it to decide every next action.

After the loop exits, the output dict that `app.py` reads is populated by parsing back through the messages list to extract each tool's result by `tool_call_id`. This dict is an output packaging step at the end, not a state management mechanism during the loop.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the query | The LLM reads the empty list in the messages context and writes a reply: "No listings found for your search. Try broader keywords, a different size, or a higher price limit." No further tools are called. |
| suggest_outfit | Wardrobe is empty or no style-tag overlap with the new item | The tool falls back to calling the LLM for general styling advice based on the item's style_tags and returns a non-empty string. The loop continues to `create_fit_card` normally. |
| suggest_outfit | Returns an empty string due to LLM or runtime failure | The LLM reads the empty result in context, explains no outfit could be suggested, and does not call `create_fit_card`. |
| create_fit_card | Outfit input is empty or whitespace-only | The tool returns "Unable to generate a fit card: no outfit suggestion was provided." without calling the LLM. This result appears in the fit card UI panel. |

---

## Architecture

```
User query (text + wardrobe choice)
         │
         ▼
    run_agent(query, wardrobe)
         │
         ▼
    Build messages list
      [system: SYSTEM_PROMPT + wardrobe serialized as JSON]
      [user: query text]
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│   while True  (LLM tool-call loop, max MAX_TOOL_ROUNDS)    │
│                                                            │
│   LLM call (messages + TOOL_DEFINITIONS, tool_choice=auto) │
│        │                                                   │
│        ├─ no tool_calls → break ───────────────────────┐   │
│        │                                               │   │
│        │  tool_calls present                           │   │
│        ▼                                               │   │
│   append assistant message to messages                 │   │
│        │                                               │   │
│        ▼                                               │   │
│   dispatch_tool(tool_name, tool_args)                  │   │
│   append role="tool" + tool_call_id to messages        │   │
│        │                                               │   │
│        ├─ search_listings → result = []                │   │
│        │      LLM reads empty list in context          │   │
│        │      writes error reply, no more tool_calls   │   │
│        │      → break ──────────────────────────────── ┤   │
│        │                                               │   │
│        ├─ search_listings → result = [items...]        │   │
│        │      LLM reads result, calls suggest_outfit   │   │
│        │                                               │   │
│        ├─ suggest_outfit → result = ""                 │   │
│        │      LLM reads empty string in context        │   │
│        │      writes error reply, no more tool_calls   │   │
│        │      → break ──────────────────────────────── ┤   │
│        │                                               │   │
│        ├─ suggest_outfit → result = "Pair with..."     │   │
│        │      LLM reads result, calls create_fit_card  │   │
│        │                                               │   │
│        └─ create_fit_card → result = "thrifted this..."│   │
│               LLM writes final reply, no tool_calls    │   │
│               → break ─────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
         │
         ▼
    Parse messages list → find role="tool" results by tool_call_id
         │
         ▼
    Populate output dict:
      selected_item      ← search_listings result[0]
      outfit_suggestion  ← suggest_outfit result
      fit_card           ← create_fit_card result
      error              ← set if LLM stopped early
         │
         ▼
    Return output dict → app.py renders 3 UI panels
```

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`, I will give Claude the Tool 1 block from this planning.md — the full description, input parameters, return value spec, and failure mode — and ask it to implement the function in `tools.py` using `load_listings()` from the data loader. Before running the generated code I will check that it filters by price and size before scoring, scores against title plus description plus style_tags combined, and returns an empty list rather than raising an exception when nothing matches. I will then test it with three queries: "vintage graphic tee" with no filters to confirm multiple results come back, "designer ballgown" under $5 in size XXS to confirm an empty list is returned, and "jacket" with max_price set to 10 to confirm every result is at or below that price.

For `suggest_outfit`, I will give Claude the Tool 2 block including both the empty-wardrobe fallback branch and the populated-wardrobe branch. I will verify the generated code checks `wardrobe["items"]` before building the LLM prompt and that it never returns an empty string under normal conditions. I will test it once with `get_example_wardrobe()` and once with `get_empty_wardrobe()` and confirm both return a non-empty string without raising an exception.

For `create_fit_card`, I will give Claude the Tool 3 block and ask it to set a higher LLM temperature and include a guard for the empty outfit string. I will run it three times on the same inputs and verify the outputs differ. If the outputs are identical I will ask Claude to increase the temperature until meaningful variation appears.

**Milestone 4 — Planning loop and state management:**

I will give Claude the Planning Loop section, the State Management section, and the Architecture diagram from this planning.md and ask it to implement `run_agent()` in `agent.py` and `handle_query()` in `app.py`. Before running the generated code I will verify that it builds the messages list with the system prompt and wardrobe JSON before calling the LLM, that it follows the while loop pattern from the lab with `tool_call_id` linking each tool result back to its request, that it checks for an empty search result before the LLM could call `suggest_outfit`, and that it populates the output dict by reading back through the messages after the loop ends. I will confirm state is flowing correctly by printing the `role="tool"` messages after each round and verifying the item returned in round 1 is the same one the LLM passes into round 2.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Search:**
The agent builds a messages list with the system prompt and the user's query. The LLM reads the query and calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. The tool loads all listings, drops anything priced above $30, then scores the rest by keyword overlap. It returns two matches sorted by relevance: `lst_006` — "Graphic Tee — 2003 Tour Bootleg Style" ($24, depop, good condition) as the top result, and `lst_033` — "Vintage Band Tee — Faded Grey" ($19, depop, fair condition) as second. This result is appended to `messages` as a `role="tool"` message with its `tool_call_id`.

**Step 2 — Suggest outfit:**
The LLM reads the search result in context and calls `suggest_outfit(new_item=lst_006, wardrobe=<wardrobe from system prompt>)`. The tool formats the wardrobe's 10 items into a prompt and asks the LLM to build outfit combinations. It returns: "Pair this faded bootleg tee with your baggy straight-leg jeans and chunky white sneakers for an effortless 90s streetwear look. Leave it untucked and roll the sleeves once. If it gets cold, throw the vintage black denim jacket on top — the all-black-and-faded combo is perfect." This result is appended to `messages` as a `role="tool"` message with its `tool_call_id`.

**Step 3 — Fit card:**
The LLM reads the outfit suggestion in context and calls `create_fit_card(outfit=<suggestion>, new_item=lst_006)`. The tool builds a prompt with the item's title, price, and platform alongside the outfit and asks the LLM for a casual caption at higher temperature. It returns: "thrifted this faded bootleg tee off depop for $24 and my baggy jeans have never looked better 🖤 denim jacket thrown on top and it's a full look fr". This result is appended to `messages` as a `role="tool"` message.

**Final output to user:**
The LLM has no more tool calls to make. It writes a final `role="assistant"` message summarizing all three results. The code reads back through the messages list to extract the three tool results by `tool_call_id` and populates the output dict. The Gradio UI renders the found listing in the first panel, the outfit suggestion in the second, and the fit card in the third.

---

**Error path — no results:**
If `search_listings` returns an empty list (for example, query: "designer ballgown size XXS under $5"), the LLM reads the empty result in context and writes a final reply without calling any further tools: "No listings matched your search. Try a broader description, a different size, or a higher budget." The output dict has `error` set and `outfit_suggestion` and `fit_card` both remain None.

---

### What FitFindr does (in plain English)

FitFindr takes a single natural language thrift request and runs it through an LLM tool-call loop — the same pattern as the course lab — where the LLM reads each tool result as a `role="tool"` message in the conversation history and uses that context to decide what to call next, with `search_listings` always running first, `suggest_outfit` only running if a listing was found, and `create_fit_card` only running if an outfit suggestion came back. State flows through the messages list itself rather than a separate store, and the system prompt encodes the decision rules so the LLM knows when to stop early instead of passing empty data downstream. After the loop ends, the tool results are read back out of the messages by `tool_call_id` and packaged into the output dict that the Gradio UI uses to populate the three panels.
