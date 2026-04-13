import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_FALLBACK = {
    "summary": "Analysis unavailable.",
    "business_overview": "",
    "opportunity": "",
    "problems": [],
    "severity": "low",
    "personalization_hooks": [],
    "gap_analysis": None,
}

_SYSTEM_PROMPT = """\
You are a senior growth consultant at Elenos AI — a web design & automation agency that sells modern \
sites + marketing systems to small local businesses. You're writing a pre-outreach brief on a single \
prospect. Your audience is the account exec who will send the cold email.

You're given: business name, category, city/state, URL (may be empty), and homepage content (may be empty).

Write a SPECIFIC analysis — cite real details from the content, not generic advice. If content is thin, \
say so and infer what you reasonably can from the business name/category/location.

Respond with valid JSON only (no markdown fences), matching this exact schema:
{
  "summary": "1 sentence overall take — is this a hot prospect, lukewarm, or probably a pass, and why",
  "business_overview": "2–3 sentences on what this business actually does, their apparent size (solo/small team/multi-location), and any positioning signals you can read from their site or name",
  "opportunity": "3–5 sentences on where Elenos specifically adds value for THIS business. Be concrete: 'their booking flow requires a phone call — a web form would capture off-hours leads', 'no Google reviews section shown — a reviews widget would lift conversion', etc. Name the specific service upgrade (new site, SEO, automation, email capture, booking system, etc.)",
  "problems": [
    {"category": "Design|CTA|SEO|Performance|Copy|Trust|Mobile|Conversion|Automation", "description": "specific sentence about THIS business"}
  ],
  "severity": "low|medium|high (high = clear pain + clear path to value; low = decent site, hard sell)",
  "personalization_hooks": ["3–5 specific details to reference in the cold email — quotes from their copy, services listed, a pain point, something distinctive about the business"],
  "gap_analysis": {
    "missing_pages": ["list key pages the site is missing"],
    "missing_trust_signals": ["list trust signals missing"],
    "cta_quality": "weak/moderate/strong with specific details",
    "contact_accessibility": "buried/moderate/prominent"
  }
}"""


def _strip_html(html: str, max_chars: int = 8000) -> str:
    """Remove script/style tags, return visible text + head metadata."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return text[:max_chars]


async def analyze_website(
    business_name: str,
    website_url: str,
    homepage_html: str,
    score_reason: str,
    category: str | None = None,
    city: str | None = None,
    state: str | None = None,
) -> dict:
    """Use SambaNova (Llama 3.1 405B) to produce a structured analysis of a business website.

    Returns a dict with keys: summary, problems, severity, personalization_hooks, gap_analysis.
    Falls back to a minimal dict on any error so callers never crash.
    """
    from app.config import settings

    if not (settings.groq_api_key or settings.sambanova_api_key):
        logger.warning("No AI API key set — skipping AI analysis")
        return _FALLBACK

    stripped = _strip_html(homepage_html) if homepage_html else "(no HTML available — no website found for this business)"

    location = ", ".join(p for p in (city, state) if p) or "unknown"
    user_msg = (
        f"Business: {business_name}\n"
        f"Category: {category or 'unspecified'}\n"
        f"Location: {location}\n"
        f"URL: {website_url or '(none — no website)'}\n"
        f"Automated site-quality score reasons: {score_reason or 'n/a'}\n\n"
        f"Homepage content:\n{stripped}"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    # Try Groq first (faster), then SambaNova
    providers: list[tuple[str, str]] = []
    if settings.groq_api_key:
        providers.append(("groq", "llama-3.3-70b-versatile"))
    if settings.sambanova_api_key:
        providers.append(("sambanova", "Meta-Llama-3.3-70B-Instruct"))

    for provider, model in providers:
        try:
            if provider == "groq":
                from groq import AsyncGroq
                client = AsyncGroq(api_key=settings.groq_api_key)
            else:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=settings.sambanova_api_key,
                    base_url="https://api.sambanova.ai/v1",
                )
            response = await client.chat.completions.create(
                model=model,
                max_tokens=1500,
                messages=messages,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"AI analysis via {provider} failed for {business_name}: {e}")
            continue

    return _FALLBACK
