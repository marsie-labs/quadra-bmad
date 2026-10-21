import uuid
from datetime import datetime, timezone

from nicegui import app as nicegui_app, ui

from app.database import get_client
from app.ui import realtime_ui

QUADRANT_LABELS = {
    "IS": "IS",
    "IS_NOT": "IS NOT",
    "DOES": "DOES",
    "DOES_NOT": "DOES NOT",
}


async def _load_cards(quadrant_id: str) -> list[dict]:
    client = await get_client()
    return (
        await client.table("cards")
        .select("*")
        .eq("quadrant_id", quadrant_id)
        .is_("deleted_at", "null")
        .order("order_index")
        .execute()
    ).data


@ui.page("/board/{access_token}")
async def canvas_page(access_token: str) -> None:
    if "author_id" not in nicegui_app.storage.user:
        nicegui_app.storage.user["author_id"] = str(uuid.uuid4())
    author_id: str = nicegui_app.storage.user["author_id"]

    client = await get_client()
    workspaces = (
        await client.table("workspaces")
        .select("*")
        .eq("access_token", access_token)
        .execute()
    ).data

    if not workspaces:
        with ui.column().classes("items-center justify-center h-screen"):
            ui.label("Session not found. Check your link.").classes("text-red-500 text-xl")
        return

    workspace = workspaces[0]
    canvases = (
        await client.table("canvases")
        .select("*")
        .eq("workspace_id", workspace["id"])
        .execute()
    ).data

    if not canvases:
        ui.label("Canvas not found.").classes("text-red-500 text-xl m-8")
        return

    canvas = canvases[0]
    quadrants_data = (
        await client.table("quadrants")
        .select("*")
        .eq("canvas_id", canvas["id"])
        .execute()
    ).data

    ui.query("body").classes("bg-gray-100")

    with ui.header().classes("bg-indigo-600 text-white px-6 py-3"):
        ui.label(f"Quadra — {workspace['project_name']}").classes("text-xl font-bold")

    with ui.row().classes("w-full gap-4 p-4 flex-nowrap"):
        for quadrant in quadrants_data:
            _build_quadrant_column(quadrant, quadrants_data, author_id)


def _build_quadrant_column(
    quadrant: dict,
    all_quadrants: list[dict],
    author_id: str,
) -> None:
    quadrant_id = quadrant["id"]
    label = QUADRANT_LABELS.get(quadrant["type"], quadrant["type"])

    with ui.card().classes("flex-1 min-w-56 max-w-xs"):
        ui.label(label).classes("text-base font-semibold text-indigo-700 mb-1")
        cards_container = ui.column().classes("w-full gap-2")

        async def refresh(q_id=quadrant_id, container=cards_container) -> None:
            cards = await _load_cards(q_id)
            container.clear()
            with container:
                for card in cards:
                    _render_card(card, quadrant_id, all_quadrants, author_id, refresh)

        add_input = ui.input(placeholder="New card…").classes("w-full text-sm")

        async def add_card(q_id=quadrant_id, inp=add_input) -> None:
            text = inp.value.strip()
            if not text:
                return
            inp.value = ""
            with cards_container:
                placeholder = ui.label(f"⏳ {text}").classes("text-gray-400 text-sm italic")
            try:
                c = await get_client()
                result = (
                    await c.table("cards")
                    .insert({
                        "quadrant_id": q_id,
                        "content": text,
                        "author_id": author_id,
                        "order_index": 0,
                    })
                    .execute()
                )
                if not result.data:
                    raise RuntimeError("Insert returned no data")
            except Exception as e:
                placeholder.delete()
                ui.notify(f"Failed to add card: {e}", color="negative")
                await refresh()
                return
            await refresh()

        ui.button("Add", on_click=add_card).classes("w-full mt-1").props("color=indigo")

        # Load cards on page render
        ui.timer(0, refresh, once=True)

        realtime_ui.register(quadrant_id, refresh)

        async def on_disconnect(q_id=quadrant_id, r=refresh) -> None:
            realtime_ui.unregister(q_id, r)

        ui.context.client.on_disconnect(on_disconnect)


def _render_card(
    card: dict,
    quadrant_id: str,
    all_quadrants: list[dict],
    author_id: str,
    refresh_fn,
) -> None:
    other_quadrants = [q for q in all_quadrants if q["id"] != quadrant_id]

    with ui.card().classes("w-full p-2 bg-white shadow-sm") as card_el:
        content_label = ui.label(card["content"]).classes("text-sm break-words w-full mb-1")

        with ui.row().classes("gap-1 justify-end"):

            async def edit(c=card, lbl=content_label) -> None:
                new_text = await ui.run_javascript(
                    f"prompt('Edit card:', {repr(c['content'])})"
                )
                if new_text is None or new_text == c["content"]:
                    return
                old = lbl.text
                lbl.set_text(new_text)
                try:
                    client = await get_client()
                    res = (
                        await client.table("cards")
                        .update({
                            "content": new_text,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                        .eq("id", c["id"])
                        .execute()
                    )
                    if not res.data:
                        raise RuntimeError("Update returned no data")
                    c["content"] = new_text
                except Exception as e:
                    lbl.set_text(old)
                    ui.notify(f"Failed to edit: {e}", color="negative")

            async def delete(c_id=card["id"], el=card_el) -> None:
                el.set_visibility(False)
                try:
                    client = await get_client()
                    res = (
                        await client.table("cards")
                        .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
                        .eq("id", c_id)
                        .execute()
                    )
                    if not res.data:
                        raise RuntimeError("Delete returned no data")
                except Exception as e:
                    el.set_visibility(True)
                    ui.notify(f"Failed to delete: {e}", color="negative")
                    return
                await refresh_fn()

            async def move(c_id=card["id"], el=card_el) -> None:
                if not other_quadrants:
                    return
                with ui.dialog() as dlg, ui.card():
                    ui.label("Move card to").classes("font-semibold")
                    options = {q["id"]: QUADRANT_LABELS.get(q["type"], q["type"]) for q in other_quadrants}
                    target_select = ui.select(options, label="Target quadrant")

                    async def confirm() -> None:
                        new_qid = target_select.value
                        if not new_qid:
                            return
                        dlg.close()
                        el.set_visibility(False)
                        try:
                            client = await get_client()
                            res = (
                                await client.table("cards")
                                .update({
                                    "quadrant_id": new_qid,
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                })
                                .eq("id", c_id)
                                .execute()
                            )
                            if not res.data:
                                raise RuntimeError("Move returned no data")
                        except Exception as e:
                            el.set_visibility(True)
                            ui.notify(f"Failed to move: {e}", color="negative")
                            return
                        await refresh_fn()

                    with ui.row():
                        ui.button("Move", on_click=confirm).props("color=indigo")
                        ui.button("Cancel", on_click=dlg.close).props("flat")
                dlg.open()

            ui.button("✎", on_click=edit).props("flat dense size=sm")
            ui.button("↗", on_click=move).props("flat dense size=sm")
            ui.button("✕", on_click=delete).props("flat dense size=sm color=negative")
