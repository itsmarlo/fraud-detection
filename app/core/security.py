from pathlib import Path

from app.services.image_support import IMAGE_EXTENSIONS


ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf", ".txt", ".docx"}
EXECUTABLE_EXTENSIONS = {".exe", ".dll", ".bat", ".cmd", ".com", ".sh", ".msi", ".jar", ".js"}


def validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in EXECUTABLE_EXTENSIONS or suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {suffix or '(none)'}")
    return suffix
