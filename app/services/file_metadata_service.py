import json
import threading
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.file_schema import FileMetadata


class FileMetadataService:
    def __init__(self, metadata_file: Path | None = None) -> None:
        self.metadata_file = metadata_file or get_settings().metadata_file
        self._lock = threading.RLock()
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.metadata_file.exists():
            self._write({"files": []})

    def _read(self) -> dict[str, Any]:
        with self._lock:
            try:
                data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
                data.setdefault("files", [])
                data.setdefault("claim_identities", [])
                return data
            except (json.JSONDecodeError, OSError):
                return {"files": [], "claim_identities": []}

    def _write(self, data: dict[str, Any]) -> None:
        with self._lock:
            temporary = self.metadata_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(self.metadata_file)

    def add(self, metadata: FileMetadata) -> FileMetadata:
        data = self._read()
        data["files"].append(metadata.model_dump(mode="json"))
        self._write(data)
        return metadata

    def get(self, file_id: str) -> FileMetadata | None:
        for item in self._read()["files"]:
            if item["file_id"] == file_id:
                return FileMetadata.model_validate(item)
        return None

    def list_for_claim(self, claim_id: str) -> list[FileMetadata]:
        return [
            FileMetadata.model_validate(item)
            for item in self._read()["files"]
            if item["claim_id"] == claim_id
        ]

    def list_all(self) -> list[FileMetadata]:
        return [FileMetadata.model_validate(item) for item in self._read()["files"]]

    def remove_for_claim(self, claim_id: str) -> list[FileMetadata]:
        data = self._read()
        removed = [
            FileMetadata.model_validate(item)
            for item in data["files"]
            if item["claim_id"] == claim_id
        ]
        data["files"] = [
            item for item in data["files"] if item["claim_id"] != claim_id
        ]
        self._write(data)
        return removed

    def update_analysis(
        self,
        file_id: str,
        status: str,
        result: dict[str, Any],
    ) -> FileMetadata:
        data = self._read()
        for index, item in enumerate(data["files"]):
            if item["file_id"] == file_id:
                item["analysis_status"] = status
                item["analysis_result"] = result
                data["files"][index] = item
                self._write(data)
                return FileMetadata.model_validate(item)
        raise KeyError(file_id)

    def claims_for_checksum(self, checksum: str, exclude_claim_id: str | None = None) -> list[str]:
        claims = {
            item["claim_id"]
            for item in self._read()["files"]
            if item["checksum"] == checksum and item["claim_id"] != exclude_claim_id
        }
        return sorted(claims)

    def claims_for_identity(
        self,
        field: str,
        value: str | None,
        exclude_claim_id: str,
    ) -> list[str]:
        if not value:
            return []
        claims = {
            item["claim_id"]
            for item in self._read()["claim_identities"]
            if item.get(field) == value and item["claim_id"] != exclude_claim_id
        }
        return sorted(claims)

    def register_claim_identity(
        self,
        claim_id: str,
        bank_account_hash: str | None,
        phone_hash: str | None,
        email_hash: str | None,
    ) -> None:
        data = self._read()
        record = {
            "claim_id": claim_id,
            "bank_account_hash": bank_account_hash,
            "phone_hash": phone_hash,
            "email_hash": email_hash,
        }
        for index, item in enumerate(data["claim_identities"]):
            if item["claim_id"] == claim_id:
                data["claim_identities"][index] = record
                self._write(data)
                return
        data["claim_identities"].append(record)
        self._write(data)


file_metadata_service = FileMetadataService()
