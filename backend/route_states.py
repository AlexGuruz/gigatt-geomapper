"""
Derive job_route_states from job origin/destination (v1: rough inference).
Plan 10.13.2: fallback = extract state from origin and destination.
"""
import re


# US state 2-letter codes (uppercase) for validation
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


def _extract_state_from_text(text):
    """Extract a 2-letter state code from text like 'Dallas, TX' or 'TX'."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    # ", TX" or " TX" at end
    m = re.search(r",\s*([A-Za-z]{2})\s*$", text)
    if m:
        code = m.group(1).upper()
        if code in US_STATE_CODES:
            return code
    # Standalone 2-letter word (e.g. "TX" or "in TX")
    for part in re.split(r"[\s,;]+", text):
        part = part.strip().upper()
        if len(part) == 2 and part in US_STATE_CODES:
            return part
    return None


def derive_route_states_for_job(origin_text, destination_text):
    """
    Return list of unique state codes (2-letter) from job origin and destination.
    Plan 10.13.2 priority 3: rough inference from origin/destination.
    """
    states = []
    for text in (origin_text, destination_text):
        code = _extract_state_from_text(text)
        if code and code not in states:
            states.append(code)
    return states


def ensure_job_route_states(client, job_id, origin_text, destination_text, source="origin_destination"):
    """
    Ensure job_route_states rows exist for this job. Replaces any existing rows for job_id.
    """
    if not client or not job_id:
        return
    states = derive_route_states_for_job(origin_text or "", destination_text or "")
    try:
        client.table("job_route_states").delete().eq("job_id", job_id).execute()
    except Exception:
        pass
    for i, state_code in enumerate(states):
        try:
            client.table("job_route_states").insert(
                {
                    "job_id": job_id,
                    "state_code": state_code,
                    "source": source,
                    "sort_order": i,
                }
            ).execute()
        except Exception:
            pass
