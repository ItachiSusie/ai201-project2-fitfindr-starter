"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _request_llm_text(prompt: str, temperature: float, purpose: str) -> str:
    """Call Groq and return non-empty text, otherwise return a descriptive error."""
    try:
        client = _get_groq_client()
    except ValueError as exc:
        return f"Unable to generate {purpose}: {exc}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
    except Exception as exc:  # Groq client errors are runtime/network dependent
        return f"Unable to generate {purpose} right now: {exc}"

    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        return f"Unable to generate {purpose}: model returned empty output."

    return content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    filtered = listings

    if max_price is not None:
        filtered = [item for item in filtered if item.get("price", float("inf")) <= max_price]

    if size is not None and size.strip():
        normalized_size = size.strip().lower()
        filtered = [
            item
            for item in filtered
            if normalized_size in str(item.get("size", "")).lower()
        ]

    if not filtered:
        return []

    keywords = re.findall(r"[a-z0-9]+", description.lower())
    if not keywords:
        return []

    scored: list[tuple[int, dict]] = []
    for item in filtered:
        searchable_text = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("description", "")),
                " ".join(item.get("style_tags", [])),
            ]
        ).lower()
        score = sum(1 for kw in keywords if kw in searchable_text)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    wardrobe_items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
    item_title = new_item.get("title", "this item")
    item_category = new_item.get("category", "unknown category")
    item_colors = ", ".join(new_item.get("colors", [])) or "unknown colors"
    item_style_tags = new_item.get("style_tags", [])
    item_style_tags_text = ", ".join(item_style_tags) if item_style_tags else "unspecified style"

    if not wardrobe_items:
        prompt = (
            "You are a stylist helping a thrift shopper.\n"
            f"New item: {item_title}\n"
            f"Category: {item_category}\n"
            f"Colors: {item_colors}\n"
            f"Style tags: {item_style_tags_text}\n\n"
            "The user currently has an empty wardrobe record. Suggest practical, general styling advice "
            "for how to wear this piece. Include what type of bottoms, shoes, and outerwear pair well. "
            "Write 2-4 sentences in a friendly tone."
        )
        return _request_llm_text(prompt, temperature=0.7, purpose="an outfit suggestion")

    normalized_item_tags = {tag.lower() for tag in item_style_tags}
    compatible_items: list[dict] = []
    for wardrobe_item in wardrobe_items:
        wardrobe_tags = {tag.lower() for tag in wardrobe_item.get("style_tags", [])}
        if normalized_item_tags & wardrobe_tags:
            compatible_items.append(wardrobe_item)

    if not compatible_items:
        prompt = (
            "You are a stylist helping a thrift shopper.\n"
            f"New item: {item_title}\n"
            f"Category: {item_category}\n"
            f"Colors: {item_colors}\n"
            f"Style tags: {item_style_tags_text}\n\n"
            "The user's wardrobe items do not strongly match this style. Give general, practical styling "
            "advice instead of forcing bad matches. Suggest what types of pieces they should pair with this "
            "item. Write 2-4 sentences in a friendly tone."
        )
        return _request_llm_text(prompt, temperature=0.7, purpose="an outfit suggestion")

    wardrobe_lines = []
    for wardrobe_item in wardrobe_items:
        name = wardrobe_item.get("name", "Unnamed item")
        category = wardrobe_item.get("category", "unknown category")
        colors = ", ".join(wardrobe_item.get("colors", [])) or "unknown colors"
        tags = ", ".join(wardrobe_item.get("style_tags", [])) or "no style tags"
        wardrobe_lines.append(f"- {name} ({category}, colors: {colors}, style: {tags})")

    prompt = (
        "You are a stylist helping a thrift shopper.\n"
        f"New item: {item_title}\n"
        f"Category: {item_category}\n"
        f"Colors: {item_colors}\n"
        f"Style tags: {item_style_tags_text}\n\n"
        "User wardrobe items:\n"
        f"{chr(10).join(wardrobe_lines)}\n\n"
        "Suggest 1-2 complete outfit combinations that use the new item and specific wardrobe pieces by name. "
        "Write 2-4 sentences in a friendly tone."
    )
    return _request_llm_text(prompt, temperature=0.7, purpose="an outfit suggestion")


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Unable to generate a fit card: no outfit suggestion was provided."

    item_title = new_item.get("title", "a thrifted piece")
    item_price = new_item.get("price", "unknown")
    item_platform = new_item.get("platform", "a resale platform")

    prompt = (
        "Write a short social caption for a thrift outfit post.\n\n"
        f"New item title: {item_title}\n"
        f"New item price: ${item_price}\n"
        f"New item platform: {item_platform}\n"
        f"Outfit suggestion: {outfit}\n\n"
        "Requirements:\n"
        "1) 2-4 sentences.\n"
        "2) Casual first-person tone like a real OOTD post.\n"
        "3) Mention the item name, price, and platform naturally once each.\n"
        "4) Mention the outfit vibe with specific language.\n"
        "5) Avoid sounding like a product listing."
    )

    return _request_llm_text(prompt, temperature=1.1, purpose="a fit card")
