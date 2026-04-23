from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse

from app.config import settings
from app.ghl_db import get_referral_code_by_code
from app.database import log_event

router = APIRouter()


@router.get("/r/{code}")
async def referral_redirect(code: str):
    """Public referral link. Redirects to GHL landing page with UTM params."""
    code_record = get_referral_code_by_code(code.lower().strip())
    if not code_record:
        return HTMLResponse(
            "<h1>Invalid referral link</h1><p>This referral link is not recognized.</p>",
            status_code=404,
        )

    # Build redirect URL
    base_url = settings.ghl_referral_landing_url or "https://www.whitehousechiropractic.com"

    # Parse existing URL to preserve any existing query params
    parsed = urlparse(base_url)
    existing_params = parse_qs(parsed.query)

    # Add UTM params
    utm_params = {
        "utm_source": "referral",
        "utm_medium": "patient_referral",
        "utm_campaign": code,
        "utm_content": str(code_record["patient_id"]),
    }
    existing_params.update(utm_params)

    # Flatten params (parse_qs returns lists)
    flat_params = {}
    for k, v in existing_params.items():
        flat_params[k] = v[0] if isinstance(v, list) else v

    new_query = urlencode(flat_params)
    redirect_url = urlunparse(parsed._replace(query=new_query))

    log_event("referral", f"Referral link clicked: code={code}")
    return RedirectResponse(url=redirect_url, status_code=302)
