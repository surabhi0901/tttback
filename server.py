import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Room:
    def __init__(self, code: str):
        self.code = code
        self.connections: dict[WebSocket, str] = {}
        self.board: list[str] = ["" for _ in range(9)]
        self.turn: str = "X"
        self.winner: str | None = None

    def check_winner(self) -> str | None:
        winning_combos = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6]
        ]
        for a, b, c in winning_combos:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if "" not in self.board:
            return "Draw"
        return None

    def reset(self) -> None:
        self.board = ["" for _ in range(9)]
        self.turn = "X"
        self.winner = None

    async def broadcast(self) -> None:
        state = {
            "type": "state",
            "board": self.board,
            "turn": self.turn,
            "players": len(self.connections),
            "winner": self.winner
        }
        for connection in self.connections:
            await connection.send_json(state)


class ConnectionManager:
    def __init__(self):
        # Dictionary to store all active rooms
        self.rooms: dict[str, Room] = {}

manager = ConnectionManager()

# The WebSocket endpoint now accepts a {room_code} from the URL
@app.websocket("/ws/{room_code}")
async def game_endpoint(websocket: WebSocket, room_code: str) -> None:
    
    # If the room doesn't exist yet, create it
    if room_code not in manager.rooms:
        manager.rooms[room_code] = Room(room_code)
    
    room = manager.rooms[room_code]

    await websocket.accept()
    
    # Block if room is full
    if len(room.connections) >= 2:
        await websocket.close(code=1000)
        return
    
    assigned_symbol = "X" if "X" not in room.connections.values() else "O"
    room.connections[websocket] = assigned_symbol
    
    await websocket.send_json({"type": "init", "symbol": assigned_symbol, "code": room_code})
    await room.broadcast()

    try:
        while True:
            data = await websocket.receive_json()
            match data:
                case {"action": "move", "index": index}:
                    symbol = room.connections.get(websocket)
                    # ONLY allow moves if there are exactly 2 players in the room
                    if symbol and len(room.connections) == 2:
                        if not room.winner and room.board[index] == "" and room.turn == symbol:
                            room.board[index] = room.turn
                            room.winner = room.check_winner()
                            if not room.winner:
                                room.turn = "O" if room.turn == "X" else "X"
                            await room.broadcast()
                case {"action": "reset"}:
                    if len(room.connections) == 2:
                        room.reset()
                        await room.broadcast()
                case _:
                    pass
    except WebSocketDisconnect:
        if websocket in room.connections:
            del room.connections[websocket]
        
        # If everyone left, delete the room from memory to save server space
        if len(room.connections) == 0:
            del manager.rooms[room_code]
        else:
            # If one player left, reset the board for the remaining player
            room.reset()
            await room.broadcast()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
