# Migration Path (Plan Section 8.6)

**Purpose:** Documents the V1 migration decision. See **plan.md** Section 8.6 and Section 11 (Phased Build Order).

**Last updated:** 2026-03-14

---

**V1 Decision: Option A — Parallel transition**

| Layer | Source of truth | Notes |
|-------|-----------------|-------|
| **Opportunity (market routes)** | JSON (`data/routes.json`) | Unchanged. Poller, email/broker/text ingestion, left sidebar, route cards. No migration of opportunity routes to DB. |
| **Dispatch** | Supabase | Drivers, jobs, assignments, location, permits, availability. New backend and tables. |

**Bridge:** Market routes and dispatch jobs remain separate. A future "create job from opportunity" flow (Phase 5+) can copy a market route into a dispatch job. No immediate dual-write or full cutover.
