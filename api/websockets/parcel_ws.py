from fastapi import WebSocket


class ParcelTrackingManager:
    def __init__(self):
        # Maps order_id -> list of active WebSocket connections
        self.active_rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, order_id: str):
        await websocket.accept()
        if order_id not in self.active_rooms:
            self.active_rooms[order_id] = []
        self.active_rooms[order_id].append(websocket)

    def disconnect(self, websocket: WebSocket, order_id: str):
        if order_id in self.active_rooms and websocket in self.active_rooms[order_id]:
            self.active_rooms[order_id].remove(websocket)

    async def broadcast_to_order(self, order_id: str, message: dict):
        if order_id in self.active_rooms:
            for connection in list(self.active_rooms[order_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(connection, order_id)


parcel_ws_manager = ParcelTrackingManager()
