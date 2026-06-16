from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORT_AVAILABLE = True
except ImportError:
    HEIF_SUPPORT_AVAILABLE = False


IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

IMAGE_MIME_TYPES_BY_EXTENSION = {
    ".avif": {"image/avif"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
    ".gif": {"image/gif"},
    ".heic": {"image/heic", "image/heic-sequence"},
    ".heif": {"image/heif", "image/heif-sequence"},
    ".jpeg": {"image/jpeg"},
    ".jpg": {"image/jpeg"},
    ".png": {"image/png"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
    ".webp": {"image/webp"},
}

AI_NATIVE_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_image_content(extension: str, content: bytes) -> None:
    if extension in {".heic", ".heif"} and not HEIF_SUPPORT_AVAILABLE:
        raise ValueError(
            "HEIC/HEIF support is unavailable. Install the pillow-heif dependency."
        )
    with Image.open(BytesIO(content)) as image:
        image.verify()


def ai_image_payload(file_path: Path, content_type: str) -> tuple[bytes, str]:
    if content_type in AI_NATIVE_IMAGE_MIME_TYPES:
        return file_path.read_bytes(), content_type

    with Image.open(file_path) as image:
        image.seek(0)
        normalized = ImageOps.exif_transpose(image).convert("RGB")
        output = BytesIO()
        normalized.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue(), "image/jpeg"
