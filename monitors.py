"""
Cross-platform monitor enumeration.
Windows: uses ctypes EnumDisplayMonitors + GetMonitorInfoW (reliable, no extra deps).
Other:   falls back to screeninfo, then single-monitor stub.
"""

import platform


class Monitor:
    def __init__(self, x, y, width, height, name, is_primary=False):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.name = name
        self.is_primary = is_primary

    def label(self, index):
        primary = "  ★" if self.is_primary else ""
        return f"Monitor {index + 1}  —  {self.width}×{self.height}  [{self.name}]{primary}"

    def __repr__(self):
        return f"Monitor({self.x},{self.y} {self.width}×{self.height} {self.name})"


def get_monitors():
    if platform.system() == "Windows":
        try:
            return _windows_monitors()
        except Exception:
            pass
    try:
        from screeninfo import get_monitors as _sm
        return [
            Monitor(m.x, m.y, m.width, m.height,
                    name=m.name or f"Display {i + 1}")
            for i, m in enumerate(_sm())
        ]
    except Exception:
        pass
    return []


def _windows_monitors():
    import ctypes
    import ctypes.wintypes as wt

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left",   ctypes.c_long),
            ("top",    ctypes.c_long),
            ("right",  ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ("cbSize",    wt.DWORD),
            ("rcMonitor", RECT),
            ("rcWork",    RECT),
            ("dwFlags",   wt.DWORD),
            ("szDevice",  ctypes.c_wchar * 32),
        ]

    collected = []

    def _cb(hMon, _hDC, _lpRect, _lParam):
        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(MONITORINFOEX)
        ctypes.windll.user32.GetMonitorInfoW(hMon, ctypes.byref(info))
        r = info.rcMonitor
        # "\\.\DISPLAY1" → "DISPLAY1"
        raw_name = info.szDevice.strip("\x00")
        name = raw_name.lstrip("\\").lstrip(".").lstrip("\\")
        collected.append(Monitor(
            x=r.left,
            y=r.top,
            width=r.right - r.left,
            height=r.bottom - r.top,
            name=name,
            is_primary=bool(info.dwFlags & 1),
        ))
        return True

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wt.HMONITOR, wt.HDC, ctypes.POINTER(RECT), wt.LPARAM,
    )
    ctypes.windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(_cb), 0)
    # Primary first, then left-to-right
    collected.sort(key=lambda m: (not m.is_primary, m.x))
    return collected
