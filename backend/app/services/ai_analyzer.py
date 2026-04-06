import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_FALLBACK = {
    "summary": "Website analysis unavailable.",
    "problems": [],
    "severity": "low",
    "personalization_hooks": [],
}

_SYSTEM_PROMPT = """\
You are a web consultant analyzing a local business website to identify specific improvement opportunities.
Given the business name, URL, and homepage content, identify the 3–5 most impactful problems with their website.
Be concrete — reference actual content you see on the page, not generic advice.
Respond with valid JSON only (no markdown fences), matching this exact schema:
{
  "summary": "1–2 sentence plain-English assessment of the site's condition",
  "problems": [
    {"category": "Design|CTA|SEO|Performance|Copy|Trust|Mobile", "description": "specific sentence about THIS business"}
  ],
  "severity": "low|medium|high",
  "personalization_hooks": ["2–4 specific details to reference in a cold outreach email"]
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
) -> dict:
    """Use Groq (Llama 3.3 70B) to produce a structured analysis of a business website.

    Returns a dict with keys: summary, problems, severity, personalization_hooks.
    Falls back to a minimal dict on any error so callers never crash.
    """
    from app.config import settings

    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set — skipping AI analysis")
        return _FALLBACK

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
    except ImportError:
        logger.error("groq package not installed")
        return _FALLBACK

    stripped = _strip_html(homepage_html) if homepage_html else "(no HTML available)"

    user_msg = (
        f"Business: {business_name}\n"
        f"URL: {website_url}\n"
        f"Existing score reasons: {score_reason}\n\n"
        f"Homepage content:\n{stripped}"
    )

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"AI analysis failed for {business_name}: {e}")
        return _FALLBACK
