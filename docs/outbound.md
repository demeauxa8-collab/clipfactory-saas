# Outbound — how the first customers get found

Date: 2026-08-14
Status: machine built (`apps/worker/scripts/outbound.py`), campaign not yet run

## The number

The target is 1000 EUR MRR. At 29 EUR that is **35 paying customers**, not a
traffic milestone. That distinction decides the whole strategy:

| Stage | Customers | What actually works |
| --- | ---: | --- |
| 0 → 10 | first 10 | Outbound with finished clips given away. Slow, manual, unreasonably effective. |
| 10 → 35 | next 25 | Clipper communities + short-form content, once the first ten have told us what to say. |

Mass distribution is the wrong tool for the first ten. It takes weeks to warm
up and teaches nothing about the product. Outbound teaches everything, and the
people who answer become the testimonials that make the content work later.

## Why give the work away

A clip costs **~0.7 cent per source minute** (measured, see
`docs/unit-economics.md`). Three clips from a 40-minute episode cost about 28
cents. Thirty prospects cost under 10 EUR.

Nobody answers a pitch. People answer finished work about themselves. This is
the one move a competitor with a marketing budget cannot copy cheaply, because
they would have to pay an editor per prospect.

## Who to target

**Segment A — professional clippers.** People paid per 1000 views on Whop
Content Rewards, Vyro, and Discord servers (Clip Money, Clipster, /clipping).
Observed rates run 0.50 to 5 USD per 1000 views; a clipper posting 10-20 times
a day earns 400-1500 USD/month, the top ones several thousand.

Why they convert: their income is directly proportional to how many clips they
ship. Speed is not comfort, it is revenue. Against 1000 USD/month, 29 EUR is
not a decision. They also post 15 times a day, which makes them a distribution
channel by accident.

The honest risk: this crowd is price-sensitive, shares accounts, and is already
targeted by OpusClip. The angle is not price, it is **clips shipped per euro**
plus multi-segment montage, which the competition does not do.

**Segment B — mid-sized podcasts and interview shows.** Slower, lower volume,
but they pay without arguing and they stay. Best served by giving away clips
from their own last episode.

## Sourcing — the qualifier that saves the most time

**Do not target the big shows.** GDIY, Pauline Laigneau and their peers already
employ editors. They will not answer, and a reply would not be a sale anyway.

The ideal prospect is a channel that **publishes long episodes and has no
Shorts tab worth the name**. That single signal says everything: they produce
enough material to be serious, and they are leaving the short-form audience on
the table. It is visible in five seconds.

Sourcing loop, roughly two minutes per prospect:

1. YouTube search on a niche + "podcast", filtered to **this week** and
   **over 20 minutes** — this surfaces channels that are actively publishing.
2. Open the channel, click the **Shorts** tab. Empty or nearly empty → prospect.
   Full of shorts → skip, someone is already doing the job.
3. The **About** tab usually exposes a business email. No email is not a
   blocker; a reply to a recent video or a DM works, put that in `contact`.
4. Copy the URL of their most recent long video into `source_url`.

Twenty qualified prospects is under an hour of work. That is the whole cost of
entry.

**Clippers are sourced differently.** They have no business inbox — they live
in Discord servers (Clip Money, Clipster, /clipping) and on Whop campaigns.
Cold-DMing them gets you banned. The way in is to be present in the server,
answer questions about editing speed, and offer accounts to people who ask.
Set `"lang": "en"` on these prospects; those communities are English-speaking.

## Running a campaign

Prerequisites: Redis running, the worker running, and an operator account whose
plan allows long videos (podcast episodes exceed the 30-minute Starter cap).

```sql
-- One-off: an internal plan for the operator account.
-- is_active = false keeps it out of anything customer-facing.
insert into plan_definitions
  (code, name, price_eur_cents, credits_per_period, max_video_minutes,
   max_clips_per_video, max_concurrent_jobs, is_active)
values ('internal', 'Internal', 0, 100000, 240, 10, 2, false)
on conflict (code) do nothing;

-- Far-future period end so this plan outranks any other subscription
-- (resolution orders by current_period_end desc nulls last).
insert into subscriptions
  (user_id, plan_code, status, current_period_start, current_period_end)
select user_id, 'internal', 'active', now(), now() + interval '10 years'
  from profiles where email = 'OPERATOR@EMAIL';

insert into credit_ledger (user_id, delta, reason, note)
select user_id, 100000, 'manual_adjustment', 'internal outbound account'
  from profiles where email = 'OPERATOR@EMAIL';
```

Then:

```bash
redis-server &
cd apps/worker
python -m app.main &                     # the worker

cp scripts/prospects.example.json prospects.json   # fill it in
python scripts/outbound.py run prospects.json --operator you@example.com
# …wait for the worker to chew through them…
python scripts/outbound.py collect prospects.json --operator you@example.com
```

`collect` writes one folder per prospect under `./outbound/<slug>/`, containing
the rendered clips and a `message.txt` draft. **Edit the first line of every
message before sending.** A batch of identical emails reads as a batch of
identical emails, and that is the one thing this approach cannot survive.

## What to measure

Track these from the first batch, or the second batch repeats the mistakes:

- prospects contacted → replies → tried the product → paid
- which segment answers (A or B)
- which line in the message gets quoted back

The conversion rate from this list is what tells us whether to scale outbound
or switch to content. Guessing it in advance is how people waste a month.
