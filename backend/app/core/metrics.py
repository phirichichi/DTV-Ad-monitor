#metrics.py 
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

router = APIRouter()

# Counter for total HTTP requests handled by the API.
http_requests_total = Counter(
    "dtv_http_requests_total",
    "Total HTTP requests processed by DTV-Ad Monitor API",
)


@router.get("/metrics")
def metrics():
    """
    Expose Prometheus metrics endpoint.
    """
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)