import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a web designer and copywriter creating a complete website brief for a local business.
Given the business details, produce a structured website spec with compelling, specific copy.
Do not use generic placeholder text — write actual headlines and copy for this specific business.
Respond with valid JSON only (no markdown fences), matching this exact schema:
{
  "business_name": "string",
  "tagline": "short punchy tagline (under 8 words)",
  "hero_headline": "main H1 headline",
  "hero_subheadline": "1–2 sentence subheadline",
  "sections": [
    {
      "name": "section name (e.g. Services, About, Why Us, Testimonials, Contact)",
      "headline": "section headline",
      "body_copy": "2–3 sentences of body copy",
      "cta_text": "call to action button text or null"
    }
  ],
  "color_palette": {
    "primary": "#hex",
    "secondary": "#hex",
    "accent": "#hex"
  },
  "design_direction": "1 sentence describing the visual style",
  "seo_title": "SEO page title (under 60 chars)",
  "meta_description": "meta description (under 155 chars)",
  "suggested_domain": "suggested domain name without TLD"
}
Include 4–5 sections. Make colors appropriate for the business category."""


async def generate_website_spec(
    business_name: str,
    category: str | None,
    city: str,
    state: str,
    ai_analysis: dict | None,
    phone: str | None,
    email: str | None,
) -> dict:
    """Generate a complete website spec using Claude."""
    from app.config import settings

    if not settings.groq_api_key:
        return _fallback_spec(business_name, category, city, state)

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
    except ImportError:
        return _fallback_spec(business_name, category, city, state)

    problems_text = ""
    if ai_analysis and ai_analysis.get("problems"):
        problems_text = "Current website problems to address: " + "; ".join(
            p["description"] for p in ai_analysis["problems"][:3]
        )

    user_msg = (
        f"Business: {business_name}\n"
        f"Category: {category or 'local business'}\n"
        f"Location: {city}, {state}\n"
        f"Phone: {phone or 'not provided'}\n"
        f"Email: {email or 'not provided'}\n"
        f"{problems_text}"
    )

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=2048,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Website spec generation failed for {business_name}: {e}")
        return _fallback_spec(business_name, category, city, state)


def _fallback_spec(business_name: str, category: str | None, city: str, state: str) -> dict:
    return {
        "business_name": business_name,
        "tagline": f"Serving {city} with pride",
        "hero_headline": f"Welcome to {business_name}",
        "hero_subheadline": f"Your trusted {category or 'local business'} in {city}, {state}.",
        "sections": [
            {"name": "Services", "headline": "What We Offer", "body_copy": "We provide top-quality services tailored to your needs.", "cta_text": "Get a Quote"},
            {"name": "About", "headline": f"About {business_name}", "body_copy": f"Proudly serving the {city} community.", "cta_text": None},
            {"name": "Contact", "headline": "Get in Touch", "body_copy": "We'd love to hear from you.", "cta_text": "Contact Us"},
        ],
        "color_palette": {"primary": "#1a1a2e", "secondary": "#16213e", "accent": "#0f3460"},
        "design_direction": "Clean and professional",
        "seo_title": f"{business_name} — {city}, {state}",
        "meta_description": f"{business_name} is a trusted {category or 'business'} serving {city}, {state}.",
        "suggested_domain": business_name.lower().replace(" ", ""),
    }
