# Multi-source clip series rollout

## Product contract

- A Pro subscriber can submit 2–5 distinct YouTube videos to one campaign as a series.
- Each source is processed as an independent job in the submitted order. A failed source does not stop the next source. Each exported clip names its source video.
- Starter continues to allow single-source jobs. Pro is 79 EUR/month for 1,000 monthly credits; Starter is 29 EUR/month for 300.
- Source duration is measured by the worker and billed in credits per video. A series needs at least one available credit per source at submission; a later source may fail if an earlier one exhausts the balance.

## Deployment order

1. Apply `db/migrations/0006_clip_series.sql` to Supabase. **Done** on 2026-09-25 in project `jsjaizcnjvghoduvyyea` (`20260925153547 clip_series_pro_plan`); owner-only SELECT and API-only insert grants were checked.
2. Deploy the updated FastAPI service and worker from the same Git revision. The worker polls PostgreSQL for ordered series jobs and continues to use Redis for standalone jobs. Keep the worker alive during processing; only an unstarted series claim is recovered automatically after two minutes.
3. Create a recurring Stripe Pro price for 79 EUR/month, set `plan_definitions.stripe_price_id` for `code = 'pro'`, configure the billing portal to offer the allowed plan changes, then activate Pro with `update public.plan_definitions set is_active = true where code = 'pro' and stripe_price_id is not null`. Never reuse the Starter price ID.
4. Deploy the web app. Confirm the API URL, Stripe secrets, webhook signing secret, Supabase service role, Redis and worker credentials are configured on their respective hosts.
5. Run an authenticated smoke test with a Pro subscription: submit two short videos, observe ordered processing, per-source clips and downloads, credit debits, a failed-source refund, and a repeat webhook delivery. Confirm Starter receives `series_not_in_plan` from the API.

## Current state on 2026-09-25

The database migration is live and the local code/build/tests are ready for review. Pro remains inactive because no dedicated Stripe price is configured. The public web site answers, but `api.clipfactory.app` does not resolve, and no production API or worker deployment was verified. Do not advertise Pro as purchasable until the API, worker and Stripe smoke test pass.
