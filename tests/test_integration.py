import asyncio
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from daemon.app import api_request, create_app
from daemon.codex_cli_adapter import CodexCliAdapter

TOKEN = "integration-test-token-not-a-secret"
FIXTURE = Path(__file__).parent / "fixtures" / "mock_codex.py"


async def receive(ws):
    return json.loads(await asyncio.wait_for(ws.recv(), 3))


async def hello(ws, device_id="stackchan-1"):
    await ws.send(json.dumps({"type": "hello", "version": 1, "device_id": device_id}))
    assert (await receive(ws))["type"] == "hello"
    return await receive(ws)


def test_cli_http_websocket_and_reconnection(tmp_path):
    async def scenario():
        app = create_app(str(FIXTURE.resolve()), token=TOKEN)
        await app.start(port=0, api_port=0)
        uri = f"ws://127.0.0.1:{app.ws.sockets[0].getsockname()[1]}/stackChan/ws?deviceType=StackChan"
        headers = {"Authorization": f"Bearer {TOKEN}"}
        token_file = tmp_path / "token"
        token_file.write_text(TOKEN)
        try:
            async with connect(uri, additional_headers=headers, proxy=None) as ws:
                assert (await hello(ws))["state"] == "idle"
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "daemon.app", "run", "test", "--wait",
                    "--cwd", str(tmp_path), "--api-port", str(app.http.port),
                    "--token-file", str(token_file), stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                states = []
                while not states or states[-1]["state"] != "success":
                    states.append(await receive(ws))
                stdout, stderr = await asyncio.wait_for(process.communicate(), 5)
                assert process.returncode == 0, stderr.decode()
                assert any(s.get("message") == "mock test" for s in states)
                task_id = json.loads(stdout.splitlines()[0])["task_id"]
                status = await asyncio.to_thread(api_request, app.http.port, TOKEN, "GET", "/status")
                assert status == states[-1]
                assert status["task_id"] == task_id
                await ws.send("[]")
                assert (await receive(ws))["code"] == "invalid_action"
                await ws.send(json.dumps({"version": 1, "type": "task.action", "task_id": task_id,
                                          "request_id": "obsolete", "action": "approve"}))
                assert (await receive(ws))["accepted"] is False
            # Reconnect after the server observes the previous close.
            for _ in range(100):
                if not app.device_server.connected:
                    break
                await asyncio.sleep(0.01)
            async with connect(uri, additional_headers=headers, proxy=None) as ws:
                replay = await hello(ws)
                assert replay == status
        finally:
            await app.close()
    asyncio.run(asyncio.wait_for(scenario(), 15))


def test_network_auth_pairing_and_duplicate_connections():
    async def scenario():
        app = create_app(token=TOKEN)
        await app.start(port=0, api_port=0)
        base = f"ws://127.0.0.1:{app.ws.sockets[0].getsockname()[1]}"
        headers = {"Authorization": f"Bearer {TOKEN}"}
        try:
            for path, auth, code in [("/wrong", headers, 404), ("/stackChan/ws", {}, 401)]:
                with pytest.raises(InvalidStatus) as err:
                    async with connect(base + path, additional_headers=auth, proxy=None):
                        pass
                assert err.value.response.status_code == code
            def unauthorized_http():
                with pytest.raises(HTTPError) as err:
                    urlopen(f"http://127.0.0.1:{app.http.port}/health", timeout=2)
                assert err.value.code == 401
            await asyncio.to_thread(unauthorized_http)
            async with connect(base + "/stackChan/ws", additional_headers=headers, proxy=None) as ws:
                await ws.send(json.dumps({"type": "hello", "version": 1, "device_id": "wrong"}))
                with pytest.raises(ConnectionClosed):
                    await ws.recv()
            async with connect(base + "/stackChan/ws", additional_headers=headers, proxy=None) as first:
                await hello(first)
                async with connect(base + "/stackChan/ws", additional_headers=headers, proxy=None) as second:
                    await second.send(json.dumps({"type": "hello", "version": 1, "device_id": "stackchan-1"}))
                    with pytest.raises(ConnectionClosed):
                        await second.recv()
                assert app.device_server.connected
        finally:
            await app.close()
    asyncio.run(asyncio.wait_for(scenario(), 15))


@pytest.mark.parametrize("prompt,expected", [("ok", "success"), ("fail", "failed"),
                                              ("late-fail", "failed"), ("missing-completion", "failed")])
def test_real_subprocess_lifecycle(prompt, expected, tmp_path):
    async def scenario():
        events = [event async for event in CodexCliAdapter(str(FIXTURE.resolve())).run(prompt, tmp_path)]
        assert events[-1].state == expected
        assert sum(e.state in {"success", "failed"} for e in events) == 1
    asyncio.run(asyncio.wait_for(scenario(), 8))


def test_busy_and_cancel_reaps_process(tmp_path):
    async def scenario():
        app = create_app(str(FIXTURE.resolve()), token=TOKEN)
        code, result = await app.dispatch("POST", "/tasks", {"prompt": "hang", "cwd": str(tmp_path)})
        assert code == 202
        while app.runtime.state.phase != "command":
            await asyncio.sleep(0.01)
        code, _ = await app.dispatch("POST", "/tasks", {"prompt": "second", "cwd": str(tmp_path)})
        assert code == 409
        code, result = await app.dispatch("POST", f"/tasks/{result['task_id']}/cancel", {})
        assert code == 200 and result["phase"] == "cancelled"
        assert not app.runtime.busy
        await app.close()
    asyncio.run(asyncio.wait_for(scenario(), 8))
