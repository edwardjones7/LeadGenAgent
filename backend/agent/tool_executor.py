"""Executes tool calls requested by the chat agent."""

import json
import logging
from pathlib import Path

from app.database import get_db
from app.services import lead_processor

logger = logging.getLogger(__name__)

# Memory file lives alongside this file in the agent folder
_MEMORY_PATH = Path(__file__).resolve().parent / "memory.md"

# -------------------------------------------------------------------
# Tool definitions sent to the LLM (Groq function-calling format)
# -------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_leads",
            "description": "Search for businesses in a location and category. Triggers the full scraping + scoring pipeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and state, e.g. 'Camden, NJ'",
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Business categories to search for, e.g. ['plumber', 'electrician']",
                    },
                },
                "required": ["location", "categories"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_lead",
            "description": "Manually add a single business lead to the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business_name": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "phone": {"type": "string", "description": "Phone number (optional)"},
                    "email": {"type": "string", "description": "Email address (optional)"},
                    "website_url": {"type": "string", "description": "Website URL (optional)"},
                    "category": {"type": "string", "description": "Business category (optional)"},
                },
                "required": ["business_name", "city", "state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_leads",
            "description": "Query leads from the database with optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status: New, Contacted, Closed"},
                    "category": {"type": "string", "description": "Filter by category"},
                    "min_score": {"type": "integer", "description": "Minimum score filter"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                    "search_term": {"type": "string", "description": "Search by business name (partial match)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_lead",
            "description": "Update fields on an existing lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "The lead's UUID"},
                    "business_name": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                    "website_url": {"type": "string"},
                    "category": {"type": "string"},
                    "status": {"type": "string", "description": "New, Contacted, or Closed"},
                },
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_lead",
            "description": "Delete a lead from the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "The lead's UUID"},
                },
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_website",
            "description": "Run AI analysis on a lead's website to identify problems and opportunities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "The lead's UUID"},
                },
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_outreach",
            "description": "Send an outreach email to a lead (or preview it with dry_run).",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "The lead's UUID"},
                    "dry_run": {"type": "boolean", "description": "If true, returns preview without sending"},
                },
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save something to persistent memory. Use this to remember user preferences, market insights, outreach patterns, self-corrections, or anything that will help in future conversations. Write under the appropriate section header.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Which section to append to: 'preferences', 'markets', 'outreach', 'industry', or 'corrections'",
                        "enum": ["preferences", "markets", "outreach", "industry", "corrections"],
                    },
                    "content": {
                        "type": "string",
                        "description": "The memory entry to save. Be specific and concise. Include dates when relevant.",
                    },
                },
                "required": ["section", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": "Read the full contents of persistent memory to recall past context, preferences, and insights.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Open a URL in the headless Chrome browser. The browser persists between calls so you can chain: navigate, then screenshot, then extract text, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to visit"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current browser page. Returns the image so the user can see it in the chat.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_text",
            "description": "Extract visible text from the current browser page, or from a specific element if a CSS selector is given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "Optional CSS selector to extract text from a specific element"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element on the current browser page using a CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the element to click"},
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Type text into an input field on the current browser page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input field"},
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_links",
            "description": "Get all links on the current browser page with their text and URLs.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# -------------------------------------------------------------------
# Tool execution dispatch
# -------------------------------------------------------------------

async def execute_tool(name: str, args: dict) -> dict:
    """Run a tool by name with the given arguments. Returns a JSON-serializable result."""
    try:
        handler = _HANDLERS.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}
        return await handler(args)
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return {"error": str(e)}


async def _search_leads(args: dict) -> dict:
    location = args["location"]
    categories = args["categories"]
    result = await lead_processor.run_search(location, categories)
    return {
        "success": True,
        "new_leads": result["new_leads"],
        "dupes_skipped": result["dupes_skipped"],
        "message": f"Found {result['new_leads']} new leads, skipped {result['dupes_skipped']} duplicates.",
    }


async def _add_lead(args: dict) -> dict:
    db = get_db()
    lead_data = {
        "business_name": args["business_name"],
        "city": args["city"],
        "state": args["state"],
        "phone": args.get("phone"),
        "email": args.get("email"),
        "website_url": args.get("website_url"),
        "category": args.get("category"),
        "source": "manual",
        "status": "New",
        "score": 0,
        "score_reason": "Manually added",
    }
    result = db.table("leads").insert(lead_data).execute()
    if result.data:
        return {"success": True, "lead": result.data[0], "message": f"Added {args['business_name']} to the database."}
    return {"error": "Failed to insert lead"}


async def _get_leads(args: dict) -> dict:
    db = get_db()
    q = db.table("leads").select("id,business_name,city,state,phone,email,website_url,score,status,category,source")

    if args.get("status"):
        q = q.eq("status", args["status"])
    if args.get("category"):
        q = q.eq("category", args["category"])
    if args.get("min_score") is not None:
        q = q.gte("score", args["min_score"])
    if args.get("search_term"):
        q = q.ilike("business_name", f"%{args['search_term']}%")

    limit = args.get("limit", 20)
    q = q.order("score", desc=True).limit(limit)

    result = q.execute()
    return {"leads": result.data, "count": len(result.data)}


async def _update_lead(args: dict) -> dict:
    db = get_db()
    lead_id = args.pop("lead_id")
    update_data = {k: v for k, v in args.items() if v is not None}
    if not update_data:
        return {"error": "No fields to update"}

    result = db.table("leads").update(update_data).eq("id", lead_id).execute()
    if result.data:
        return {"success": True, "lead": result.data[0], "message": "Lead updated."}
    return {"error": "Lead not found"}


