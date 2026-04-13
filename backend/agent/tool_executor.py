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
    {
        "type": "function",
        "function": {
            "name": "bulk_send_outreach",
            "description": "Send outreach emails to multiple leads matching filters. Respects daily rate limits. Skips ineligible leads (no email, bounced, opted out, replied, max follow-ups). Returns summary of sent/skipped/errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_score": {
                        "type": "integer",
                        "description": "Minimum lead score to include (e.g. 7)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by business category (optional)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by CRM status: New, Contacted (optional)",
                    },
                    "location": {
                        "type": "string",
                        "description": "Filter by city name (optional, partial match)",
                    },
                    "max_count": {
                        "type": "integer",
                        "description": "Max emails to send this batch (default 50)",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, returns list of leads that would be emailed without actually sending",
                    },
                },
                "required": ["min_score"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_outreach_status",
            "description": "Get a summary of the outreach campaign: how many leads emailed, opened, replied, bounced, pending follow-up, and today's send count.",
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
            "name": "update_outreach_config",
            "description": "Update outreach automation settings: rate limits, follow-up delays, toggle smart scheduling on/off, set minimum score for auto-send.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_per_hour": {"type": "integer", "description": "Max emails per hour"},
                    "max_per_day": {"type": "integer", "description": "Max emails per day"},
                    "followup_1_days": {"type": "integer", "description": "Days before first follow-up"},
                    "followup_2_days": {"type": "integer", "description": "Days before second follow-up"},
                    "followup_3_days": {"type": "integer", "description": "Days before third follow-up"},
                    "smart_schedule_enabled": {"type": "boolean", "description": "Enable/disable autonomous smart scheduling"},
                    "min_score_auto": {"type": "integer", "description": "Minimum score for auto-scheduled outreach"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_emails",
            "description": "Deep email search for leads that are missing emails. Searches the business website, Google, Yelp, BBB, Yellow Pages, and tries common email patterns. Can target a specific lead by ID or find emails for all leads missing them (up to 20 at a time).",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "string",
                        "description": "Optional — a specific lead's UUID to find email for. If omitted, finds emails for all leads missing them.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max leads to process when doing bulk search (default 20)",
                    },
                },
                "required": [],
            },
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
    from app.services.outreach_engine import send_outreach_to_lead

    db = get_db()
    lead_id = args["lead_id"]
    dry_run = args.get("dry_run", False)

    result = db.table("leads").select("*").eq("id", lead_id).single().execute()
    if not result.data:
        return {"error": "Lead not found"}

    lead = result.data
    send_result = await send_outreach_to_lead(lead, dry_run=dry_run)

    if dry_run and send_result.get("success"):
        return {
            "success": True,
            "preview": {"subject": send_result["subject"], "body": send_result["body"]},
            "message": "Email preview generated (not sent).",
        }

    if send_result.get("success"):
        return {"success": True, "message": f"Email sent to {lead['email']}."}

    return {"error": send_result.get("error", "Send failed")}


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


async def _bulk_send_outreach(args: dict) -> dict:
    from app.services.outreach_engine import bulk_send, is_lead_eligible

    db = get_db()
    min_score = args["min_score"]
    category = args.get("category")
    status = args.get("status")
    location = args.get("location")
    max_count = args.get("max_count", 50)
    dry_run = args.get("dry_run", False)

    # Build query for matching leads
    q = db.table("leads").select("*").gte("score", min_score).not_.is_("email", "null")
    if category:
        q = q.eq("category", category)
    if status:
        q = q.eq("status", status)
    if location:
        q = q.ilike("city", f"%{location}%")

    q = q.order("score", desc=True).limit(max_count)
    result = q.execute()
    leads = result.data or []

    if not leads:
        return {"success": True, "message": "No leads match the filters.", "sent": 0, "total": 0}

    if dry_run:
        eligible = []
        skipped_reasons: dict[str, int] = {}
        for lead in leads:
            ok, reason = is_lead_eligible(lead)
            if ok:
                eligible.append(f"{lead['business_name']} ({lead['email']}) — score {lead['score']}")
            else:
                skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
        return {
            "success": True,
            "dry_run": True,
            "would_send": len(eligible),
            "would_skip": len(leads) - len(eligible),
            "skipped_reasons": skipped_reasons,
            "leads": eligible[:20],
            "message": f"Would send to {len(eligible)} leads, skip {len(leads) - len(eligible)}",
        }

    # Actually send
    send_result = await bulk_send(leads, delay_seconds=72.0)
    send_result["success"] = True
    send_result["message"] = f"Sent {send_result['sent']} emails, skipped {send_result['skipped']}, {send_result['errors']} errors"
    return send_result


