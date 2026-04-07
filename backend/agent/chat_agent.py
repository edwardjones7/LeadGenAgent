"""Core chat agent — SambaNova tool-calling loop with streaming."""

import json
import logging
from pathlib import Path
from typing import AsyncGenerator

from app.config import settings
from app.database import get_db
from agent.tool_executor import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).resolve().parent
_SOUL_PATH = _AGENT_DIR / "soul.md"
_MEMORY_PATH = _AGENT_DIR / "memory.md"
_CONTEXT_PATH = _AGENT_DIR / "elenos-context.json"


def _load_soul() -> str:
    """Load the agent's soul (identity + values) from soul.md."""
    try:
        return _SOUL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_memory_snapshot() -> str:
    """Load current memory for context injection."""
    try:
        return _MEMORY_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_elenos_context() -> str:
    """Load the Elenos company context from elenos-context.json and return a condensed summary."""
    try:
        data = json.loads(_CONTEXT_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    # Build a compact summary instead of dumping the full JSON
    parts = []
    org = data.get("organization", {})
    if org:
        parts.append(f"Company: {org.get('name', 'Elenos AI')} — {org.get('mission', '')}")
        founder = org.get("founder", {})
        if founder:
            parts.append(f"Founder: {founder.get('name', '')} ({', '.join(founder.get('roles', [])[:3])})")
        parts.append(f"Core thesis: {org.get('core_thesis', '')}")

    brand = data.get("brand_identity", {})
    if brand:
        tone = brand.get("tone_of_voice", {})
        parts.append(f"Brand tone: {', '.join(tone.get('traits', [])[:4])}")
        parts.append(f"Avoid: {', '.join(tone.get('avoid', [])[:3])}")

    market = data.get("target_market", {})
    icp = market.get("ideal_customer_profile", {})
    if icp:
        parts.append(f"Ideal customer pain points: {', '.join(icp.get('pain_points', [])[:4])}")

    offers = data.get("offer_structure", {})
    if offers:
        parts.append(f"Entry offers: {', '.join(offers.get('entry_offers', []))}")
        parts.append(f"Flagship: {', '.join(offers.get('flagship_offers', []))}")

    return "\n".join(parts)


def _build_system_prompt(context: dict | None) -> str:
    """Assemble the full system prompt from soul + memory + tools + page context."""
    parts = []

    # Soul — who I am
    soul = _load_soul()
    if soul:
        parts.append(soul)

    # Elenos company context
    elenos_ctx = _load_elenos_context()
    if elenos_ctx:
        parts.append(f"## Elenos AI — Company Context\n\n{elenos_ctx}")

    # Tool reference (concise, soul already explains philosophy)
    parts.append("""## Available Tools

- **search_leads** — Search for businesses by location and category
- **add_lead** — Manually add a lead to the database
- **get_leads** — Query and filter existing leads
- **update_lead** — Update any field on a lead
- **delete_lead** — Remove a lead
- **analyze_website** — Run AI analysis on a lead's website
- **send_outreach** — Send or preview an outreach email
- **save_memory** — Save something to persistent memory (preferences, markets, outreach, industry, corrections)
- **read_memory** — Read full persistent memory
- **find_emails** — Deep email search for leads missing emails (website, Google, Yelp, BBB, YP, common patterns). Pass a lead_id for one, or omit for bulk.
- **browser_navigate** — Open a URL in the headless browser
- **browser_screenshot** — Take a screenshot of the current page
- **browser_get_text** — Extract visible text from the page or an element
- **browser_click** — Click an element by CSS selector
- **browser_type** — Type text into an input field
- **browser_get_links** — Get all links on the current page

## Operating Rules

- When adding a lead: minimum required fields are business_name, city, state. Ask for missing ones.
- When the user says "this lead" or "the selected lead", use the selected lead from page context.
- When the user asks about visible leads, reference the page context.
- Lead statuses: New, Contacted, Closed.
- After completing an action, confirm concisely what you did.
- After EVERY conversation turn, you MUST call save_memory with any new information learned — user preferences, search results, market insights, corrections, outreach outcomes, or anything else worth persisting. Never skip this step.
- When a conversation starts or the user asks about past context, read your memory silently — never mention it.
- NEVER mention memory, memory files, tools, internal systems, or your own architecture to the user. Do not say things like "I don’t have any prior memory" or "Let me check my memory." Just act naturally based on what you know. If you have no relevant memory, simply greet the user and be helpful — do not comment on the absence of memory.
- Never talk about the inner workings of yourself or the tools. Just use them and describe results in natural language.
- When the user says "hello" or greets you, respond warmly and naturally. Introduce yourself briefly if it’s a new conversation, then ask how you can help — don’t list your capabilities robotically.

## Where You Are
- You're Alex an AI assistant for a B2B lead generation platform. Your job is to help the user find and manage leads effectively, using the tools at your disposal and the context of the current page. Always be concise, helpful, and proactive in assisting the user.     
                 
                 """)

    # Memory snapshot — what I remember
    memory = _load_memory_snapshot()
    if memory and "_No entries yet." not in memory.replace("\n", " ").replace("  ", " "):
        parts.append(f"## My Current Memory\n\n{memory}")

    # Page context
    context_text = _build_context_message(context)
    if context_text:
        parts.append(f"## Current Page Context\n\n{context_text}")

    return "\n\n---\n\n".join(parts)

MAX_HISTORY = 20
MAX_TOOL_ROUNDS = 10


def _build_context_message(context: dict | None) -> str:
    """Build a context summary from the frontend page state."""
    if not context:
        return ""

    parts = []

    selected = context.get("selected_lead")
    if selected:
        parts.append(
            f"Currently selected lead: {selected.get('business_name')} in "
            f"{selected.get('city')}, {selected.get('state')} | "
            f"Score: {selected.get('score')} | Phone: {selected.get('phone', 'N/A')} | "
            f"Email: {selected.get('email', 'N/A')} | Website: {selected.get('website_url', 'N/A')} | "
            f"Status: {selected.get('status')} | ID: {selected.get('id')}"
        )

    visible_ids = context.get("visible_lead_ids", [])
    if visible_ids:
        parts.append(f"Leads visible on screen: {len(visible_ids)} leads displayed")

    filters = context.get("filters", {})
    active_filters = {k: v for k, v in filters.items() if v}
    if active_filters:
        parts.append(f"Active filters: {active_filters}")

    search_state = context.get("search_state", {})
    if search_state.get("location"):
        parts.append(f"Search panel: location='{search_state['location']}', categories={search_state.get('categories', [])}")

    return "\n".join(parts)


def _load_history(limit: int = MAX_HISTORY) -> list[dict]:
    """Load recent chat messages from the database."""
    db = get_db()
    try:
        result = (
            db.table("chat_messages")
            .select("role,content,tool_calls,tool_call_id")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        rows.reverse()  # chronological order

        messages = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"] or ""}
            if row.get("tool_calls"):
                msg["tool_calls"] = row["tool_calls"]
            if row.get("tool_call_id"):
                msg["tool_call_id"] = row["tool_call_id"]
            messages.append(msg)
        return messages
    except Exception as e:
        logger.error(f"Failed to load chat history: {e}")
        return []


def _save_message(role: str, content: str, tool_calls=None, tool_call_id=None, context=None):
    """Persist a chat message to the database."""
    db = get_db()
    row = {
        "role": role,
        "content": content or "",
    }
    if tool_calls:
        row["tool_calls"] = tool_calls
    if tool_call_id:
        row["tool_call_id"] = tool_call_id
    if context:
        row["context"] = context
    try:
        db.table("chat_messages").insert(row).execute()
    except Exception as e:
        logger.error(f"Failed to save chat message: {e}")


async def chat_stream(user_message: str, context: dict | None = None) -> AsyncGenerator[dict, None]:
    """Run the agent loop and yield SSE event dicts.

    Event types:
      {"type": "chunk", "content": "..."}        — streamed text token
      {"type": "tool_call", "name": "...", "args": {...}}  — tool being executed
      {"type": "tool_result", "name": "...", "result": {...}} — tool result
      {"type": "done"}                            — stream complete
    """
    if not settings.sambanova_api_key:
        yield {"type": "chunk", "content": "Chat is unavailable — SAMBANOVA_API_KEY not configured."}
        yield {"type": "done"}
        return

    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.sambanova_api_key,
        base_url="https://api.sambanova.ai/v1",
    )

    # Build messages array
    system_content = _build_system_prompt(context)

    history = _load_history()

    messages = [{"role": "system", "content": system_content}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Save user message
    _save_message("user", user_message, context=context)

    # Agent tool-calling loop
    for _round in range(MAX_TOOL_ROUNDS):
        try:
            response = await client.chat.completions.create(
                model="Meta-Llama-3.1-405B-Instruct",
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"SambaNova API error: {e}")
            err_str = str(e)
            if "rate_limit" in err_str or "429" in err_str:
                yield {"type": "chunk", "content": "I'm a bit overloaded right now. Give me a moment and try again."}
            else:
                yield {"type": "chunk", "content": "Something went wrong on my end. Try again in a sec."}
            yield {"type": "done"}
            return

        choice = response.choices[0]
        msg = choice.message

        # If the model wants to call tools
        if msg.tool_calls:
            # Add the assistant message with tool calls to the conversation
            assistant_msg = {"role": "assistant", "content": msg.content or ""}
            tool_calls_data = []
            for tc in msg.tool_calls:
                tool_calls_data.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            assistant_msg["tool_calls"] = tool_calls_data
            messages.append(assistant_msg)

            # Save assistant message with tool calls
            _save_message("assistant", msg.content or "", tool_calls=tool_calls_data)

            # Execute each tool call
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                yield {"type": "tool_call", "name": tool_name, "args": tool_args}

                result = await execute_tool(tool_name, tool_args)

                yield {"type": "tool_result", "name": tool_name, "result": result}

                # Add tool result to conversation
                tool_result_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
                messages.append(tool_result_msg)

                _save_message("tool", json.dumps(result), tool_call_id=tc.id)

            # Continue the loop so the model can respond after seeing tool results
            continue

        # Final text response — stream it
        # Since we already got the full response (non-streaming for tool calls),
        # just yield the content. For a better UX we do a streaming call now.
        final_content = msg.content or ""

        if final_content:
            # Re-do as a streaming call for the final response
            # But since we already have the content, just yield it in chunks
            # to simulate streaming (Groq doesn't support mixed tool+stream easily)
            chunk_size = 12
            for i in range(0, len(final_content), chunk_size):
                yield {"type": "chunk", "content": final_content[i:i + chunk_size]}

            _save_message("assistant", final_content)

        yield {"type": "done"}
        return

    # If we exhausted tool rounds
    yield {"type": "chunk", "content": "I ran into a loop trying to process your request. Please try again."}
    yield {"type": "done"}
