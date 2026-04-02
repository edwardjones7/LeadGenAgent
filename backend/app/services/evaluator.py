import re
import time
import httpx
from bs4 import BeautifulSoup

OLD_PLATFORMS = [
    "wordpress 3.", "wordpress 4.", "wordpress 5.0", "wordpress 5.1",
    "jimdo", "webs.com", "yola", "homestead", "angelfire",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


async def evaluate(url: str, client: httpx.AsyncClient) -> dict:
    """Evaluate a website and return a quality score (1-10) and reasons.

    Higher score = worse website = better lead for Elenos.
    """
    reasons = []
    penalty = 0

    # Check SSL
    if not url.startswith("https://"):
        reasons.append("No SSL certificate (HTTP only)")
        penalty += 3

    # Fetch page
    start = time.monotonic()
    try:
        response = await client.get(url, timeout=10.0, follow_redirects=True)
        load_time = time.monotonic() - start
    except httpx.TimeoutException:
        reasons.append("Website unreachable (timeout)")
        penalty += 5
        return _finalize(penalty, reasons)
    except Exception:
        reasons.append("Website connection failed")
        penalty += 5
        return _finalize(penalty, reasons)

    if response.status_code >= 400:
        reasons.append(f"Website returns error ({response.status_code})")
        penalty += 4
        return _finalize(penalty, reasons)

    # Load time
    if load_time > 6:
        reasons.append(f"Very slow page load ({load_time:.1f}s)")
        penalty += 3
    elif load_time > 3:
        reasons.append(f"Slow page load ({load_time:.1f}s)")
        penalty += 2

    # Parse HTML
    soup = BeautifulSoup(response.text, "lxml")

    # Mobile viewport
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if not viewport:
        reasons.append("Not mobile optimized (no viewport meta tag)")
        penalty += 2

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if not meta_desc or not (meta_desc.get("content") or "").strip():
        reasons.append("Missing meta description (SEO gap)")
        penalty += 1

    # Page title
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    if len(title_text) < 5:
        reasons.append("No descriptive page title")
        penalty += 1

    # Copyright year
    full_text = soup.get_text()
    copyright_match = re.search(
        r"(?:©|copyright)\s*(?:20)?(\d{2,4})", full_text, re.IGNORECASE
    )
    if copyright_match:
        raw_year = copyright_match.group(1)
        year = int(raw_year) if len(raw_year) == 4 else int("20" + raw_year)
        if 1990 <= year <= 2099:
            if year < 2019:
                reasons.append(f"Severely outdated copyright year ({year})")
                penalty += 2
            elif year < 2022:
                reasons.append(f"Outdated copyright year ({year})")
                penalty += 1

    # Old platform
    generator = soup.find("meta", attrs={"name": "generator"})
    if generator:
        gen_content = (generator.get("content") or "").lower()
        for platform in OLD_PLATFORMS:
            if platform in gen_content:
                reasons.append(f"Built on outdated platform ({generator.get('content')})")
                penalty += 1
                break

    return _finalize(penalty, reasons)


def _finalize(penalty: int, reasons: list[str]) -> dict:
    score = max(1, min(10, penalty))
    reason_text = "; ".join(reasons) if reasons else "Website appears acceptable"
    return {"score": score, "score_reason": reason_text}
