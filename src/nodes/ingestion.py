"""Node 1: Ingestion & File Inventory.
Implements Layer 1 Deduplication via cryptographic SHA-256 content hashing.
Emits events to tracking bus.
"""

import hashlib
from typing import Dict, Any, List
from src.models import IngestedFile, FileType
from src.events import global_event_bus


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def ingestion_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Ingests raw file records, hashes content, and identifies exact file duplicates."""
    raw_files = state.get("raw_file_inputs", [])
    ingested_files: List[IngestedFile] = []
    seen_hashes: Dict[str, str] = {}  # sha256 -> original file_id

    global_event_bus.emit(
        event_type="INGESTION_STARTED",
        stage="1_Ingestion",
        message=f"Starting ingestion of {len(raw_files)} documents from Google Drive and audit sources.",
        data={"total_files": len(raw_files)}
    )

    for item in raw_files:
        content_bytes = item.get("content_bytes", item.get("filename", "").encode("utf-8"))
        file_hash = compute_sha256(content_bytes)
        file_type = FileType(item.get("file_type", "PDF"))
        file_id = item.get("file_id", f"file_{len(ingested_files)+1}")
        filename = item.get("filename", f"doc_{len(ingested_files)+1}")

        is_dup = False
        original_id = None
        if file_hash in seen_hashes:
            is_dup = True
            original_id = seen_hashes[file_hash]
            global_event_bus.emit(
                event_type="DUPLICATE_FILE_DETECTED",
                stage="1_Ingestion",
                message=f"Duplicate file detected: '{filename}' has identical hash to '{original_id}'. Reusing cached extraction.",
                data={"filename": filename, "original_file_id": original_id, "hash": file_hash}
            )
        else:
            seen_hashes[file_hash] = file_id
            global_event_bus.emit(
                event_type="FILE_INGESTED",
                stage="1_Ingestion",
                message=f"Ingested {file_type.value}: {filename} (SHA-256: {file_hash[:10]}...)",
                data={"file_id": file_id, "filename": filename, "type": file_type.value}
            )

        ingested_files.append(IngestedFile(
            file_id=file_id,
            filename=filename,
            file_type=file_type,
            sha256_hash=file_hash,
            size_bytes=len(content_bytes),
            is_duplicate_file=is_dup,
            original_file_id=original_id
        ))

    global_event_bus.emit(
        event_type="INGESTION_COMPLETED",
        stage="1_Ingestion",
        message=f"Ingestion completed. {len(ingested_files)} files cataloged, {sum(1 for f in ingested_files if f.is_duplicate_file)} duplicates filtered.",
        data={"cataloged_count": len(ingested_files)}
    )

    return {"files": ingested_files}
