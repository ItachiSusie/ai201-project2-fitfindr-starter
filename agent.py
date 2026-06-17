"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """Extract description, optional size, and optional max_price from the query."""
    original = query.strip()
    working = original

    max_price = None
    price_match = re.search(
        r"\b(?:under|below|max(?:imum)?|up to)\s*\$?\s*(\d+(?:\.\d+)?)\b",
        working,
        flags=re.IGNORECASE,
    )
    if price_match:
        max_price = float(price_match.group(1))
        working = re.sub(
            r"\b(?:under|below|max(?:imum)?|up to)\s*\$?\s*\d+(?:\.\d+)?\b",
            " ",
            working,
            flags=re.IGNORECASE,
        )

    size = None
    size_patterns = [
        r"\bsize\s*[:\-]?\s*([A-Za-z0-9/]+(?:\s*L\d{1,2})?)\b",
        r"\bin\s+size\s*([A-Za-z0-9/]+(?:\s*L\d{1,2})?)\b",
    ]
    for pattern in size_patterns:
        size_match = re.search(pattern, working, flags=re.IGNORECASE)
        if size_match:
            size = size_match.group(1).strip()
            working = re.sub(pattern, " ", working, flags=re.IGNORECASE)
            break

    description = re.sub(r"\s+", " ", working).strip(" ,.-")
    if not description:
        description = original

    return {"description": description, "size": size, "max_price": max_price}


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    session["parsed"] = _parse_query(query)
    description = session["parsed"]["description"]
    size = session["parsed"]["size"]
    max_price = session["parsed"]["max_price"]

    session["search_results"] = search_listings(
        description=description,
        size=size,
        max_price=max_price,
    )

    if not session["search_results"]:
        session["error"] = (
            f'No listings matched "{description}". '
            "Try broader keywords, a different size, or a higher budget."
        )
        return session

    session["selected_item"] = session["search_results"][0]

    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )

    if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
        session["error"] = (
            "Could not generate an outfit suggestion for this item. "
            "Try a different search or add more wardrobe details."
        )
        return session

    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
