-- Phase 7: job origin coordinates for distance filtering (jobs near driver's next location)
ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS origin_lat numeric,
  ADD COLUMN IF NOT EXISTS origin_lng numeric;

COMMENT ON COLUMN public.jobs.origin_lat IS 'Origin latitude for distance filter (e.g. jobs near driver projected_available_location)';
COMMENT ON COLUMN public.jobs.origin_lng IS 'Origin longitude for distance filter';