async def _get_outreach_status(args: dict) -> dict:
    from app.services.outreach_engine import get_daily_send_count, get_outreach_config

    db = get_db()

    # Count leads by outreach status
    try:
        all_leads = db.table("leads").select("outreach_status,replied", count="exact").not_.is_("email", "null").execute()
        leads_data = all_leads.data or []
    except Exception:
        leads_data = []

    status_counts: dict[str, int] = {}
    replied_count = 0
    for lead in leads_data:
        s = lead.get("outreach_status", "idle")
        status_counts[s] = status_counts.get(s, 0) + 1
        if lead.get("replied"):
            replied_count += 1

    # Count email statuses
    try:
        emails = db.table("email_outreach").select("status").execute()
        email_data = emails.data or []
    except Exception:
        email_data = []

    email_status_counts: dict[str, int] = {}
    for e in email_data:
        s = e.get("status", "unknown")
        email_status_counts[s] = email_status_counts.get(s, 0) + 1

    daily_sends = await get_daily_send_count()
    config = await get_outreach_config()

    return {
        "success": True,
        "leads_with_email": len(leads_data),
        "lead_outreach_status": status_counts,
        "replied": replied_count,
        "email_statuses": email_status_counts,
        "total_emails_sent": len(email_data),
        "today_sends": daily_sends,
        "daily_cap": config["max_per_day"],
        "smart_schedule_enabled": config["smart_schedule_enabled"],
        "min_score_auto": config["min_score_auto"],
    }


async def _update_outreach_config(args: dict) -> dict:
    db = get_db()
    allowed_fields = {
        "max_per_hour", "max_per_day",
        "followup_1_days", "followup_2_days", "followup_3_days",
        "smart_schedule_enabled", "min_score_auto",
    }
    updates = {k: v for k, v in args.items() if k in allowed_fields and v is not None}
    if not updates:
        return {"error": "No valid fields to update"}

    # Get existing config row
    existing = db.table("outreach_config").select("id").limit(1).execute()
    if not existing.data:
        # Create default row first
        db.table("outreach_config").insert({}).execute()
        existing = db.table("outreach_config").select("id").limit(1).execute()

    config_id = existing.data[0]["id"]
    result = db.table("outreach_config").update(updates).eq("id", config_id).execute()
    if result.data:
        return {"success": True, "config": result.data[0], "message": f"Updated: {', '.join(updates.keys())}"}
    return {"error": "Failed to update config"}


async def _find_emails(args: dict) -> dict:
    from app.services.email_extractor import find_email_for_lead, bulk_find_emails

    db = get_db()
    lead_id = args.get("lead_id")
    limit = args.get("limit", 20)

    if lead_id:
        # Single lead
        result = db.table("leads").select("*").eq("id", lead_id).single().execute()
        if not result.data:
            return {"error": "Lead not found"}
        lead = result.data
        if lead.get("email"):
            return {"success": True, "message": f"Lead already has email: {lead['email']}", "email": lead["email"]}

        found = await find_email_for_lead(
            business_name=lead["business_name"],
            city=lead["city"],
            state=lead["state"],
            website_url=lead.get("website_url"),
            phone=lead.get("phone"),
        )
        if found["email"]:
            db.table("leads").update({"email": found["email"]}).eq("id", lead_id).execute()
            return {
                "success": True,
                "email": found["email"],
                "source": found["source"],
                "message": f"Found {found['email']} via {found['source']} for {lead['business_name']}",
            }
        return {"success": False, "message": f"Could not find email for {lead['business_name']}", "source": "not_found"}

    else:
        # Bulk — find emails for all leads missing them
        result = (
            db.table("leads")
            .select("id,business_name,city,state,phone,website_url,email")
            .is_("email", "null")
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        leads = result.data or []
        if not leads:
            return {"success": True, "message": "All leads already have emails!", "found": 0, "total": 0}

        results = await bulk_find_emails(leads)

        found_count = 0
        details = []
        for r in results:
            if r.get("email"):
                db.table("leads").update({"email": r["email"]}).eq("id", r["lead_id"]).execute()
                found_count += 1
                # Find the lead name for the message
                lead_name = next((l["business_name"] for l in leads if l["id"] == r["lead_id"]), "Unknown")
                details.append(f"{lead_name}: {r['email']} ({r['source']})")

        return {
            "success": True,
            "found": found_count,
            "total": len(leads),
            "message": f"Found emails for {found_count}/{len(leads)} leads",
            "details": details,
        }


_HANDLERS = {
    "search_leads": _search_leads,
    "add_lead": _add_lead,
    "get_leads": _get_leads,
    "update_lead": _update_lead,
    "delete_lead": _delete_lead,
    "analyze_website": _analyze_website,
    "send_outreach": _send_outreach,
    "bulk_send_outreach": _bulk_send_outreach,
    "get_outreach_status": _get_outreach_status,
    "update_outreach_config": _update_outreach_config,
    "save_memory": _save_memory,
    "read_memory": _read_memory,
    "browser_navigate": _browser_navigate,
    "browser_screenshot": _browser_screenshot,
    "browser_get_text": _browser_get_text,
    "browser_click": _browser_click,
    "browser_type": _browser_type,
    "browser_get_links": _browser_get_links,
    "find_emails": _find_emails,
}
