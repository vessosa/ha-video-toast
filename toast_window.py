import io
import queue
import threading
import tkinter as tk

import requests
from PIL import Image, ImageTk

HEADER_H   = 30
PROGRESS_H = 3

# Fade
FADE_IN_STEP  = 0.12
FADE_OUT_STEP = 0.20
FADE_INTERVAL = 16   # ms

# Theme
BG      = "#18181b"
BG_VID  = "#09090b"
ACCENT  = "#06b6d4"
FG      = "#f4f4f5"
FG2     = "#a1a1aa"
FG3     = "#52525b"

ANIM_FPS           = 60
ANIM_INTERVAL      = 1000 // ANIM_FPS
FRAME_INTERVAL     = 33
COUNTDOWN_INTERVAL = 100


class ToastWindow:
    def __init__(self, root, camera_entity, stream_url, auth_headers, config, on_close,
                 duration_override=None):
        self.root          = root
        self.camera_entity = camera_entity
        self.stream_url    = stream_url
        self.auth_headers  = auth_headers
        self.config        = config
        self.on_close      = on_close

        tcfg = config["toast"]
        self.duration  = duration_override if duration_override is not None else tcfg["duration"]
        self.remaining = float(self.duration)

        self._frame_queue = queue.Queue(maxsize=2)
        self._running     = True
        self._after_ids   = []

        self.x = 0
        self.y = 0
        self._anim_target_x = 0
        self._anim_start_x  = 0
        self._anim_elapsed  = 0
        self._anim_running  = False

        self._build()
        self._start_stream_thread()
        self._schedule(FRAME_INTERVAL,     self._update_frame)
        self._schedule(COUNTDOWN_INTERVAL, self._tick_countdown)
        self._fade_in(0.0)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        tcfg    = self.config["toast"]
        w       = tcfg["width"]
        h       = tcfg["height"]
        total_h = h + HEADER_H + PROGRESS_H

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.win.geometry(f"{w}x{total_h}+0+0")
        # Full 1px ACCENT border via window background
        self.win.configure(bg=ACCENT)

        inner = tk.Frame(self.win, bg=BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Header
        header = tk.Frame(inner, bg=BG, height=HEADER_H)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # App icon
        try:
            from logo import make_app_icon
            from PIL import ImageTk as _ITk
            icon_img = make_app_icon(size=HEADER_H - 10)
            self._icon_photo = _ITk.PhotoImage(icon_img)
            tk.Label(header, image=self._icon_photo, bg=BG, bd=0).pack(
                side=tk.LEFT, padx=(8, 4),
            )
        except Exception:
            tk.Label(header, text="●", bg=BG, fg=ACCENT,
                     font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(8, 2))

        # Camera name
        cam_label = self.camera_entity.replace("camera.", "").replace("_", " ").title()
        tk.Label(header, text=cam_label, bg=BG, fg=FG,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        # × close (far right)
        close = tk.Label(header, text=" × ", bg=BG, fg=FG3,
                         font=("Segoe UI", 13), cursor="hand2")
        close.pack(side=tk.RIGHT, padx=(0, 4))
        close.bind("<Button-1>", lambda _: self.close())
        close.bind("<Enter>",    lambda _: close.config(fg=FG))
        close.bind("<Leave>",    lambda _: close.config(fg=FG3))

        # "View Live" cyan pill (right of name, left of ×)
        view = tk.Label(header, text="  View Live ↗  ", bg=ACCENT, fg="#09090b",
                        font=("Segoe UI", 8, "bold"), cursor="hand2", padx=2, pady=2)
        view.pack(side=tk.RIGHT, padx=(0, 8), pady=5)
        view.bind("<Button-1>", lambda _: self._open_in_ha())
        view.bind("<Enter>",    lambda _: view.config(bg="#0891b2"))
        view.bind("<Leave>",    lambda _: view.config(bg=ACCENT))

        # Video area
        self.video_label = tk.Label(inner, bg=BG_VID, width=w, height=h)
        self.video_label.pack(fill=tk.BOTH, expand=True)

        self._status_text = tk.Label(
            self.video_label, text="Connecting…",
            bg=BG_VID, fg=FG3, font=("Segoe UI", 10),
        )
        self._status_text.place(relx=0.5, rely=0.5, anchor="center")

        # Progress bar
        self._prog_canvas = tk.Canvas(
            inner, height=PROGRESS_H, bg=BG, highlightthickness=0,
        )
        self._prog_canvas.pack(fill=tk.X)
        self._prog_rect = self._prog_canvas.create_rectangle(
            0, 0, w, PROGRESS_H, fill=ACCENT, outline="",
        )

        self.win.bind("<Button-1>", lambda _: self.reset_timer())

    # ── MJPEG stream ──────────────────────────────────────────────────────────

    def _start_stream_thread(self):
        threading.Thread(target=self._pull_frames, daemon=True).start()

    def _pull_frames(self):
        tcfg = self.config["toast"]
        target_w, target_h = tcfg["width"], tcfg["height"]
        try:
            resp = _get_stream(self.stream_url, self.auth_headers)
            buf  = b""
            for chunk in resp.iter_content(chunk_size=4096):
                if not self._running:
                    break
                buf += chunk
                while True:
                    start = buf.find(b"\xff\xd8")
                    end   = buf.find(b"\xff\xd9", start + 2) if start != -1 else -1
                    if start == -1 or end == -1:
                        break
                    jpg = buf[start:end + 2]
                    buf = buf[end + 2:]
                    try:
                        img = Image.open(io.BytesIO(jpg))
                        img = img.resize((target_w, target_h), Image.LANCZOS)
                        if not self._frame_queue.full():
                            self._frame_queue.put_nowait(img)
                    except Exception:
                        pass
        except Exception:
            if self._running:
                self._frame_queue.put_nowait(None)

    def _update_frame(self):
        if not self._running:
            return
        try:
            frame = self._frame_queue.get_nowait()
            if frame is None:
                self._status_text.config(text="No signal", fg="#ef4444")
            else:
                if self._status_text.winfo_ismapped():
                    self._status_text.place_forget()
                photo = ImageTk.PhotoImage(frame)
                self.video_label.config(image=photo)
                self.video_label._photo = photo
        except queue.Empty:
            pass
        self._schedule(FRAME_INTERVAL, self._update_frame)

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _tick_countdown(self):
        if not self._running:
            return
        self.remaining = max(0.0, self.remaining - COUNTDOWN_INTERVAL / 1000)
        frac = self.remaining / self.duration
        w = self.config["toast"]["width"]
        self._prog_canvas.coords(self._prog_rect, 0, 0, int(w * frac), PROGRESS_H)
        if self.remaining <= 0:
            self.close()
        else:
            self._schedule(COUNTDOWN_INTERVAL, self._tick_countdown)

    def reset_timer(self):
        self.remaining = float(self.duration)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_in_ha(self):
        threading.Thread(target=self._open_in_ha_worker, daemon=True).start()

    def _open_in_ha_worker(self):
        import webbrowser
        ha_url = self.config.get("ha_url", "").rstrip("/")
        token  = self.config.get("token", "")
        url    = ha_url
        try:
            resp = _get_with_ssl_fallback(
                f"{ha_url}/api/states/{self.camera_entity}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=3,
            )
            cam_token = resp.json().get("attributes", {}).get("access_token", "")
            if cam_token:
                url = (f"{ha_url}/api/camera_proxy_stream/{self.camera_entity}"
                       f"?token={cam_token}")
        except Exception:
            pass
        webbrowser.open(url)

    # ── Position + slide animation ────────────────────────────────────────────

    def move_to(self, x, y):
        self.x = x
        self.y = y
        self._anim_target_x = x
        self.win.geometry(f"+{x}+{y}")

    def slide_to(self, target_x):
        self._anim_target_x = target_x
        self._anim_start_x  = self.x
        self._anim_elapsed  = 0
        if not self._anim_running:
            self._anim_running = True
            self._schedule(ANIM_INTERVAL, self._anim_step)

    def _anim_step(self):
        if not self._running:
            return
        self._anim_elapsed += ANIM_INTERVAL
        t     = min(1.0, self._anim_elapsed / 200)
        eased = 1 - (1 - t) ** 3
        self.x = int(self._anim_start_x + (self._anim_target_x - self._anim_start_x) * eased)
        self.win.geometry(f"+{self.x}+{self.y}")
        if t < 1.0:
            self._schedule(ANIM_INTERVAL, self._anim_step)
        else:
            self.x = self._anim_target_x
            self._anim_running = False

    # ── Fade in / fade out ────────────────────────────────────────────────────

    def _fade_in(self, alpha):
        if not self._running:
            return
        alpha = min(1.0, alpha + FADE_IN_STEP)
        self.win.attributes("-alpha", alpha)
        if alpha < 1.0:
            self._schedule(FADE_INTERVAL, lambda: self._fade_in(alpha))

    def _fade_out(self, alpha):
        alpha = max(0.0, alpha - FADE_OUT_STEP)
        try:
            self.win.attributes("-alpha", alpha)
        except Exception:
            self._destroy()
            return
        if alpha <= 0.0:
            self._destroy()
        else:
            self.win.after(FADE_INTERVAL, lambda: self._fade_out(alpha))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _schedule(self, delay, fn):
        if not self._running:
            return
        aid = self.root.after(delay, fn)
        self._after_ids.append(aid)

    def close(self):
        if not self._running:
            return
        self._running = False
        for aid in self._after_ids:
            try:
                self.root.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        self._fade_out(self.win.attributes("-alpha"))

    def _destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        if self.on_close:
            self.on_close(self)


# ── Network helpers ───────────────────────────────────────────────────────────

def _get_stream(url, headers):
    try:
        return requests.get(url, stream=True, headers=headers, timeout=10, verify=True)
    except requests.exceptions.SSLError:
        return requests.get(url, stream=True, headers=headers, timeout=10, verify=False)


def _get_with_ssl_fallback(url, **kwargs):
    try:
        return requests.get(url, verify=True, **kwargs)
    except requests.exceptions.SSLError:
        return requests.get(url, verify=False, **kwargs)
