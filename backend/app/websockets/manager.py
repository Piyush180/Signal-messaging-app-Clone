"""
In-memory registry of live WebSocket connections.

Responsibilities (and ONLY these):
  - track which sockets belong to which user (a user may have several tabs open),
  - send a JSON payload to every socket of a given user,
  - report whether a user currently has any live socket (presence).

It deliberately knows nothing about the database or message logic. That
separation is what lets the same broadcast helper be called from both the REST
endpoints and the WebSocket handler.

Scaling note (explained further in DESIGN.md): this dict lives in one process,
so it works for a single server. To run multiple backend instances you would
replace the direct `send` with a publish to Redis Pub/Sub and have each instance
deliver to its own local sockets. The interface below would stay the same.
"""
import logging
from typing import Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger("ws.manager")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(user_id, set()).add(websocket)
        logger.info("user %s connected (%d sockets)", user_id, len(self._connections[user_id]))

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(user_id, None)
        logger.info("user %s disconnected", user_id)

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    def online_user_ids(self) -> List[int]:
        return list(self._connections.keys())

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        dead = []
        for ws in list(sockets):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - a dead socket must never crash a broadcast
                dead.append(ws)
        for ws in dead:
            sockets.discard(ws)
        if not sockets:
            self._connections.pop(user_id, None)

    async def broadcast(self, user_ids: List[int], payload: dict) -> None:
        for uid in set(user_ids):
            await self.send_to_user(uid, payload)


manager = ConnectionManager()
