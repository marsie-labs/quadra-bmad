from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.database import get_client
from app.models import (
    CanvasState,
    QuadrantOut,
    QuadrantType,
    SessionCreate,
    SessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201, response_model=SessionResponse)
async def create_session(body: SessionCreate, request: Request) -> SessionResponse:
    client = await get_client()

    workspace = (
        await client.table("workspaces")
        .insert({"project_name": body.project_name})
        .execute()
    ).data[0]

    canvas = (
        await client.table("canvases")
        .insert({"workspace_id": workspace["id"]})
        .execute()
    ).data[0]

    await client.table("quadrants").insert(
        [{"canvas_id": canvas["id"], "type": qt.value} for qt in QuadrantType]
    ).execute()

    quadrants_data = (
        await client.table("quadrants")
        .select("*")
        .eq("canvas_id", canvas["id"])
        .execute()
    ).data

    base_url = str(request.base_url).rstrip("/")
    access_url = f"{base_url}/sessions/{workspace['access_token']}"

    return SessionResponse(
        session_id=workspace["id"],
        access_token=workspace["access_token"],
        access_url=access_url,
        project_name=workspace["project_name"],
        canvas=CanvasState(
            canvas_id=canvas["id"],
            workspace_id=workspace["id"],
            is_active=canvas["is_active"],
            quadrants=[QuadrantOut(**q) for q in quadrants_data],
        ),
    )


@router.get("/{access_token}", response_model=SessionResponse)
async def get_session(access_token: UUID, request: Request) -> SessionResponse:
    client = await get_client()

    workspaces = (
        await client.table("workspaces")
        .select("*")
        .eq("access_token", str(access_token))
        .execute()
    ).data

    if not workspaces:
        raise HTTPException(status_code=404, detail="Session not found")

    workspace = workspaces[0]

    canvases = (
        await client.table("canvases")
        .select("*")
        .eq("workspace_id", workspace["id"])
        .execute()
    ).data

    if not canvases:
        raise HTTPException(status_code=500, detail="Canvas data corrupted")
    canvas = canvases[0]

    quadrants_data = (
        await client.table("quadrants")
        .select("*")
        .eq("canvas_id", canvas["id"])
        .execute()
    ).data

    base_url = str(request.base_url).rstrip("/")
    access_url = f"{base_url}/sessions/{workspace['access_token']}"

    return SessionResponse(
        session_id=workspace["id"],
        access_token=workspace["access_token"],
        access_url=access_url,
        project_name=workspace["project_name"],
        canvas=CanvasState(
            canvas_id=canvas["id"],
            workspace_id=workspace["id"],
            is_active=canvas["is_active"],
            quadrants=[QuadrantOut(**q) for q in quadrants_data],
        ),
    )
