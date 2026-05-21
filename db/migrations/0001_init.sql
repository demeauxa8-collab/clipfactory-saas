-- ClipFactory SaaS — initial schema
-- Target: Supabase Postgres (15+)
-- All tables live in the public schema. Auth is handled by Supabase auth.users.

-- =============================================================
-- Extensions
-- =============================================================

create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- =============================================================
-- Helper: updated_at trigger
-- =============================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- =============================================================
-- plan_definitions
-- One row per pricing plan. Seeded below.
-- =============================================================

create table public.plan_definitions (
  code                    text primary key,
  name                    text not null,
  price_eur_cents         integer not null check (price_eur_cents >= 0),
  credits_per_period      integer not null check (credits_per_period > 0),
  max_video_minutes       integer not null check (max_video_minutes > 0),
  max_clips_per_video     integer not null check (max_clips_per_video > 0),
  max_concurrent_jobs     integer not null check (max_concurrent_jobs > 0),
  stripe_price_id         text unique,
  is_active               boolean not null default true,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

create trigger trg_plan_definitions_updated_at
  before update on public.plan_definitions
  for each row execute function public.set_updated_at();

-- Seed V1: single Starter plan.
insert into public.plan_definitions
  (code, name, price_eur_cents, credits_per_period, max_video_minutes, max_clips_per_video, max_concurrent_jobs)
values
  ('starter', 'Starter', 2900, 300, 30, 3, 1);

-- =============================================================
-- profiles
-- 1-to-1 with auth.users. Created via trigger on signup.
-- =============================================================

create table public.profiles (
  user_id              uuid primary key references auth.users(id) on delete cascade,
  email                text not null,
  full_name            text,
  stripe_customer_id   text unique,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

create trigger trg_profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- Auto-create profile on auth.users insert.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (user_id, email)
  values (new.id, new.email)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- =============================================================
-- subscriptions
-- One active row per user. We keep history (no delete) for audit.
-- =============================================================

create type public.subscription_status as enum (
  'trialing',
  'active',
  'past_due',
  'canceled',
  'incomplete',
  'incomplete_expired',
  'unpaid',
  'paused'
);

create table public.subscriptions (
  id                        uuid primary key default uuid_generate_v4(),
  user_id                   uuid not null references public.profiles(user_id) on delete cascade,
  plan_code                 text not null references public.plan_definitions(code),
  stripe_subscription_id    text unique,
  stripe_customer_id        text,
  status                    public.subscription_status not null,
  current_period_start      timestamptz,
  current_period_end        timestamptz,
  cancel_at_period_end      boolean not null default false,
  canceled_at               timestamptz,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

create index idx_subscriptions_user on public.subscriptions(user_id);
create index idx_subscriptions_status on public.subscriptions(status);

create trigger trg_subscriptions_updated_at
  before update on public.subscriptions
  for each row execute function public.set_updated_at();

-- =============================================================
-- credit_ledger
-- Append-only. Balance is recomputed by reducing all rows for a user.
-- Use a partial sum index later if needed.
-- =============================================================

create type public.credit_reason as enum (
  'subscription_grant',
  'subscription_renewal',
  'job_debit',
  'job_refund',
  'manual_adjustment'
);

create table public.credit_ledger (
  id              bigserial primary key,
  user_id         uuid not null references public.profiles(user_id) on delete cascade,
  delta           integer not null,            -- positive grant, negative debit
  reason          public.credit_reason not null,
  job_id          uuid,                        -- nullable; FK added after jobs table
  subscription_id uuid references public.subscriptions(id) on delete set null,
  note            text,
  created_at      timestamptz not null default now()
);

create index idx_credit_ledger_user on public.credit_ledger(user_id, created_at desc);
create index idx_credit_ledger_job on public.credit_ledger(job_id);

-- Balance view: simple sum for now. Switch to materialized view if perf becomes an issue.
create or replace view public.credit_balances as
  select user_id, coalesce(sum(delta), 0)::integer as balance
  from public.credit_ledger
  group by user_id;

-- =============================================================
-- jobs
-- One row per "process this URL" request.
-- =============================================================

create type public.job_status as enum (
  'queued',
  'downloading',
  'transcribing',
  'analyzing',
  'rendering',
  'completed',
  'failed',
  'canceled'
);

create table public.jobs (
  id                       uuid primary key default uuid_generate_v4(),
  user_id                  uuid not null references public.profiles(user_id) on delete cascade,
  source_url               text not null,
  source_kind              text not null default 'youtube',  -- youtube | upload | other
  target_clip_count        integer not null check (target_clip_count between 1 and 10),
  status                   public.job_status not null default 'queued',
  duration_seconds         integer,                          -- detected source duration
  credits_estimated        integer not null,                 -- charged upfront on dequeue
  credits_charged          integer,                          -- final, after run
  error_code               text,
  error_message            text,
  worker_id                text,
  queued_at                timestamptz not null default now(),
  started_at               timestamptz,
  finished_at              timestamptz,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

create index idx_jobs_user_status on public.jobs(user_id, status);
create index idx_jobs_status_queued_at on public.jobs(status, queued_at) where status = 'queued';

create trigger trg_jobs_updated_at
  before update on public.jobs
  for each row execute function public.set_updated_at();

-- Close the credit_ledger -> jobs FK now that jobs exists.
alter table public.credit_ledger
  add constraint fk_credit_ledger_job
  foreign key (job_id) references public.jobs(id) on delete set null;

-- =============================================================
-- clips
-- One row per rendered clip.
-- =============================================================

create table public.clips (
  id                  uuid primary key default uuid_generate_v4(),
  job_id              uuid not null references public.jobs(id) on delete cascade,
  user_id             uuid not null references public.profiles(user_id) on delete cascade,
  idx                 integer not null,                  -- 0-based order within job
  title               text,
  hook_text           text,
  rationale           text,                              -- why this clip was picked
  start_seconds       numeric(10,3) not null,
  end_seconds         numeric(10,3) not null,
  duration_seconds    numeric(10,3) generated always as (end_seconds - start_seconds) stored,
  score_total         integer,                           -- 0-100
  score_breakdown     jsonb,                             -- hook, emotion, visual, fit, editing
  r2_key              text not null,                     -- path inside R2 bucket
  bytes               bigint,
  width               integer not null default 1080,
  height              integer not null default 1920,
  created_at          timestamptz not null default now(),
  unique (job_id, idx)
);

create index idx_clips_user on public.clips(user_id, created_at desc);

-- =============================================================
-- stripe_events
-- Idempotency table for the Stripe webhook handler.
-- =============================================================

create table public.stripe_events (
  event_id      text primary key,
  event_type    text not null,
  payload       jsonb not null,
  received_at   timestamptz not null default now(),
  processed_at  timestamptz,
  error         text
);

create index idx_stripe_events_unprocessed on public.stripe_events(received_at) where processed_at is null;

-- =============================================================
-- RLS — Row Level Security
-- The service role (backend) bypasses RLS. The anon/authenticated
-- keys (used by the Next.js app via Supabase client) are constrained
-- to the rules below.
-- =============================================================

alter table public.profiles            enable row level security;
alter table public.subscriptions       enable row level security;
alter table public.credit_ledger       enable row level security;
alter table public.jobs                enable row level security;
alter table public.clips               enable row level security;
alter table public.plan_definitions    enable row level security;
alter table public.stripe_events       enable row level security;

-- plan_definitions: readable by everyone (incl. anonymous), no write from client.
create policy "plan_definitions_select_public"
  on public.plan_definitions for select
  using (true);

-- profiles
create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = user_id);

create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = user_id);

-- subscriptions: read own only. Writes happen via backend service_role.
create policy "subscriptions_select_own"
  on public.subscriptions for select
  using (auth.uid() = user_id);

-- credit_ledger: read own only.
create policy "credit_ledger_select_own"
  on public.credit_ledger for select
  using (auth.uid() = user_id);

-- jobs: read/insert own; updates restricted (backend handles transitions).
create policy "jobs_select_own"
  on public.jobs for select
  using (auth.uid() = user_id);

create policy "jobs_insert_own"
  on public.jobs for insert
  with check (auth.uid() = user_id and status = 'queued');

-- clips: read own only.
create policy "clips_select_own"
  on public.clips for select
  using (auth.uid() = user_id);

-- stripe_events: no client access at all (only service_role).
-- (RLS enabled, no policies = denied for anon/auth roles.)
