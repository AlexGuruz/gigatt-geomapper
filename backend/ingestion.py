"""
Multi-source document ingestion. Plan Phase 5, Section 10.9.
ingestion_document (raw) -> parse -> permit_candidate -> review -> job.
"""
import os
import uuid
import re
from datetime import datetime


UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")
SOURCE_TYPES = ("email_pdf", "text_screenshot", "email_screenshot", "manual_upload")


def _ensure_uploads_dir():
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    return UPLOADS_DIR


def create_ingestion_document(client, source_type, file_data=None, filename=None, mime_type=None, source_ref=None, uploaded_by=None):
    """
    Store file to data/uploads, create ingestion_document row. source_type in SOURCE_TYPES.
    file_data: bytes. filename: original name. Returns ingestion_document dict or None.
    """
    if not client or source_type not in SOURCE_TYPES:
        return None
    _ensure_uploads_dir()
    storage_key = None
    file_path = None
    if file_data and filename:
        ext = os.path.splitext(filename)[1] or ".bin"
        if not ext.startswith("."):
            ext = "." + ext
        storage_key = str(uuid.uuid4()) + ext
        file_path = os.path.join(UPLOADS_DIR, storage_key)
        try:
            with open(file_path, "wb") as f:
                f.write(file_data if isinstance(file_data, bytes) else file_data.read())
        except Exception:
            return None
    row = {
        "source_type": source_type,
        "source_ref": source_ref,
        "file_path": file_path,
        "storage_key": storage_key,
        "mime_type": mime_type or ("application/pdf" if (filename or "").lower().endswith(".pdf") else None),
        "uploaded_by": uploaded_by,
        "processing_status": "pending",
    }
    try:
        r = client.table("ingestion_documents").insert(row).execute()
        data = (r.data or []) if hasattr(r, "data") else []
        return data[0] if data else None
    except Exception:
        return None


