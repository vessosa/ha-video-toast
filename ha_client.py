import asyncio
import json
import ssl
import threading

import requests
import websockets


class HAClient:
    def __init__(self, config, on_toast_event):
        self.config = config
        self.on_toast_event = on_toast_event
        self.on_status_change = None
        self._loop = None
        self._thread = None
        self._stop = threading.Event()
        self._msg_id = 0

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._cancel_tasks)

    def _cancel_tasks(self):
        for task in asyncio.all_tasks(self._loop):
            task.cancel()

    def stream_url(self, camera_entity):
        return f"{self.config['ha_url'].rstrip('/')}/api/camera_proxy_stream/{camera_entity}"

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.config['token']}"}

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except (RuntimeError, asyncio.CancelledError):
            pass
        finally:
            self._loop.close()

    async def _connect_loop(self):
        while not self._stop.is_set():
            try:
                await self._connect()
            except asyncio.CancelledError:
                return
            except Exception:
                self._emit_status(False)
                if not self._stop.is_set():
                    try:
                        await asyncio.sleep(5)
                    except asyncio.CancelledError:
                        return

    async def _connect(self):
        ws_url, ssl_ctx = _build_ws_url(self.config["ha_url"])
        async with websockets.connect(ws_url, ssl=ssl_ctx) as ws:
            msg = json.loads(await ws.recv())
            if msg.get("type") != "auth_required":
                raise ConnectionError("Unexpected handshake")

            self._msg_id += 1
            await ws.send(json.dumps({"type": "auth", "access_token": self.config["token"]}))
            msg = json.loads(await ws.recv())
            if msg.get("type") != "auth_ok":
                raise PermissionError("Auth failed — check token")

            self._msg_id += 1
            sub_id = self._msg_id
            await ws.send(json.dumps({
                "id": sub_id,
                "type": "subscribe_events",
                "event_type": "ha_video_toast",
            }))
            await ws.recv()  # result ack

            self._emit_status(True)

            async for raw in ws:
                if self._stop.is_set():
                    break
                msg = json.loads(raw)
                if msg.get("type") == "event" and msg.get("id") == sub_id:
                    data = msg["event"].get("data", {})
                    if self.on_toast_event:
                        self.on_toast_event(data)

    def _emit_status(self, connected):
        if self.on_status_change:
            self.on_status_change(connected)

    # ------------------------------------------------------------------
    # Static helpers used by settings window (run synchronously in thread)
    # ------------------------------------------------------------------

    @staticmethod
    def test_connection(ha_url, token):
        """Returns (True, None) or (False, error_string)."""
        result = [None]

        async def _test():
            try:
                ws_url, ssl_ctx = _build_ws_url(ha_url)
                async with websockets.connect(ws_url, ssl=ssl_ctx, open_timeout=5) as ws:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    if msg.get("type") != "auth_required":
                        result[0] = (False, "Unexpected response from server")
                        return
                    await ws.send(json.dumps({"type": "auth", "access_token": token}))
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    if msg.get("type") == "auth_ok":
                        result[0] = (True, None)
                    else:
                        result[0] = (False, "Invalid token")
            except Exception as e:
                result[0] = (False, str(e))

        loop = asyncio.new_event_loop()
        loop.run_until_complete(_test())
        loop.close()
        return result[0]

    @staticmethod
    def discover_cameras(ha_url, token):
        """Returns sorted list of camera entity IDs."""
        try:
            url = ha_url.rstrip("/") + "/api/states"
            headers = {"Authorization": f"Bearer {token}"}
            resp = _get_with_ssl_fallback(url, headers=headers, timeout=5)
            return sorted(s["entity_id"] for s in resp.json() if s["entity_id"].startswith("camera."))
        except Exception:
            return []


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_ws_url(ha_url):
    base = ha_url.rstrip("/")
    if base.startswith("https://"):
        return base.replace("https://", "wss://") + "/api/websocket", ssl.create_default_context()
    if base.startswith("http://"):
        return base.replace("http://", "ws://") + "/api/websocket", None
    return "ws://" + base + "/api/websocket", None


def _get_with_ssl_fallback(url, **kwargs):
    try:
        return requests.get(url, verify=True, **kwargs)
    except requests.exceptions.SSLError:
        return requests.get(url, verify=False, **kwargs)
