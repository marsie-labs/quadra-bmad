from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import get_client
from app.models import CardCreate, CardOut, CardUpdate

router = APIRouter(tags=["cards"])


@router.post("/cards", status_code=201, response_model=CardOut)
async def create_card(body: CardCreate) -> CardOut:
    client = await get_client()

    quadrants = (
        await client.table("quadrants")
        .select("id")
        .eq("id", str(body.quadrant_id))
        .execute()
    ).data
    if not quadrants:
        raise HTTPException(status_code=404, detail="Quadrant not found")

    card = (
        await client.table("cards")
        .insert({
            "quadrant_id": str(body.quadrant_id),
            "content": body.content,
            "order_index": body.order_index,
            "author_id": body.author_id,
        })
        .execute()
    ).data[0]

    return CardOut(**card)


@router.get("/quadrants/{quadrant_id}/cards", response_model=list[CardOut])
async def list_cards(quadrant_id: UUID) -> list[CardOut]:
    client = await get_client()

    quadrants = (
        await client.table("quadrants")
        .select("id")
        .eq("id", str(quadrant_id))
        .execute()
    ).data
    if not quadrants:
        raise HTTPException(status_code=404, detail="Quadrant not found")

    cards = (
        await client.table("cards")
        .select("*")
        .eq("quadrant_id", str(quadrant_id))
        .is_("deleted_at", "null")
        .order("order_index")
        .execute()
    ).data

    return [CardOut(**c) for c in cards if c.get("deleted_at") is None]


@router.patch("/cards/{card_id}", response_model=CardOut)
async def update_card(card_id: UUID, body: CardUpdate) -> CardOut:
    client = await get_client()

    existing = (
        await client.table("cards")
        .select("*")
        .eq("id", str(card_id))
        .execute()
    ).data
    if not existing or existing[0]["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="Card not found")

    updates: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if body.content is not None:
        updates["content"] = body.content
    if body.order_index is not None:
        updates["order_index"] = body.order_index
    if body.quadrant_id is not None:
        quadrants = (
            await client.table("quadrants")
            .select("id")
            .eq("id", str(body.quadrant_id))
            .execute()
        ).data
        if not quadrants:
            raise HTTPException(status_code=404, detail="Target quadrant not found")
        updates["quadrant_id"] = str(body.quadrant_id)

    result = (
        await client.table("cards")
        .update(updates)
        .eq("id", str(card_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Card data corrupted")
    card = result.data[0]

    return CardOut(**card)


@router.delete("/cards/{card_id}", response_model=CardOut)
async def delete_card(card_id: UUID) -> CardOut:
    client = await get_client()

    existing = (
        await client.table("cards")
        .select("*")
        .eq("id", str(card_id))
        .execute()
    ).data
    if not existing or existing[0]["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="Card not found")

    result = (
        await client.table("cards")
        .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", str(card_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Card data corrupted")
    card = result.data[0]

    return CardOut(**card)
