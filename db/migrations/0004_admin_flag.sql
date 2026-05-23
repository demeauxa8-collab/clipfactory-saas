-- ClipFactory SaaS — admin role flag + public stats view
--
-- The admin flag gates the /admin/* dashboard. It is set manually (no UI to grant
-- admin powers). Public stats view aggregates non-PII counters for the landing.

alter table public.profiles
  add column is_admin boolean not null default false;

create index idx_profiles_is_admin on public.profiles(is_admin) where is_admin = true;

-- Public stats view — exposed without RLS to the anon role for the landing page
-- counters. Strict counts only, no per-user data, no email.

create or replace view public.public_stats as
  select
    (select count(*)::bigint from public.clips) as clips_generated,
    (select coalesce(round(sum(duration_seconds) / 3600.0)::bigint, 0)
       from public.jobs where status = 'completed') as hours_processed,
    (select count(distinct user_id)::bigint
       from public.jobs
       where queued_at >= now() - interval '60 days') as creators_active;

grant select on public.public_stats to anon, authenticated;
