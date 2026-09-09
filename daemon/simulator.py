"""Console device simulator; reconnecting exercises the real WebSocket path."""
import asyncio
import json

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


async def monitor(url, token, device_id):
    while True:
        try:
            async with connect(url, additional_headers={"Authorization": f"Bearer {token}"}, proxy=None) as ws:
                await ws.send(json.dumps({"type": "hello", "version": 1, "device_id": device_id}))
                async for raw in ws:
                    print(raw, flush=True)
        except (OSError, ConnectionClosed):
            print("Disconnected; reconnecting...", flush=True)
            await asyncio.sleep(1)
