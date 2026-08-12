from bson import ObjectId
from fastapi import APIRouter, HTTPException, status

from app.database import get_db
from app.models.card import BenefitEntitlements, CardEntitlementsResponse
from app.models.common import mongo_doc_to_dict

router = APIRouter(prefix="/cards", tags=["Cards"])


@router.get(
    "",
    summary="List all cards",
)
async def list_cards():
    db = get_db()
    docs = [mongo_doc_to_dict(d) async for d in db.cards.find({})]
    return {"cards": docs, "total": len(docs)}


@router.get(
    "/{card_id}",
    summary="Get a single card",
)
async def get_card(card_id: str):
    db = get_db()
    if not ObjectId.is_valid(card_id):
        raise HTTPException(status_code=400, detail="Invalid card ID")
    doc = await db.cards.find_one({"_id": ObjectId(card_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Card not found")
    return mongo_doc_to_dict(doc)


@router.get(
    "/{card_id}/entitlements",
    summary="Show what benefits a card covers",
    response_model=CardEntitlementsResponse,
)
async def get_entitlements(card_id: str):
    """
    Returns the full benefit entitlement profile for a card —
    coverage types, caps, and validity windows.
    Matches the 'Benefit Entitlement DB' in the architecture diagram.
    """
    db = get_db()
    if not ObjectId.is_valid(card_id):
        raise HTTPException(status_code=400, detail="Invalid card ID")

    card_doc = await db.cards.find_one({"_id": ObjectId(card_id)})
    if not card_doc:
        raise HTTPException(status_code=404, detail="Card not found")

    product_doc = await db.card_products.find_one(
        {"_id": ObjectId(card_doc["card_product_id"])}
    )
    if not product_doc:
        raise HTTPException(status_code=404, detail="Card product not found")

    entitlements = BenefitEntitlements(**product_doc.get("entitlements", {}))

    return CardEntitlementsResponse(
        card_id=card_id,
        cardholder_name=card_doc["cardholder_name"],
        card_product_name=product_doc["name"],
        entitlements=entitlements,
    )
