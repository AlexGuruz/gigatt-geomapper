#!/usr/bin/env python
"""
Phase 5 API smoke test: ingestion + permit-candidates + create-job.
Run with: python scripts/test_phase5_api.py [BASE_URL]
Default BASE_URL: http://127.0.0.1:8080
Requires server running and Supabase configured.
"""
import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BASE = BASE.rstrip("/")


def req(method, path, body=None, headers=None):
    url = BASE + path
    h = dict(headers or {})
    data = None
    if body is not None and not isinstance(body, bytes):
        data = json.dumps(body).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    elif isinstance(body, bytes):
        data = body
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as res:
            return res.getcode(), json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except Exception:
            body = raw
        return e.code, body
    except Exception as e:
        return None, str(e)


def build_multipart(fields, boundary=b"----WebKitFormBoundary7MA4YWxkTrZu0gW"):
    """fields: list of (name, value) or (name, (filename, content, mime))."""
    parts = []
    for name, val in fields:
        parts.append(b"--" + boundary)
        if isinstance(val, tuple):
            filename, content, mime = val[0], val[1], val[2] if len(val) > 2 else b"application/octet-stream"
            if isinstance(content, str):
                content = content.encode("utf-8")
            parts.append(("Content-Disposition: form-data; name=\"%s\"; filename=\"%s\"" % (name, filename)).encode("utf-8"))
            parts.append(b"Content-Type: " + (mime if isinstance(mime, bytes) else mime.encode("utf-8")))
            parts.append(b"")
            parts.append(content)
        else:
            parts.append(("Content-Disposition: form-data; name=\"%s\"" % name).encode("utf-8"))
            parts.append(b"")
            parts.append(val.encode("utf-8") if isinstance(val, str) else val)
    parts.append(b"--" + boundary + b"--")
    return b"\r\n".join(parts), boundary


def main():
    print("Phase 5 API smoke test — base:", BASE)
    print()

    # GET /api/ingestion-documents
    code, body = req("GET", "/api/ingestion-documents")
    if code == 200:
        print("[OK] GET /api/ingestion-documents -> 200, count:", len(body) if isinstance(body, list) else "n/a")
    elif code == 503:
        print("[SKIP] GET /api/ingestion-documents -> 503 (Supabase not configured)")
        print("Done. Configure Supabase for full Phase 5 tests.")
        return
    else:
        print("[FAIL] GET /api/ingestion-documents ->", code, body)

    # GET /api/permit-candidates
    code, body = req("GET", "/api/permit-candidates")
    if code == 200:
        print("[OK] GET /api/permit-candidates -> 200, count:", len(body) if isinstance(body, list) else "n/a")
    else:
        print("[FAIL] GET /api/permit-candidates ->", code)

    # POST /api/ingestion-documents (multipart: file + source_type)
    minimal_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n198\n%%EOF"
    body_bytes, boundary = build_multipart([
        ("file", ("test.pdf", minimal_pdf, "application/pdf")),
        ("source_type", "manual_upload"),
    ])
    code, out = req("POST", "/api/ingestion-documents", body_bytes, {
        "Content-Type": "multipart/form-data; boundary=" + boundary.decode("ascii"),
        "Content-Length": str(len(body_bytes)),
    })
    if code == 200 and isinstance(out, dict) and out.get("id"):
        doc_id = out["id"]
        print("[OK] POST /api/ingestion-documents -> 200, doc_id:", doc_id[:8] + "...")
    else:
        print("[FAIL] POST /api/ingestion-documents ->", code, out)
        return

    # POST /api/ingestion-documents/:id/parse
    code, out = req("POST", "/api/ingestion-documents/" + doc_id + "/parse", None)
    if code == 200 and isinstance(out, dict) and out.get("permit_candidate"):
        cand = out["permit_candidate"]
        cand_id = cand.get("id")
        print("[OK] POST .../parse -> 200, permit_candidate id:", cand_id[:8] + "..." if cand_id else "n/a")
    else:
        print("[FAIL] POST .../parse ->", code, out)
        return

    if not cand_id:
        print("[SKIP] No permit_candidate id; skipping PATCH/approve/create-job")
        print("Done.")
        return

    # PATCH /api/permit-candidates/:id (edit)
    code, out = req("PATCH", "/api/permit-candidates/" + cand_id, {
        "origin_text": "Dallas, TX",
        "destination_text": "Oklahoma City, OK",
        "estimated_miles": 200,
        "estimated_duration_minutes": 180,
    })
    if code == 200:
        print("[OK] PATCH /api/permit-candidates/:id -> 200")
    else:
        print("[FAIL] PATCH permit-candidate ->", code, out)

    # POST /api/permit-candidates/:id/approve
    code, out = req("POST", "/api/permit-candidates/" + cand_id + "/approve", {})
    if code == 200:
        print("[OK] POST .../approve -> 200")
    else:
        print("[FAIL] POST .../approve ->", code, out)

    # POST /api/permit-candidates/:id/create-job
    code, job = req("POST", "/api/permit-candidates/" + cand_id + "/create-job", {})
    if code == 200 and isinstance(job, dict) and job.get("id"):
        job_id = job["id"]
        print("[OK] POST .../create-job -> 200, job_id:", job_id[:8] + "...")
    else:
        print("[FAIL] POST .../create-job ->", code, job)
        print("Done.")
        return

    # GET /api/jobs (unassigned should include new job)
    code, jobs = req("GET", "/api/jobs?status=unassigned")
    if code == 200 and isinstance(jobs, list) and any(str(j.get("id")) == str(job_id) for j in jobs):
        print("[OK] GET /api/jobs?status=unassigned -> 200, new job in list")
    elif code == 200:
        print("[OK] GET /api/jobs?status=unassigned -> 200 (job may be in full list)")
    else:
        print("[FAIL] GET /api/jobs ->", code)

    print()
    print("Done. Fix any [FAIL]; [SKIP] is expected when Supabase is not set up.")


if __name__ == "__main__":
    main()