def _extract_text_pdf(file_path):
    """Extract text from PDF. Returns (text, parse_notes)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        text = "\n".join(parts).strip() if parts else ""
        return text, "pdf_extract" if text else "no_text"
    except Exception as e:
        return "", "pdf_error: " + str(e)[:200]


def _extract_text_image(file_path):
    """Placeholder: no OCR by default. Returns (placeholder, notes)."""
    return "", "image_ocr_not_configured"


def parse_ingestion_document(client, doc_id):
    """
    Run extraction on ingestion_document; create or update permit_candidate.
    Set processing_status (parsed_partial, parsed_ready_for_review, failed) and review_status (needs_review, insufficient_data).
    Returns (permit_candidate dict or None, error_message or None).
    """
    if not client or not doc_id:
        return None, "missing doc_id"
    try:
        r = client.table("ingestion_documents").select("*").eq("id", doc_id).limit(1).execute()
        rows = (r.data or []) if hasattr(r, "data") else []
        doc = rows[0] if rows else None
    except Exception as e:
        return None, str(e)
    if not doc:
        return None, "document not found"
    file_path = doc.get("file_path") or (os.path.join(UPLOADS_DIR, doc.get("storage_key") or "") if doc.get("storage_key") else None)
    if not file_path or not os.path.isfile(file_path):
        raw_text = ""
        parse_notes = "file_not_found"
    else:
        mime = (doc.get("mime_type") or "").lower()
        if "pdf" in mime or (file_path or "").lower().endswith(".pdf"):
            raw_text, parse_notes = _extract_text_pdf(file_path)
        else:
            raw_text, parse_notes = _extract_text_image(file_path)

    processing_status = "parsed_ready_for_review" if raw_text else "parsed_partial"
    if parse_notes and "error" in parse_notes.lower():
        processing_status = "failed"
    review_status = "needs_review" if raw_text else "insufficient_data"

    try:
        client.table("ingestion_documents").update({
            "processing_status": processing_status,
            "raw_text": raw_text[:100000] if raw_text else None,
            "parse_notes": parse_notes,
            "parser_type": "pypdf" if "pdf" in (mime or "") else "placeholder",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", doc_id).execute()
    except Exception as e:
        return None, str(e)

    origin_text = None
    destination_text = None
    if raw_text:
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.search(r"\b(origin|from|pickup|start)\s*[:\-]", line, re.I):
                origin_text = re.sub(r"^(origin|from|pickup|start)\s*[:\-]\s*", "", line, flags=re.I).strip() or origin_text
            if re.search(r"\b(destination|to|delivery|end)\s*[:\-]", line, re.I):
                destination_text = re.sub(r"^(destination|to|delivery|end)\s*[:\-]\s*", "", line, flags=re.I).strip() or destination_text
        if not origin_text and " to " in raw_text:
            parts = raw_text.split(" to ", 1)
            if len(parts) == 2:
                origin_text = parts[0].strip()[-100:] if len(parts[0]) > 100 else parts[0].strip()
                destination_text = parts[1].strip()[:100] if len(parts[1]) > 100 else parts[1].strip()

    candidate_row = {
        "ingestion_document_id": doc_id,
        "origin_text": origin_text or raw_text[:200] if raw_text else None,
        "destination_text": destination_text,
        "route_text": raw_text[:5000] if raw_text else None,
        "review_status": review_status,
    }
    try:
        existing = client.table("permit_candidates").select("id").eq("ingestion_document_id", doc_id).limit(1).execute()
        existing_data = (existing.data or []) if hasattr(existing, "data") else []
        if existing_data:
            client.table("permit_candidates").update({
                **candidate_row,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", existing_data[0]["id"]).execute()
            r2 = client.table("permit_candidates").select("*").eq("id", existing_data[0]["id"]).limit(1).execute()
            out = (r2.data or [])[0] if r2.data else None
        else:
            ins = client.table("permit_candidates").insert(candidate_row).execute()
            out = (ins.data or [])[0] if ins.data else None
        return out, None
    except Exception as e:
        return None, str(e)


def list_ingestion_documents(client, processing_status=None, source_type=None):
    if not client:
        return []
    try:
        q = client.table("ingestion_documents").select("*").order("created_at", desc=True)
        if processing_status:
            q = q.eq("processing_status", processing_status)
        if source_type:
            q = q.eq("source_type", source_type)
        r = q.execute()
        return (r.data or []) if hasattr(r, "data") else []
    except Exception:
        return []


def list_permit_candidates(client, review_status=None, ingestion_document_id=None):
    if not client:
        return []
    try:
        q = client.table("permit_candidates").select("*, ingestion_documents(source_type, processing_status)").order("created_at", desc=True)
        if review_status:
            q = q.eq("review_status", review_status)
        if ingestion_document_id:
            q = q.eq("ingestion_document_id", ingestion_document_id)
        r = q.execute()
        return (r.data or []) if hasattr(r, "data") else []
    except Exception:
        try:
            q = client.table("permit_candidates").select("*").order("created_at", desc=True)
            if review_status:
                q = q.eq("review_status", review_status)
            if ingestion_document_id:
                q = q.eq("ingestion_document_id", ingestion_document_id)
            r = q.execute()
            return (r.data or []) if hasattr(r, "data") else []
        except Exception:
            return []


def get_permit_candidate(client, candidate_id):
    if not client or not candidate_id:
        return None
    try:
        r = client.table("permit_candidates").select("*").eq("id", candidate_id).limit(1).execute()
        return (r.data or [])[0] if r.data else None
    except Exception:
        return None


def update_permit_candidate(client, candidate_id, fields):
    if not client or not candidate_id or not fields:
        return None
    allowed = {"origin_text", "destination_text", "route_text", "restrictions_text", "escort_requirements",
               "estimated_miles", "estimated_duration_minutes", "issuing_state", "permit_number", "permit_type",
               "effective_from", "effective_to", "review_status"}
    payload = {k: v for k, v in fields.items() if k in allowed}
    if not payload:
        return get_permit_candidate(client, candidate_id)
    payload["updated_at"] = datetime.utcnow().isoformat()
    try:
        client.table("permit_candidates").update(payload).eq("id", candidate_id).execute()
        return get_permit_candidate(client, candidate_id)
    except Exception:
        return None


def approve_permit_candidate(client, candidate_id):
    return update_permit_candidate(client, candidate_id, {"review_status": "approved"})


def reject_permit_candidate(client, candidate_id):
    return update_permit_candidate(client, candidate_id, {"review_status": "rejected"})


def create_job_from_candidate(client, candidate_id):
    """
    Create job from approved permit_candidate. Enforce required: origin, destination (from origin_text, destination_text).
    Returns (job dict, error_message).
    """
    cand = get_permit_candidate(client, candidate_id)
    if not cand:
        return None, "permit_candidate not found"
    if (cand.get("review_status") or "").lower() != "approved":
        return None, "candidate must be approved before creating job"
    origin = (cand.get("origin_text") or "").strip()
    destination = (cand.get("destination_text") or "").strip()
    if not origin or not destination:
        return None, "origin and destination are required"
    from backend.jobs import create_job
    from backend.route_states import ensure_job_route_states
    payload = {
        "origin": origin,
        "destination": destination,
        "route_text": cand.get("route_text"),
        "estimated_miles": cand.get("estimated_miles"),
        "estimated_duration": cand.get("estimated_duration_minutes"),
        "escort_requirements": cand.get("escort_requirements"),
    }
    job = create_job(client, payload)
    if not job:
        return None, "create_job failed"
    try:
        client.table("jobs").update({
            "permit_candidate_id": candidate_id,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", job["id"]).execute()
        ensure_job_route_states(client, job["id"], origin, destination, source="permit_candidate")
    except Exception:
        pass
    from backend.jobs import get_job as _get_job
    job_id = job.get("id") if isinstance(job, dict) else None
    if not job_id:
        # Should be rare, but avoid returning null when job insert succeeded.
        return job, None
    fetched = _get_job(client, job_id)
    # If lookup fails (e.g. transient type/encoding mismatch), still return the job dict we just created.
    return fetched or job, None
