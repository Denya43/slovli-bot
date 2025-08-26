from io import BytesIO
import os
from typing import List, Optional, Tuple

from telegram import Update

from .config import ATTEMPTS, WORD_LEN

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:  # noqa: BLE001
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore


def _load_cyrillic_font(pixel_size: int):
    if ImageFont is None:
        return None
    candidates: List[str] = [
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ]
    windir = os.environ.get("WINDIR", r"C:\\Windows")
    candidates.extend(
        [
            os.path.join(windir, "Fonts", p)
            for p in (
                "arialbd.ttf",
                "arial.ttf",
                "segoeuib.ttf",
                "segoeui.ttf",
                "tahoma.ttf",
                "calibrib.ttf",
                "calibri.ttf",
            )
        ]
    )
    candidates.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, pixel_size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def render_attempts_image(attempts: List[Tuple[str, List[str]]], word_length: int = 5) -> Optional[bytes]:
    if Image is None:
        return None

    tile, gap, padding = 80, 10, 20
    rows, cols = ATTEMPTS, word_length

    width = padding * 2 + cols * tile + (cols - 1) * gap
    height = padding * 2 + rows * tile + (rows - 1) * gap

    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    colors = {
        "correct": (106, 170, 100),
        "present": (201, 180, 88),
        "absent": (120, 124, 126),
        "empty": (211, 214, 218),
    }
    border_color = (120, 124, 126)
    text_color = (255, 255, 255)
    font = _load_cyrillic_font(int(tile * 0.5))

    for r in range(rows):
        for c in range(cols):
            x0 = padding + c * (tile + gap)
            y0 = padding + r * (tile + gap)
            x1, y1 = x0 + tile, y0 + tile

            if r < len(attempts):
                guess, marks = attempts[r]
                ch = guess[c]
                fill = colors.get(marks[c], colors["absent"])
            else:
                ch = ""
                fill = colors["empty"]

            draw.rectangle([x0, y0, x1, y1], fill=fill)
            draw.rectangle([x0, y0, x1, y1], outline=border_color, width=2)

            if ch:
                try:
                    bbox = draw.textbbox((0, 0), ch, font=font)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                except Exception:  # noqa: BLE001
                    tw, th = draw.textsize(ch, font=font)  # type: ignore[attr-defined]
                draw.text((x0 + (tile - tw) // 2, y0 + (tile - th) // 2 - 2), ch, font=font, fill=text_color)

    bio = BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


async def reply_with_grid_image(update: Update, attempts: List[Tuple[str, List[str]]], word_length: int = 5):
    img_bytes = render_attempts_image(attempts, word_length)
    if not img_bytes:
        return
    bio = BytesIO(img_bytes)
    try:
        bio.name = "grid.png"  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    bio.seek(0)
    await update.message.reply_photo(photo=bio)



