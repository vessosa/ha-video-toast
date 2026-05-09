"""
App icon: camera silhouette drawn at 4× then downsampled for smooth antialiasing.
"""

from PIL import Image, ImageDraw

_SCALE = 4


def make_app_icon(size: int = 20) -> Image.Image:
    """Camera icon, square, transparent background. size = final px."""
    S = size * _SCALE
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    p   = S // 10        # outer padding
    r   = S // 7         # corner radius of body

    # --- camera body ------------------------------------------------
    body_top = p + S // 7   # leave room for viewfinder bump above
    d.rounded_rectangle([p, body_top, S - p, S - p],
                        radius=r, fill="#06b6d4")

    # --- viewfinder bump (top-left of body) -------------------------
    bw = S // 3
    bh = S // 7
    bx = p + S // 10
    # bridge between bump and body
    d.rectangle([bx, body_top - bh // 2, bx + bw, body_top + bh // 2],
                fill="#06b6d4")
    d.rounded_rectangle([bx, body_top - bh, bx + bw, body_top],
                        radius=bh // 2, fill="#06b6d4")

    # --- lens -------------------------------------------------------
    cx = S // 2
    cy = (body_top + S - p) // 2 + S // 20   # slightly below centre

    r1 = S // 4              # outer ring  (dark)
    r2 = r1 - S // 14        # middle ring (lighter)
    r3 = r2 - S // 14        # inner glass (dark)

    d.ellipse([cx - r1, cy - r1, cx + r1, cy + r1], fill="#0a0f14")
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill="#0e5f78")
    d.ellipse([cx - r3, cy - r3, cx + r3, cy + r3], fill="#071820")

    # specular highlight
    h = max(2, S // 14)
    hx = cx - r3 // 2
    hy = cy - r3 // 2
    d.ellipse([hx - h, hy - h, hx + h, hy + h], fill="#ffffff")

    return img.resize((size, size), Image.LANCZOS)
