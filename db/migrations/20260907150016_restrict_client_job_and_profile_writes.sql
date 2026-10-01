-- Keep admissions, plan checks and job transitions in the authenticated API.
-- The backend connects with a privileged database role. Client reads retain RLS.
revoke insert, update, delete, truncate, references, trigger
  on public.jobs from public, anon, authenticated;
drop policy if exists "jobs_insert_own" on public.jobs;

-- Profiles: clients may update their display name only.
revoke insert, update, delete, truncate, references, trigger
  on public.profiles from public, anon, authenticated;
revoke update (user_id, email, full_name, stripe_customer_id, created_at, updated_at, is_admin)
  on public.profiles from public, anon, authenticated;
grant update (full_name) on public.profiles to authenticated;

-- Run the balance view with the caller's ledger RLS, not the view owner's rights.
alter view public.credit_balances set (security_invoker = true);

-- Intermediate files become visible only after accounting and completion commit.
drop policy if exists "clips_select_own" on public.clips;
create policy "clips_select_own" on public.clips for select
  using (auth.uid() = user_id and exists (
    select 1 from public.jobs j where j.id = clips.job_id and j.status = 'completed'
  ));
