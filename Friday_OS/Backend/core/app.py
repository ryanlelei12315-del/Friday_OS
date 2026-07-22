import asyncio
import json
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FridayOS Core Bridge")

# Allow your Next.js/Electron interface to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/bridge")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[✔] FridayOS frontend interface linked to Core Bridge.")

    try:
        while True:
            # 1. Listen for microphone audio packets or UI window directives
            raw_data = await websocket.receive_text()
            payload = json.loads(raw_data)

            # Example Event: Incoming voice stream block
            if payload.get("event") == "mic_audio_chunk":
                start_time = time.time()

                # Simulate processing the frame through your voice sandbox pipeline
                await asyncio.sleep(0.1)

                # Calculate processing latency (ttft simulation)
                ttft_ms = int((time.time() - start_time) * 1000)

                # 2. Broadcast live telemetry metrics straight back to the frontend HUD
                await websocket.send_json(
                    {
                        "status": "processing",
                        "telemetry": {
                            "llm_ttft": f"{ttft_ms + 2300}ms",  # Matching your hardware profile
                            "state": "THINKING",
                            "chromadb_cached": True,
                        },
                    }
                )

    except WebSocketDisconnect:
        print("[!] FridayOS frontend disconnected from Core Bridge.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
