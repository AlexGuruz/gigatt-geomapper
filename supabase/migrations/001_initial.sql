-- GIGATT Geomapper - Phase 1 Initial Schema
-- Run in Supabase SQL editor after creating project.
-- Migration path: Option A - JSON for opportunity, Supabase for dispatch only.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Profiles: extends auth.users with role (auth.users comes from Supabase Auth)
CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email text,
  role text NOT NULL CHECK (role IN ('driver', 'dispatcher', 'admin')) DEFAULT 'driver',
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Driver profiles: driver-specific data
CREATE TABLE public.driver_profiles (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  name text,
  phone text,
  status text NOT NULL CHECK (status IN ('off_duty', 'available', 'assigned', 'en_route', 'completed')) DEFAULT 'off_duty',
  last_seen_at timestamptz,
  last_location_at timestamptz,
  last_status_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Dispatcher profiles
CREATE TABLE public.dispatcher_profiles (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Driver last location (current position, fast lookup)
CREATE TABLE public.driver_last_location (
  driver_id uuid PRIMARY KEY REFERENCES public.driver_profiles(id) ON DELETE CASCADE,
  lat double precision NOT NULL,
  lng double precision NOT NULL,
  timestamp timestamptz NOT NULL,
  heading double precision,
  speed double precision,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Location history: append-only trail (retention: 90 days, implement via cron or policy)
CREATE TABLE public.location_history (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  driver_id uuid NOT NULL REFERENCES public.driver_profiles(id) ON DELETE CASCADE,
  event_id text NOT NULL,
  lat double precision NOT NULL,
  lng double precision NOT NULL,
  timestamp timestamptz NOT NULL,
  speed double precision,
  heading double precision,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(driver_id, event_id)
);

CREATE INDEX idx_location_history_driver_timestamp ON public.location_history(driver_id, timestamp DESC);

-- Driver availability calendar
CREATE TYPE availability_type AS ENUM ('available', 'unavailable', 'limited');

CREATE TABLE public.driver_availability (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  driver_id uuid NOT NULL REFERENCES public.driver_profiles(id) ON DELETE CASCADE,
  date date NOT NULL,
  availability_type availability_type NOT NULL,
  start_time time,
  end_time time,
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(driver_id, date)
);

-- Driver state permissions (allowlist)
CREATE TABLE public.driver_state_permissions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  driver_id uuid NOT NULL REFERENCES public.driver_profiles(id) ON DELETE CASCADE,
  state_code char(2) NOT NULL,
  allowed boolean NOT NULL DEFAULT true,
  source text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(driver_id, state_code)
);

-- Ingestion documents (raw input - first object in chain)
CREATE TYPE source_type AS ENUM ('email_pdf', 'text_screenshot', 'email_screenshot', 'manual_upload');
CREATE TYPE processing_status AS ENUM ('pending', 'parsed_partial', 'parsed_ready_for_review', 'failed');

CREATE TABLE public.ingestion_documents (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_type source_type NOT NULL,
  source_ref text,
  file_path text,
  storage_key text,
  mime_type text,
  uploaded_by uuid REFERENCES auth.users(id),
  received_at timestamptz NOT NULL DEFAULT now(),
  processing_status processing_status NOT NULL DEFAULT 'pending',
  raw_text text,
  parse_notes text,
  parser_type text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Permit candidates (parsed, needs review)
CREATE TYPE review_status AS ENUM ('needs_review', 'insufficient_data', 'approved', 'rejected');

CREATE TABLE public.permit_candidates (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  ingestion_document_id uuid REFERENCES public.ingestion_documents(id) ON DELETE SET NULL,
  issuing_state text,
  permit_number text,
  permit_type text,
  effective_from date,
  effective_to date,
  origin_text text,
  destination_text text,
  route_text text,
  restrictions_text text,
  escort_requirements text,
  estimated_miles integer,
  estimated_duration_minutes integer,
  parse_confidence numeric(3,2),
  review_status review_status NOT NULL DEFAULT 'needs_review',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Permits (optional canonical, after approval)
CREATE TABLE public.permits (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  permit_candidate_id uuid REFERENCES public.permit_candidates(id) ON DELETE SET NULL,
  permit_number text,
  state text,
  effective_from date,
  effective_to date,
  route_text text,
  restrictions_text text,
  escort_requirements text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Jobs / dispatch routes
CREATE TYPE job_status AS ENUM ('unassigned', 'assigned', 'active', 'completed', 'cancelled');

CREATE TABLE public.jobs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  permit_id uuid REFERENCES public.permits(id) ON DELETE SET NULL,
  permit_candidate_id uuid REFERENCES public.permit_candidates(id) ON DELETE SET NULL,
  origin text,
  destination text,
  route_text text,
  estimated_miles integer,
  estimated_duration integer,
  escort_requirements text,
  assigned_driver_id uuid REFERENCES public.driver_profiles(id) ON DELETE SET NULL,
  status job_status NOT NULL DEFAULT 'unassigned',
  scheduled_start timestamptz,
  projected_completion timestamptz,
  projected_available_at timestamptz,
  projected_available_location jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Job route states (for assignment validation)
CREATE TABLE public.job_route_states (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  job_id uuid NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
  state_code char(2) NOT NULL,
  source text,
  sort_order integer DEFAULT 0
);

-- Devices (optional, for session policy)
CREATE TABLE public.devices (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  driver_id uuid NOT NULL REFERENCES public.driver_profiles(id) ON DELETE CASCADE,
  device_id text,
  platform text,
  last_seen_at timestamptz,
  last_app_version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Dispatch config (business rules)
CREATE TABLE public.dispatch_config (
  key text PRIMARY KEY,
  value jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Default config values
INSERT INTO public.dispatch_config (key, value) VALUES
  ('dispatch_day_cutoff_time', '"16:00"'),
  ('dispatch_next_day_start_time', '"08:00"'),
  ('availability_buffer_minutes', '15');

-- Trigger: create profile when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, email, role)
  VALUES (new.id, new.email, 'driver');
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- RLS policies (enable RLS on all tables)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.driver_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dispatcher_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.driver_last_location ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.driver_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.driver_state_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permit_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_route_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dispatch_config ENABLE ROW LEVEL SECURITY;

-- Profiles: users can read own
CREATE POLICY "Users can read own profile" ON public.profiles
  FOR SELECT USING (auth.uid() = id);

-- Driver profiles: drivers read own; dispatcher/admin read all; driver can insert own; admin can insert any
CREATE POLICY "Drivers read own profile" ON public.driver_profiles
  FOR SELECT USING (
    user_id = auth.uid() OR
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
  );

CREATE POLICY "Driver insert own profile" ON public.driver_profiles
  FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "Admin insert driver profile" ON public.driver_profiles
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role = 'admin')
  );

CREATE POLICY "Driver update own profile" ON public.driver_profiles
  FOR UPDATE USING (user_id = auth.uid());

-- Driver last location: same as driver_profiles
CREATE POLICY "Driver location readable by driver or dispatcher" ON public.driver_last_location
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.driver_profiles dp JOIN public.profiles p ON p.id = dp.user_id WHERE dp.id = driver_id AND (dp.user_id = auth.uid() OR p.role IN ('dispatcher', 'admin')))
  );

-- Location history: drivers insert own; drivers read own; dispatcher/admin read all
CREATE POLICY "Location history insert own" ON public.location_history
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM public.driver_profiles dp WHERE dp.id = driver_id AND dp.user_id = auth.uid())
  );

