from pathlib import Path


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".txt", ".docx"}
EXECUTABLE_EXTENSIONS = {".exe", ".dll", ".bat", ".cmd", ".com", ".sh", ".msi", ".jar", ".js"}


def validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in EXECUTABLE_EXTENSIONS or suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {suffix or '(none)'}")
    return suffix
