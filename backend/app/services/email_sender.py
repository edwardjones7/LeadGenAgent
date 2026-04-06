import logging

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email via Resend. Returns {"id": str|None, "status": "sent"|"failed", "error": str|None}."""
    from app.config import settings

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — cannot send email")
        return {"id": None, "status": "failed", "error": "RESEND_API_KEY not configured"}

    if not settings.from_email:
        return {"id": None, "status": "failed", "error": "FROM_EMAIL not configured"}

    try:
        import resend
        resend.api_key = settings.resend_api_key
        response = resend.Emails.send({
            "from": settings.from_email,
            "to": [to],
            "subject": subject,
            "text": body,
        })
        msg_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
        return {"id": msg_id, "status": "sent", "error": None}
    except ImportError:
        logger.error("resend package not installed")
        return {"id": None, "status": "failed", "error": "resend package not installed"}
    except Exception as e:
        logger.error(f"Resend send failed to {to}: {e}")
        return {"id": None, "status": "failed", "error": str(e)}
