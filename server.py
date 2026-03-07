import asyncio
from typing import List
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

class GameManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []
        self.board: list[str] = ["" for _ in range(9)]
        self.turn: str = "X"

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        if len(self.connections) >= 2:
            await websocket.close(code=1000)
            return
        self.connections.append(websocket)
        await self.broadcast()

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.remove(websocket)
        self.reset()

    async def broadcast(self) -> None:
        state = {
            "board": self.board,
            "turn": self.turn,
            "players": len(self.connections)
        }
        for connection in self.connections:
            await connection.send_json(state)

    def reset(self) -> None:
        self.board = ["" for _ in range(9)]
        self.turn = "X"

    async def process_move(self, index: int) -> None:
        if self.board[index] == "":
            self.board[index] = self.turn
            self.turn = "O" if self.turn == "X" else "X"
            await self.broadcast()

manager = GameManager()

@app.websocket("/ws")
async def game_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            match data:
                case {"action": "move", "index": int(index)}:
                    await manager.process_move(index)
                case {"action": "reset"}:
                    manager.reset()
                    await manager.broadcast()
                case _:
                    pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)