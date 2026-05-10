import dnd
from toast_window import ToastWindow, HEADER_H, PROGRESS_H


class ToastManager:
    def __init__(self, root, ha_client, config):
        self.root = root
        self.ha_client = ha_client
        self.config = config
        self._toasts = []  # index 0 = rightmost (oldest), last = leftmost (newest)

    def handle_event(self, event_data):
        """Called from WebSocket thread — schedule on main thread."""
        self.root.after(0, lambda: self._handle(event_data))

    def _handle(self, event_data):
        tcfg = self.config["toast"]
        if tcfg.get("respect_dnd") and dnd.is_dnd_active():
            return

        camera = event_data.get("camera")
        if not camera:
            return

        duration = event_data.get("duration", tcfg["duration"])
        width    = event_data.get("width",    None)
        height   = event_data.get("height",   None)

        # Same camera already showing → reset its timer
        for t in self._toasts:
            if t.camera_entity == camera:
                t.reset_timer()
                return

        # Evict oldest if at capacity
        max_toasts = tcfg.get("max_toasts", 4)
        if len(self._toasts) >= max_toasts:
            self._toasts[0].close()

        self._open(camera, duration, width, height)

    def _open(self, camera_entity, duration, width=None, height=None):
        toast = ToastWindow(
            self.root,
            camera_entity,
            self.ha_client.stream_url(camera_entity),
            self.ha_client.auth_headers(),
            self.config,
            on_close=self._on_close,
            duration_override=duration,
            width_override=width,
            height_override=height,
        )
        self._toasts.append(toast)
        idx = len(self._toasts) - 1
        toast.move_to(self._slot_x(idx), self._slot_y(toast))

    def _on_close(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
        for i, t in enumerate(self._toasts):
            t.slide_to(self._slot_x(i))

    # ------------------------------------------------------------------
    # Layout math (monitor-aware)
    # ------------------------------------------------------------------

    def _monitor(self):
        from monitors import get_monitors
        idx = self.config["toast"].get("monitor_index", 0)
        mons = get_monitors()
        if mons and 0 <= idx < len(mons):
            return mons[idx]
        if mons:
            return mons[0]
        # Fallback: tkinter primary screen dimensions
        class _M:
            x = 0; y = 0
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
        return _M()

    def _slot_x(self, slot):
        """Use the actual width of the toast at that slot (may differ per event override)."""
        tcfg   = self.config["toast"]
        m      = self._monitor()
        corner = tcfg.get("corner", "bottom-right")
        # Width of toast at this slot (use its own _width if available, else config)
        t_width = self._toasts[slot]._width if slot < len(self._toasts) else tcfg["width"]
        step    = t_width + tcfg["gap"]
        if "right" in corner:
            return m.x + m.width - tcfg["margin"] - t_width - slot * step
        else:
            return m.x + tcfg["margin"] + slot * step

    def _slot_y(self, toast=None):
        tcfg    = self.config["toast"]
        m       = self._monitor()
        corner  = tcfg.get("corner", "bottom-right")
        h       = toast._height if toast else tcfg["height"]
        total_h = h + HEADER_H + PROGRESS_H
        if "bottom" in corner:
            return m.y + m.height - tcfg["taskbar_height"] - tcfg["margin"] - total_h
        else:
            return m.y + tcfg["margin"]
