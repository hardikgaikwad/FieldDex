"""Photo handling: HEIC/JPEG in, a clean JPEG plus pixel-art card art out."""
import hashlib
import io
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image, ImageEnhance, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

VIEW_MAX = 1280     # stored photo, shown when you tap a card
VISION_MAX = 896    # what the vision model sees
PIXEL_SIZE = 48     # card art resolution
PIXEL_COLOURS = 20

_DATETIME_ORIGINAL = next(k for k, v in ExifTags.TAGS.items() if v == "DateTimeOriginal")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def open_image(data: bytes) -> tuple[Image.Image, str | None]:
    """Open any supported photo upright; also return when it was taken, if the EXIF says."""
    img = Image.open(io.BytesIO(data))
    taken = None
    try:
        raw = img.getexif().get_ifd(ExifTags.IFD.Exif).get(_DATETIME_ORIGINAL)
        if raw:
            taken = datetime.strptime(raw.strip("\x00 "), "%Y:%m:%d %H:%M:%S").isoformat(timespec="seconds")
    except (ValueError, KeyError, AttributeError):
        pass
    return ImageOps.exif_transpose(img).convert("RGB"), taken


def save_view(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    view = img.copy()
    view.thumbnail((VIEW_MAX, VIEW_MAX))
    view.save(path, "JPEG", quality=85)


def vision_bytes(img: Image.Image) -> bytes:
    small = img.copy()
    small.thumbnail((VISION_MAX, VISION_MAX))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def save_pixel_art(img: Image.Image, path: Path) -> None:
    """Centre-crop, shrink to a tiny grid, cut the palette: instant pixel art from a real photo."""
    path.parent.mkdir(parents=True, exist_ok=True)
    square = ImageOps.fit(img, (PIXEL_SIZE * 8, PIXEL_SIZE * 8), Image.Resampling.LANCZOS)
    square = ImageEnhance.Color(square).enhance(1.35)
    square = ImageEnhance.Contrast(square).enhance(1.15)
    tiny = square.resize((PIXEL_SIZE, PIXEL_SIZE), Image.Resampling.BOX)
    tiny = tiny.quantize(colors=PIXEL_COLOURS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    tiny.save(path, "PNG")
