-- ClipFactory SaaS — V1 scope expansion
-- Adds:
--   - campaigns table
--   - campaign_feedback table
--   - cost/margin columns on jobs
--   - vision columns on clips
--   - extends job_status enum implicitly (no new value needed — handled in app code)

-- =============================================================
-- campaigns
-- =============================================================

create table public.campaigns (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid not null references public.profiles(user_id) on delete cascade,
  name            text not null check (char_length(name) between 1 and 80),
  audience        text not null default '' check (char_length(audience) <= 400),
  niche           text not null default '' check (char_length(niche) <= 120),
  tone            text not null default '' check (char_length(tone) <= 120),
  goal            text not null default '' check (char_length(goal) <= 400),
  avoid_topics    text[] not null default array[]::text[],
  example_hooks   text[] not null default array[]::text[],
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index idx_campaigns_user on public.campaigns(user_id, created_at desc);

create trigger trg_campaigns_updated_at
  before update on public.campaigns
  for each row execute function public.set_updated_at();

-- =============================================================
-- jobs — add campaign + cost/margin columns
-- =============================================================

alter table public.jobs
  add column campaign_id uuid references public.campaigns(id) on delete set null;

create index idx_jobs_campaign on public.jobs(campaign_id);

alter table public.jobs
  add column current_step text,
  add column source_r2_key text,
  add column transcription_cost_cents integer,
  add column analysis_tokens integer,
  add column vision_frames_count integer,
  add column render_seconds integer,
  add column storage_bytes bigint,
  add column total_cost_estimate_cents integer,
  add column failed_step text,
  add column retry_count integer not null default 0;

-- =============================================================
-- clips — add vision + excerpt context
-- =============================================================

alter table public.clips
  add column visual_summary text,
  add column transcript_excerpt text;

-- =============================================================
-- campaign_feedback (user feedback on a generated clip)
-- =============================================================

create type public.feedback_kind as enum ('good', 'bad');

create table public.campaign_feedback (
  id           uuid primary key default uuid_generate_v4(),
  clip_id      uuid not null references public.clips(id) on delete cascade,
  user_id      uuid not null references public.profiles(user_id) on delete cascade,
  campaign_id  uuid references public.campaigns(id) on delete set null,
  kind         public.feedback_kind not null,
  note         text check (note is null or char_length(note) <= 500),
  created_at   timestamptz not null default now(),
  unique (clip_id, user_id)
);

create index idx_feedback_user_created on public.campaign_feedback(user_id, created_at desc);
create index idx_feedback_campaign on public.campaign_feedback(campaign_id);

-- =============================================================
-- RLS — new tables
-- =============================================================

alter table public.campaigns enable row level security;
alter table public.campaign_feedback enable row level security;

create policy "campaigns_select_own"
  on public.campaigns for select
  using (auth.uid() = user_id);

create policy "campaigns_insert_own"
  on public.campaigns for insert
  with check (auth.uid() = user_id);

create policy "campaigns_update_own"
  on public.campaigns for update
  using (auth.uid() = user_id);

create policy "campaigns_delete_own"
  on public.campaigns for delete
  using (auth.uid() = user_id);

create policy "campaign_feedback_select_own"
  on public.campaign_feedback for select
  using (auth.uid() = user_id);

create policy "campaign_feedback_insert_own"
  on public.campaign_feedback for insert
  with check (auth.uid() = user_id);

-- jobs.campaign_id is enforced at the API level: every new job must belong to
-- a campaign owned by the same user. Adding the FK does not enforce ownership
-- by itself; the API service layer checks the join.