CREATE POLICY "Location history select" ON public.location_history
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.driver_profiles dp JOIN public.profiles p ON p.id = dp.user_id WHERE dp.id = driver_id AND (dp.user_id = auth.uid() OR p.role IN ('dispatcher', 'admin')))
  );

-- Driver availability: driver manages own; dispatcher/admin read all
CREATE POLICY "Availability driver manage own" ON public.driver_availability
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.driver_profiles dp WHERE dp.id = driver_id AND dp.user_id = auth.uid())
  );

CREATE POLICY "Availability dispatcher read" ON public.driver_availability
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
  );

-- Jobs, permit_candidates, etc.: dispatcher/admin full access for now
CREATE POLICY "Jobs dispatcher admin" ON public.jobs
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
  );

CREATE POLICY "Permit candidates dispatcher admin" ON public.permit_candidates
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
  );

CREATE POLICY "Ingestion documents dispatcher admin" ON public.ingestion_documents
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
  );

-- Drivers can read own assigned job
CREATE POLICY "Jobs driver read own" ON public.jobs
  FOR SELECT USING (
    assigned_driver_id IN (SELECT id FROM public.driver_profiles WHERE user_id = auth.uid())
  );

-- Dispatch config: read by dispatcher/admin
CREATE POLICY "Config dispatcher read" ON public.dispatch_config
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
  );
