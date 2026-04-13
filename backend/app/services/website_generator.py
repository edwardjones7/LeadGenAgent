import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a senior product strategist + web designer writing a complete Product Requirements Document (PRD) \
for a modern local business website. The PRD will be used by the Elenos AI team to pitch and then build the site.

Be SPECIFIC to this business — cite the category, city, and any known signals. Invent realistic, concrete \
copy (no placeholder text, no "lorem ipsum", no "insert X here"). Write as if you already know the business.

Respond with valid JSON only — no markdown fences, no commentary. Match this exact schema:
{
  "business_name": "string",
  "project_title": "e.g. 'Starbucks Coffee Madison Website'",
  "overview": "2–3 sentence project summary — what we're building and the feel it should have",
  "objectives": ["5–6 measurable objectives"],
  "target_audience": {
    "primary": ["2–3 primary segments"],
    "secondary": ["2–3 secondary segments"]
  },
  "user_personas": [
    {
      "name": "persona name in quotes e.g. 'The Busy Commuter'",
      "bio": "1 sentence on who they are",
      "needs": ["3–4 needs / goals"]
    }
  ],
  "core_features": [
    {
      "section": "section name e.g. Homepage, About, Menu, Services, Testimonials, Contact",
      "purpose": "1 sentence on what this section does",
      "components": ["concrete page elements — headline copy, CTAs, imagery, form fields, etc."]
    }
  ],
  "design": {
    "style_direction": "2 sentences on the visual feel",
    "color_palette": {"primary": "#hex", "secondary": "#hex", "accent": "#hex", "background": "#hex", "text": "#hex"},
    "typography": "font family or style guidance",
    "ui_notes": ["4–6 specific UI rules — buttons, spacing, hover, iconography, etc."]
  },
  "ux_requirements": ["6–8 UX rules — responsiveness, perf target, navigation, CTAs, a11y, etc."],
  "technical_requirements": {
    "recommended_platform": "e.g. Next.js + Tailwind, Webflow, WordPress with Elementor — pick one and justify in-line",
    "integrations": ["4–6 integrations — maps, analytics, booking, payment, email capture, etc."],
    "hosting": "e.g. Vercel, Netlify, managed WordPress"
  },
  "success_metrics": ["5–6 KPIs with concrete targets, e.g. 'Bounce rate < 50%'"],
  "future_enhancements": ["4–6 phase-2 ideas"],
  "sitemap": ["Home", "About", "..." ],
  "copy_tone": ["4–5 tone rules — e.g. warm, confident, community-driven"],
  "key_differentiator": "1–2 sentences on the positioning angle vs competitors",

  "tagline": "short punchy tagline (under 8 words)",
  "hero_headline": "main H1 headline",
  "hero_subheadline": "1–2 sentence subheadline",
  "sections": [
    {
      "name": "matches a core_features section",
      "headline": "section headline copy",
      "body_copy": "2–3 sentences of real body copy",
      "cta_text": "button text or null"
    }
  ],
  "seo_title": "under 60 chars",
  "meta_description": "under 155 chars",
  "suggested_domain": "domain name without TLD"
}

Rules:
- 3–4 user_personas, 5–7 core_features, 4–6 sections
- Colors MUST fit the category (a coffee shop is warm/brown/cream, a law firm is navy/slate, a gym is bold/high-contrast)
- Objectives and KPIs must be plausible for a local SMB — not enterprise
- recommended_platform should be one choice, not a list"""


async def generate_website_spec(
    business_name: str,
    category: str | None,
    city: str,
    state: str,
    ai_analysis: dict | None,
    phone: str | None,
    email: str | None,
) -> dict:
    """Generate a complete website spec using a free LLM (Groq → SambaNova fallback)."""
    from app.config import settings

    if not (settings.groq_api_key or settings.sambanova_api_key):
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
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    # Try providers in order — both are free-tier
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
                max_tokens=6000,  # PRD output is large
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Website spec via {provider} failed for {business_name}: {e}")
            continue

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
