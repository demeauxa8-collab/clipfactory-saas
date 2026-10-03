-- Starter gets multi-video series (up to 3 sources, each within the plan's
-- per-source duration limit). Pro keeps 5. Credits are still debited per
-- source minute, so a series costs exactly the sum of its sources.
update public.plan_definitions
   set max_series_sources = 3
 where code = 'starter';
