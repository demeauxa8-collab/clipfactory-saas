-- A clip series groups independently processed source videos in one campaign.
-- The worker claims one queued source at a time; clips keep their source job.
-- One source means multi-video series are unavailable on that plan.
alter table public.plan_definitions
  add column max_series_sources integer not null default 1
    check (max_series_sources between 1 and 5);

-- Pro is seeded inactive until its dedicated Stripe price is configured.
insert into public.plan_definitions
  (code, name, price_eur_cents, credits_per_period, max_video_minutes,
   max_clips_per_video, max_concurrent_jobs, max_series_sources, is_active)
values ('pro', 'Pro', 7900, 1000, 60, 3, 1, 5, false);

create table public.clip_series (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references public.profiles(user_id) on delete cascade,
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  created_at timestamptz not null default now()
);

create index idx_clip_series_user_created on public.clip_series(user_id, created_at desc);

alter table public.clip_series enable row level security;
revoke all on table public.clip_series from anon, authenticated;
grant select on table public.clip_series to authenticated;
create policy "clip_series_select_own"
  on public.clip_series for select
  to authenticated
  using ((select auth.uid()) = user_id);

alter table public.jobs
  add column series_id uuid references public.clip_series(id) on delete set null,
  add column series_position integer check (series_position >= 0),
  add constraint jobs_series_position_pair check (
    series_id is null or series_position is not null
  );

create unique index idx_jobs_series_position
  on public.jobs(series_id, series_position) where series_id is not null;

-- Only the API may attach jobs to a series. Authenticated clients may still
-- insert ordinary jobs under the original policy.
drop policy "jobs_insert_own" on public.jobs;
create policy "jobs_insert_own"
  on public.jobs for insert
  with check (
    (select auth.uid()) = user_id and status = 'queued'
    and series_id is null and series_position is null
  );
