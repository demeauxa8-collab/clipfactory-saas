-- =============================================================
-- 0006 — Free trial
--
-- Until now a visitor had to subscribe before running anything, so
-- nobody could see a single clip before paying 29 EUR. This migration
-- moves the wall to the other side of the value: every new account
-- gets a trial plan with enough credits for one short video.
--
-- The trial is a real plan + a 'trialing' subscription, so every quota
-- rule already in the codebase (max duration, clip count, concurrency,
-- credit debits) applies to it without a single special case.
-- =============================================================

alter type public.credit_reason add value if not exists 'trial_grant';

-- -------------------------------------------------------------
-- The trial plan
--
-- 15 credits = one 15-minute video. At the measured ~0.7 cent per
-- source minute, a full trial costs us about 11 cents.
-- -------------------------------------------------------------

insert into public.plan_definitions
  (code, name, price_eur_cents, credits_per_period, max_video_minutes,
   max_clips_per_video, max_concurrent_jobs, is_active)
values
  ('trial', 'Free trial', 0, 15, 15, 3, 1, true)
on conflict (code) do update
  set name                = excluded.name,
      credits_per_period  = excluded.credits_per_period,
      max_video_minutes   = excluded.max_video_minutes,
      max_clips_per_video = excluded.max_clips_per_video,
      max_concurrent_jobs = excluded.max_concurrent_jobs,
      is_active           = excluded.is_active;

-- -------------------------------------------------------------
-- Grant the trial on signup
--
-- current_period_end stays null on purpose: every "which plan is
-- active" query orders by current_period_end desc nulls last, so a
-- paid subscription always outranks the trial once it exists.
--
-- The trial block is wrapped in its own exception handler — a failure
-- to grant credits must never make the signup itself fail.
-- -------------------------------------------------------------

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_credits integer;
  v_sub_id  uuid;
begin
  insert into public.profiles (user_id, email)
  values (new.id, new.email)
  on conflict (user_id) do nothing;

  begin
    select credits_per_period into v_credits
      from public.plan_definitions
     where code = 'trial' and is_active;

    -- No trial plan configured, or this account already had one.
    if v_credits is null
       or exists (select 1 from public.subscriptions where user_id = new.id)
    then
      return new;
    end if;

    insert into public.subscriptions (user_id, plan_code, status, current_period_start)
    values (new.id, 'trial', 'trialing', now())
    returning id into v_sub_id;

    insert into public.credit_ledger (user_id, delta, reason, subscription_id, note)
    values (new.id, v_credits, 'trial_grant', v_sub_id, 'Signup free trial');
  exception
    when others then
      raise warning 'trial grant failed for %: %', new.id, sqlerrm;
  end;

  return new;
end;
$$;