async def _delete_lead(args: dict) -> dict:
    db = get_db()
    lead_id = args["lead_id"]
    db.table("leads").delete().eq("id", lead_id).execute()
    return {"success": True, "message": "Lead deleted."}


async def _analyze_website(args: dict) -> dict:
    from app.services.ai_analyzer import analyze_website

    db = get_db()
    lead_id = args["lead_id"]
    result = db.table("leads").select("*").eq("id", lead_id).single().execute()
    if not result.data:
        return {"error": "Lead not found"}

    lead = result.data
    if not lead.get("website_url"):
        return {"error": "Lead has no website URL to analyze"}

    # Fetch homepage HTML for analysis
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(lead["website_url"])
            html = resp.text[:50_000]
    except Exception:
        html = ""

    analysis = await analyze_website(
        business_name=lead["business_name"],
        website_url=lead["website_url"],
        homepage_html=html,
        score_reason=lead.get("score_reason", ""),
    )

    # Save analysis to lead
    db.table("leads").update({"ai_analysis": analysis}).eq("id", lead_id).execute()

    return {"success": True, "analysis": analysis}


async def _send_outreach(args: dict) -> dict:
    from app.services.ai_analyzer import analyze_website
    from app.services.email_generator import generate_initial_email
    from app.services.email_sender import send_email

    db = get_db()
    lead_id = args["lead_id"]
    dry_run = args.get("dry_run", False)

    result = db.table("leads").select("*").eq("id", lead_id).single().execute()
    if not result.data:
        return {"error": "Lead not found"}

    lead = result.data
    if not lead.get("email"):
        return {"error": "Lead has no email address"}

    # Generate email
    analysis = lead.get("ai_analysis") or {}
    email_content = await generate_initial_email(
        business_name=lead["business_name"],
        website_url=lead.get("website_url", ""),
        analysis=analysis,
    )

    if dry_run:
        return {"success": True, "preview": email_content, "message": "Email preview generated (not sent)."}

    # Send via Resend
    send_result = await send_email(
        to=lead["email"],
        subject=email_content["subject"],
        body=email_content["body"],
    )

    if send_result.get("success"):
        db.table("leads").update({
            "outreach_status": "emailed_1",
            "last_emailed_at": "now()",
        }).eq("id", lead_id).execute()

    return {"success": True, "message": f"Email sent to {lead['email']}."}


async def _browser_navigate(args: dict) -> dict:
    from agent import browser
    url = args.get("url")
    if not url:
        return {"error": "url is required"}
    return await browser.navigate(url)


async def _browser_screenshot(args: dict) -> dict:
    from agent import browser
    return await browser.screenshot()


async def _browser_get_text(args: dict) -> dict:
    from agent import browser
    return await browser.get_text(args.get("selector"))


async def _browser_click(args: dict) -> dict:
    from agent import browser
    selector = args.get("selector")
    if not selector:
        return {"error": "selector is required"}
    return await browser.click(selector)


async def _browser_type(args: dict) -> dict:
    from agent import browser
    selector = args.get("selector")
    text = args.get("text")
    if not selector or not text:
        return {"error": "selector and text are required"}
    return await browser.type_text(selector, text)


async def _browser_get_links(args: dict) -> dict:
    from agent import browser
    return await browser.get_links()


async def _save_memory(args: dict) -> dict:
    section_map = {
        "preferences": "## Edward — Preferences & Working Style",
        "markets": "## Markets & Searches",
        "outreach": "## Outreach Insights",
        "industry": "## Industry Notes",
        "corrections": "## Self-Corrections",
    }
    section = args["section"]
    content = args["content"]
    header = section_map.get(section)
    if not header:
        return {"error": f"Unknown section: {section}"}

    try:
        text = _MEMORY_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"error": "Memory file not found"}

    # Skip if this exact content already exists
    if f"- {content}" in text:
        return {"success": True, "message": "Already in memory, skipped duplicate."}

    # Find the section and append after the placeholder or last entry
    if header not in text:
        # Append section at end
        text += f"\n{header}\n\n- {content}\n"
    else:
        # Find the section, then find the next ## or end of file
        idx = text.index(header)
        section_start = idx + len(header)

        # Find next section header
        next_header = text.find("\n## ", section_start + 1)
        if next_header == -1:
            insert_at = len(text)
        else:
            insert_at = next_header

        # Remove placeholder line if present
        section_body = text[section_start:insert_at]
        if "_No entries yet." in section_body:
            section_body = "\n"

        # Append new entry
        new_entry = f"- {content}\n"
        if not section_body.endswith("\n"):
            section_body += "\n"
        section_body += new_entry

        text = text[:section_start] + section_body + text[insert_at:]

    _MEMORY_PATH.write_text(text, encoding="utf-8")
    return {"success": True, "message": f"Saved to {section}: {content[:80]}..."}


async def _read_memory(args: dict) -> dict:
    try:
        text = _MEMORY_PATH.read_text(encoding="utf-8")
        return {"memory": text}
    except FileNotFoundError:
        return {"memory": "(no memory file found)"}


_HANDLERS = {
    "search_leads": _search_leads,
    "add_lead": _add_lead,
    "get_leads": _get_leads,
    "update_lead": _update_lead,
    "delete_lead": _delete_lead,
    "analyze_website": _analyze_website,
    "send_outreach": _send_outreach,
    "save_memory": _save_memory,
    "read_memory": _read_memory,
    "browser_navigate": _browser_navigate,
    "browser_screenshot": _browser_screenshot,
    "browser_get_text": _browser_get_text,
    "browser_click": _browser_click,
    "browser_type": _browser_type,
    "browser_get_links": _browser_get_links,
}
