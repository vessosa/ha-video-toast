import threading

import pystray
from PIL import Image, ImageDraw

# States: "unconfigured" | "connecting" | "connected" | "error"
_DOT_COLOR = {
    "unconfigured": "#71717a",   # zinc — not set up yet
    "connecting":   "#f59e0b",   # amber — in progress, not an error
    "connected":    "#22c55e",   # green
    "error":        "#ef4444",   # red — only after an actual failure
}
_BODY_COLOR = {
    "unconfigured": "#3f3f46",
    "connecting":   "#0891b2",
    "connected":    "#06b6d4",
    "error":        "#0891b2",
}

_SIZE = 64
_SCALE = 4   # draw at 4× for smooth downsampling


def _make_icon(state: str) -> Image.Image:
    S = _SIZE * _SCALE
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    body  = _BODY_COLOR.get(state, "#0891b2")
    dot   = _DOT_COLOR.get(state, "#71717a")

    pad = S // 8
    r   = S // 10

    # Camera body
    body_top = pad + S // 6
    d.rounded_rectangle([pad, body_top, S - pad, S - pad], radius=r, fill=body)

    # Viewfinder bump
    bw = S // 3
    bh = S // 8
    bx = pad + S // 10
    d.rectangle([bx, body_top - bh // 2, bx + bw, body_top + bh // 2], fill=body)
    d.rounded_rectangle([bx, body_top - bh, bx + bw, body_top],
                        radius=bh // 2, fill=body)

    # Lens
    cx = S // 2
    cy = (body_top + S - pad) // 2 + S // 20
    r1, r2, r3 = S // 5, S // 7, S // 11
    d.ellipse([cx - r1, cy - r1, cx + r1, cy + r1], fill="#0a0f14")
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill="#0e5f78")
    d.ellipse([cx - r3, cy - r3, cx + r3, cy + r3], fill="#071820")

    # Specular highlight on lens
    h  = max(1, S // 20)
    hx = cx - r3 // 2
    hy = cy - r3 // 2
    d.ellipse([hx - h, hy - h, hx + h, hy + h], fill="#ffffff")

    # Status dot (top-right)
    dr = S // 8
    dx = S - pad - dr
    dy = pad
    d.ellipse([dx - dr, dy, dx + dr, dy + dr * 2], fill=dot)

    return img.resize((_SIZE, _SIZE), Image.LANCZOS)


class TrayIcon:
    def __init__(self, on_settings, on_quit):
        self.on_settings = on_settings
        self.on_quit = on_quit
        self._icon     = None
        self._state    = "unconfigured"

    def start(self, configured: bool = False):
        self._state = "connecting" if configured else "unconfigured"
        menu = pystray.Menu(
            pystray.MenuItem("Settings", self._click_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._click_quit),
        )
        self._icon = pystray.Icon(
            "ha-video-toast", _make_icon(self._state), self._title(), menu,
        )
        threading.Thread(target=self._icon.run, daemon=True).start()

    def set_connected(self, connected: bool):
        self._state = "connected" if connected else "error"
        self._update()

    def set_configured(self, configured: bool):
        if configured:
            self._state = "connecting"
        else:
            self._state = "unconfigured"
        self._update()

    def _update(self):
        if not self._icon:
            return
        self._icon.icon  = _make_icon(self._state)
        self._icon.title = self._title()

    def _title(self):
        return {
            "unconfigured": "HA Video Toast — Not configured (right-click → Settings)",
            "connecting":   "HA Video Toast — Connecting…",
            "connected":    "HA Video Toast — Connected",
            "error":        "HA Video Toast — Connection lost, retrying…",
        }.get(self._state, "HA Video Toast")

    def _click_settings(self, *_):
        if self.on_settings:
            self.on_settings()

    def _click_quit(self, *_):
        if self._icon:
            self._icon.stop()
        if self.on_quit:
            self.on_quit()
