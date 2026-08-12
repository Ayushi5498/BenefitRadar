from fastapi import APIRouter

from app.services.metrics_service import get_summary

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get(
    "/summary",
    summary="Pipeline metrics — detection rates, form accuracy, utilization",
)
async def metrics_summary():
    """
    Returns a single JSON object with all key performance indicators:
    - Total transactions ingested
    - % that passed the rules filter (Stage 1)
    - % that became a match (Stage 2)
    - Pre-fill accuracy (% of claims submitted without editing)
    - Utilization rate (approved claims / total matches detected)
    - Claims breakdown by benefit type
    """
    return await get_summary()
