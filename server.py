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

class GameManager:
    def __init__(self) -> None:
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

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        if len(self.connections) >= 2:
            await websocket.close(code=1000)
            return
        
        assigned_symbol = "X" if "X" not in self.connections.values() else "O"
        self.connections[websocket] = assigned_symbol
        
        await websocket.send_json({"type": "init", "symbol": assigned_symbol})
        await self.broadcast()

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            del self.connections[websocket]
        self.reset()

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

    def reset(self) -> None:
        self.board = ["" for _ in range(9)]
        self.turn = "X"
        self.winner = None

    async def process_move(self, index: int, player_symbol: str) -> None:
        if self.winner or self.board[index] != "" or self.turn != player_symbol:
            return
        
        self.board[index] = self.turn
        self.winner = self.check_winner()
        
        if not self.winner:
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
                # --- THIS IS THE LINE THAT WAS FIXED ---
                case {"action": "move", "index": index}: 
                    symbol = manager.connections.get(websocket)
                    if symbol:
                        await manager.process_move(index, symbol)
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
