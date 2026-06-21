-- ClipFactory SaaS — first-party analytics events
--
-- One table captures product + behavioural events from every surface (web, API,
-- worker) so we own the data end-to-end. PostHog is an optional mirror wired in
-- the app layer; this table is the source of truth and works with zero external
-- accounts.
--
-- Privacy: we store user_id (FK to auth.users) but never raw PII here — no email,
-- no name. Property payloads are caller-controlled and should stay PII-free.

create table public.analytics_events (
  id           uuid primary key default uuid_generate_v4(),
  user_id      uuid references auth.users(id) on delete set null,
  anon_id      text,                  -- client id for pre-auth / anonymous sessions
  session_id   text,
  event_name   text not null,
  source       text not null default 'web' check (source in ('web', 'api', 'worker')),
  properties   jsonb not null default '{}'::jsonb,
  path         text,
  referrer     text,
  created_at   timestamptz not null default now()
);

create index idx_analytics_events_user    on public.analytics_events(user_id, created_at desc);
create index idx_analytics_events_name    on public.analytics_events(event_name, created_at desc);
create index idx_analytics_events_created on public.analytics_events(created_at desc);
create index idx_analytics_events_props   on public.analytics_events using gin (properties);

alter table public.analytics_events enable row level security;

-- Authenticated browsers may insert events tagged with their own id (or anonymous).
create policy "analytics_events_insert_own"
  on public.analytics_events for insert to authenticated
  with check (auth.uid() = user_id or user_id is null);

-- A user can read back their own events. Server roles (API/worker) use the
-- service connection and bypass RLS, so they can insert worker/api events freely.
create policy "analytics_events_select_own"
  on public.analytics_events for select to authenticated
  using (auth.uid() = user_id);

-- Admin/operator funnel rollup. No grant to anon/authenticated — read it from the
-- API admin endpoints over the service-role connection only.
create or replace view public.analytics_daily as
  select
    date_trunc('day', created_at)::date as day,
    event_name,
    source,
    count(*)::bigint                as events,
    count(distinct user_id)::bigint as users
  from public.analytics_events
  group by 1, 2, 3;
