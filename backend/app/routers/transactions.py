from fastapi import APIRouter, HTTPException, status

from app.models.transaction import TransactionSimulateRequest
from app.services.ingestion import simulate_transaction

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "/simulate",
    summary="Simulate a purchase and run the full detection pipeline",
    status_code=status.HTTP_201_CREATED,
)
async def simulate(req: TransactionSimulateRequest = TransactionSimulateRequest()):
    """
    Ingest a mock transaction and run it through:
    1. Rules-based candidate filter
    2. Benefit matching engine
    3. Claim pre-fill service (if a match is found)

    All fields are optional — omitted fields are randomly generated,
    making this a single-click demo trigger.
    """
    try:
        result = await simulate_transaction(req)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result
