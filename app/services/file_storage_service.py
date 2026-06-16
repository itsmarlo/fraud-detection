import hashlib
import mimetypes
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from PIL import UnidentifiedImageError
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.security import validate_extension
from app.models.file_schema import DocumentType, FileMetadata
from app.services.file_metadata_service import FileMetadataService, file_metadata_service
from app.services.image_support import (
    IMAGE_EXTENSIONS,
    IMAGE_MIME_TYPES_BY_EXTENSION,
    validate_image_content,
)


class FileValidationError(ValueError):
    pass


class FileStorageService:
    def __init__(
        self,
        metadata_service: FileMetadataService | None = None,
        upload_dir: Path | None = None,
    ) -> None:
        self.settings = get_settings()
        self.upload_dir = upload_dir or self.settings.upload_dir
        self.metadata_service = metadata_service or file_metadata_service
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def store(
        self,
        claim_id: str,
        document_type: DocumentType,
        upload: UploadFile,
    ) -> FileMetadata:
        original_filename = Path(upload.filename or "upload").name
        try:
            extension = validate_extension(original_filename)
        except ValueError as exc:
            raise FileValidationError(str(exc)) from exc

        content = await upload.read(self.settings.max_upload_size_mb * 1024 * 1024 + 1)
        if not content:
            raise FileValidationError("Empty files are not allowed")
        if len(content) > self.settings.max_upload_size_mb * 1024 * 1024:
            raise FileValidationError(
                f"File exceeds the {self.settings.max_upload_size_mb} MB upload limit"
            )

        content_type = (upload.content_type or mimetypes.guess_type(original_filename)[0] or "").lower()
        if content_type not in self.settings.allowed_mime_types:
            raise FileValidationError(f"Unsupported MIME type: {content_type or '(missing)'}")
        expected_mime_types = {
            **IMAGE_MIME_TYPES_BY_EXTENSION,
            ".pdf": {"application/pdf"},
            ".txt": {"text/plain"},
            ".docx": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            },
        }
        if content_type not in expected_mime_types[extension]:
            raise FileValidationError(
                f"MIME type {content_type} does not match extension {extension}"
            )
        self._validate_content(extension, content)

        file_id = f"FILE-{uuid4().hex[:12].upper()}"
        stored_filename = f"{uuid4().hex}{extension}"
        destination = self.upload_dir / stored_filename
        destination.write_bytes(content)

        metadata = FileMetadata(
            file_id=file_id,
            claim_id=claim_id,
            document_type=document_type,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            file_size=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
            upload_timestamp=datetime.now(UTC),
        )
        return self.metadata_service.add(metadata)

    def path_for(self, metadata: FileMetadata) -> Path:
        candidate = (self.upload_dir / metadata.stored_filename).resolve()
        if self.upload_dir.resolve() not in candidate.parents:
            raise FileValidationError("Invalid stored filename")
        return candidate

    def remove_for_claim(self, claim_id: str) -> int:
        removed = self.metadata_service.remove_for_claim(claim_id)
        for metadata in removed:
            path = self.path_for(metadata)
            path.unlink(missing_ok=True)
        return len(removed)

    @staticmethod
    def _validate_content(extension: str, content: bytes) -> None:
        try:
            if extension in IMAGE_EXTENSIONS:
                validate_image_content(extension, content)
            elif extension == ".pdf":
                if not content.startswith(b"%PDF"):
                    raise FileValidationError("File content is not a PDF")
                PdfReader(BytesIO(content))
            elif extension == ".docx":
                with ZipFile(BytesIO(content)) as archive:
                    if "word/document.xml" not in archive.namelist():
                        raise FileValidationError("File content is not a valid DOCX document")
            elif extension == ".txt":
                content.decode("utf-8")
        except (UnidentifiedImageError, OSError, BadZipFile, UnicodeDecodeError, Exception) as exc:
            if isinstance(exc, FileValidationError):
                raise
            raise FileValidationError(f"File is corrupt or does not match its extension: {exc}") from exc


file_storage_service = FileStorageService()
