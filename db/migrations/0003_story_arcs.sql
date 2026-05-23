-- ClipFactory SaaS — story-first pipeline
-- Adds:
--   - jobs.video_map jsonb (compressed visual summary of the source)
--   - jobs.eval_secondary jsonb (parallel run results for A/B benchmark)
--   - jobs.video_map_cost_cents + jobs.deep_vision_cost_cents (cost split)
--   - clips.segments jsonb (ordered list of (start, end, role) — replaces single window)
--   - clips.rendered_duration_seconds (final rendered length, can differ from sum of segments after crossfade)

-- =============================================================
-- jobs — story-first additions
-- =============================================================

alter table public.jobs
  add column video_map jsonb,
  add column eval_secondary jsonb,
  add column video_map_cost_cents integer,
  add column deep_vision_cost_cents integer,
  add column primary_provider text,
  add column fallback_used boolean not null default false;

create index idx_jobs_fallback_used on public.jobs(fallback_used) where fallback_used = true;

-- =============================================================
-- clips — multi-segment montage support
-- =============================================================

-- segments shape:
--   [
--     { "role": "setup"   | "transition" | "payoff" | "single",
--       "start": <seconds in source>,
--       "end":   <seconds in source>,
--       "transcript_excerpt": "..." }
--   ]
-- For the single-window legacy case, segments has length 1 with role="single".

alter table public.clips
  add column segments jsonb,
  add column rendered_duration_seconds numeric(10, 3);

-- Backfill existing rows (if any) — none in production yet, but kept for safety.
update public.clips
   set segments = jsonb_build_array(
         jsonb_build_object(
           'role', 'single',
           'start', start_seconds,
           'end',   end_seconds,
           'transcript_excerpt', coalesce(transcript_excerpt, '')
         )
       ),
       rendered_duration_seconds = end_seconds - start_seconds
 where segments is null;

-- =============================================================
-- Optional view: clips with their parent job campaign for analytics
-- =============================================================

create or replace view public.clips_with_context as
  select c.id          as clip_id,
         c.job_id,
         c.user_id,
         j.campaign_id,
         c.idx,
         c.title,
         c.score_total,
         c.score_breakdown,
         c.segments,
         c.rendered_duration_seconds,
         c.r2_key,
         c.created_at
    from public.clips c
    join public.jobs j on j.id = c.job_id;
