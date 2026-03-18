-- Phase 3: RLS for job_route_states and driver_state_permissions (dispatcher/admin read)
-- Plan Section 10.13; Phase 3 steps 3.6–3.8

-- job_route_states: dispatcher/admin can read and manage (for assignment validation)
CREATE POLICY "Job route states dispatcher admin" ON public.job_route_states
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
  );

-- driver_state_permissions: dispatcher/admin read (for assign modal eligibility); drivers read own
CREATE POLICY "Driver state permissions dispatcher admin" ON public.driver_state_permissions
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role IN ('dispatcher', 'admin'))
    OR EXISTS (SELECT 1 FROM public.driver_profiles dp WHERE dp.id = driver_state_permissions.driver_id AND dp.user_id = auth.uid())
  );
