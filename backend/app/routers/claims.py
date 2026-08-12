from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_db
from app.models.claim import (
    ClaimApproveRequest,
    ClaimListResponse,
    ClaimStatus,
    ClaimSubmitRequest,
    ClaimSubmitResponse,
)
from app.models.common import mongo_doc_to_dict

router = APIRouter(prefix="/claims", tags=["Claims"])


def _require_claim(doc):
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return mongo_doc_to_dict(doc)


@router.get(
    "",
    summary="List all claims for a card member",
    response_model=ClaimListResponse,
)
async def list_claims(
    card_member_id: Optional[str] = Query(default=None),
    card_id: Optional[str] = Query(default=None),
    claim_status: Optional[str] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    db = get_db()
    query: dict = {}
    if card_member_id:
        query["card_member_id"] = card_member_id
    if card_id:
        query["card_id"] = card_id
    if claim_status:
        query["status"] = claim_status

    total = await db.claims.count_documents(query)
    cursor = (
        db.claims.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = [mongo_doc_to_dict(d) async for d in cursor]
    return ClaimListResponse(claims=docs, total=total)


@router.get(
    "/{claim_id}",
    summary="Get a single claim by ID",
)
async def get_claim(claim_id: str):
    db = get_db()
    if not ObjectId.is_valid(claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")
    doc = await db.claims.find_one({"_id": ObjectId(claim_id)})
    return _require_claim(doc)


@router.post(
    "/{claim_id}/submit",
    summary="Card member confirms and submits a pre-filled claim",
    response_model=ClaimSubmitResponse,
)
async def submit_claim(claim_id: str, body: ClaimSubmitRequest = ClaimSubmitRequest()):
    """
    The card member taps 'Submit' in the app (PDF Slide 8, step 2).
    Transitions the claim from DETECTED → SUBMITTED.
    """
    db = get_db()
    if not ObjectId.is_valid(claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    doc = await db.claims.find_one({"_id": ObjectId(claim_id)})
    _require_claim(doc)

    if doc["status"] != ClaimStatus.DETECTED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Claim is already in status '{doc['status']}' — cannot submit.",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.claims.update_one(
        {"_id": ObjectId(claim_id)},
        {
            "$set": {
                "status": ClaimStatus.SUBMITTED.value,
                "submitted_at": now,
                "edited": body.edited,
            }
        },
    )

    # Automatically transition to UNDER_REVIEW to simulate bank receipt
    await db.claims.update_one(
        {"_id": ObjectId(claim_id)},
        {"$set": {"status": ClaimStatus.UNDER_REVIEW.value, "reviewed_at": now}},
    )

    return ClaimSubmitResponse(
        claim_id=claim_id,
        status=ClaimStatus.UNDER_REVIEW,
        message="Claim submitted and is now under review by the bank.",
    )


@router.post(
    "/{claim_id}/approve",
    summary="Simulate bank approval or rejection of a claim",
    response_model=ClaimSubmitResponse,
)
async def approve_claim(claim_id: str, body: ClaimApproveRequest = ClaimApproveRequest()):
    """
    Simulates the bank's approval step (PDF Slide 9 — Claims & Approval Workflow).
    In production this would be driven by the bank's adjudication system.
    For the demo, call this endpoint to advance the claim to APPROVED/REJECTED.
    """
    db = get_db()
    if not ObjectId.is_valid(claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    doc = await db.claims.find_one({"_id": ObjectId(claim_id)})
    _require_claim(doc)

    if doc["status"] not in (ClaimStatus.SUBMITTED.value, ClaimStatus.UNDER_REVIEW.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Claim must be SUBMITTED or UNDER_REVIEW to approve/reject "
                f"(current: '{doc['status']}')."
            ),
        )

    new_status = ClaimStatus.APPROVED if body.approved else ClaimStatus.REJECTED
    update: dict = {
        "status": new_status.value,
        "resolved_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    if body.approved:
        update["payout_amount_usd"] = doc["amount_usd"]
    if body.reviewer_notes:
        update["reviewer_notes"] = body.reviewer_notes

    await db.claims.update_one({"_id": ObjectId(claim_id)}, {"$set": update})

    message = (
        f"Claim approved. ${doc['amount_usd']:.2f} will be credited in 3–5 business days."
        if body.approved
        else f"Claim rejected. {body.reviewer_notes or 'No additional notes.'}"
    )

    return ClaimSubmitResponse(
        claim_id=claim_id,
        status=new_status,
        message=message,
    )
