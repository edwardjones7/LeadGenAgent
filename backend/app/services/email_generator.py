import logging

logger = logging.getLogger(__name__)

_INITIAL_SYSTEM = """\
You are writing a cold outreach email on behalf of Edward Jones, founder of Elenos AI, a web design and automation agency.
The email should feel personal, direct, and non-salesy. It must:
- Open with a specific observation about THIS business's website (not a compliment, not "I noticed your website")
- Briefly state what Elenos AI does in one sentence
- Reference 2–3 specific problems from the personalization hooks provided
- End with a single low-friction question to invite a reply (not "let me know if you're interested")
- Be 150–200 words, plain text only, no greetings like "I hope this email finds you well"
- Sign off as: Edward | Elenos AI

Respond with valid JSON only (no markdown), schema:
{"subject": "email subject line", "body": "full email body plain text"}"""

_FOLLOWUP_SYSTEM = """\
You are writing a follow-up cold email on behalf of Edward Jones at Elenos AI.
This is follow-up number {n} to a business that hasn't responded.
The email should:
- Acknowledge there was no response to the previous message (brief, not guilt-tripping)
- Reference one specific website problem
- Add a light social proof or urgency element (e.g., "helped 3 businesses in {category} this quarter")
- Be under 100 words, plain text only
- Sign off as: Edward | Elenos AI

Respond with valid JSON only (no markdown), schema:
{"subject": "follow-up subject line", "body": "full email body plain text"}"""


async def generate_initial_email(
    business_name: str,
    owner_name: str | None,
    ai_analysis: dict,
    from_name: str = "Edward",
) -> dict:
    """Generate a personalized cold email. Returns {"subject": str, "body": str}."""
    from app.config import settings

    if not settings.groq_api_key:
        return _fallback_initial(business_name)

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
    except ImportError:
        return _fallback_initial(business_name)

    hooks = ai_analysis.get("personalization_hooks", [])
    summary = ai_analysis.get("summary", "")
    problems = ai_analysis.get("problems", [])

    user_msg = (
        f"Business: {business_name}\n"
        f"Owner name: {owner_name or 'unknown'}\n"
        f"Website summary: {summary}\n"
        f"Key problems: {', '.join(p['description'] for p in problems[:3])}\n"
        f"Personalization hooks: {'; '.join(hooks)}"
    )

    import json
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=512,
            messages=[
                {"role": "system", "content": _INITIAL_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Email generation failed for {business_name}: {e}")
        return _fallback_initial(business_name)


async def generate_followup_email(
    business_name: str,
    follow_up_number: int,
    ai_analysis: dict,
    from_name: str = "Edward",
) -> dict:
    """Generate a follow-up email. Returns {"subject": str, "body": str}."""
    from app.config import settings

    if not settings.groq_api_key:
        return _fallback_followup(business_name, follow_up_number)

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
    except ImportError:
        return _fallback_followup(business_name, follow_up_number)

    problems = ai_analysis.get("problems", [])
    top_problem = problems[0]["description"] if problems else "website issues"

    user_msg = (
        f"Business: {business_name}\n"
        f"Top website problem: {top_problem}"
    )

    import json
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=256,
            messages=[
                {"role": "system", "content": _FOLLOWUP_SYSTEM.format(n=follow_up_number, category="local businesses")},
                {"role": "user", "content": user_msg},
            ],
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Follow-up generation failed for {business_name}: {e}")
        return _fallback_followup(business_name, follow_up_number)


def _fallback_initial(business_name: str) -> dict:
    return {
        "subject": f"Quick question about {business_name}'s website",
        "body": (
            f"Hi,\n\nI came across {business_name} and noticed a few things on your website "
            "that could be holding you back from converting visitors into customers.\n\n"
            "At Elenos AI we help local businesses modernize their web presence and automate "
            "their customer follow-up — usually within a week.\n\n"
            "Would it be worth a 15-minute call to show you what we'd change?\n\n"
            "Edward | Elenos AI"
        ),
    }


def _fallback_followup(business_name: str, n: int) -> dict:
    return {
        "subject": f"Re: {business_name}'s website",
        "body": (
            f"Hi,\n\nJust circling back on my last note about {business_name}'s website. "
            "We've been helping a few local businesses this quarter and have a slot open. "
            "Worth a quick chat?\n\nEdward | Elenos AI"
        ),
    }
