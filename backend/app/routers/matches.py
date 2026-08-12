from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_db
from app.models.common import mongo_doc_to_dict
from app.models.match import MatchListResponse

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get(
    "",
    summary="List detected benefit matches",
    response_model=MatchListResponse,
)
async def list_matches(
    card_member_id: Optional[str] = Query(
        default=None, description="Filter by card member ID"
    ),
    card_id: Optional[str] = Query(default=None, description="Filter by card ID"),
    benefit_type: Optional[str] = Query(
        default=None, description="Filter by benefit type"
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    db = get_db()
    query: dict = {}
    if card_member_id:
        query["card_member_id"] = card_member_id
    if card_id:
        query["card_id"] = card_id
    if benefit_type:
        query["benefit_type"] = benefit_type

    total = await db.detected_matches.count_documents(query)
    cursor = (
        db.detected_matches.find(query)
        .sort("detected_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = [mongo_doc_to_dict(d) async for d in cursor]
    return MatchListResponse(matches=docs, total=total)


@router.get(
    "/{match_id}",
    summary="Get a single detected match",
)
async def get_match(match_id: str):
    db = get_db()
    if not ObjectId.is_valid(match_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid match ID")
    doc = await db.detected_matches.find_one({"_id": ObjectId(match_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return mongo_doc_to_dict(doc)
