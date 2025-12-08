import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from livekit import api as lk_api
from livekit.api import LiveKitAPI, ListRoomsRequest

load_dotenv()

app = FastAPI(title="LiveKit Token Server")

# CORS (relaxed; tighten for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_rooms() -> list[str]:
    client = LiveKitAPI()
    try:
        rooms = await client.room.list_rooms(ListRoomsRequest())
        return [room.name for room in rooms.rooms]
    finally:
        await client.aclose()


async def generate_room_name() -> str:
    name = "room-" + str(uuid.uuid4())[:8]
    rooms = await get_rooms()
    while name in rooms:
        name = "room-" + str(uuid.uuid4())[:8]
    return name


@app.get("/api/getToken", response_class=PlainTextResponse)
async def get_token(name: str = Query("guest"), room: Optional[str] = Query(None)):
    if not room:
        room = await generate_room_name()

    token = (
        lk_api.AccessToken(os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))
        .with_identity(name)
        .with_name(name)
        .with_grants(
            lk_api.VideoGrants(
                room_join=True,
                room=room,
            )
        )
    )

    return token.to_jwt()


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"


# Run with: uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload