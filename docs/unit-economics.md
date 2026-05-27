# Unit economics — credits, VPS, APIs, margins

Last updated: 2026-05-24.

This doc is the financial source of truth for V1 pricing until real production
usage replaces the estimates.

## Executive decision

ClipFactory is profitable at the V1 target of 7 Starter customers, even with the
larger CPX32 VPS.

The old margin docs used gross revenue (`7 x 29 EUR = 203 EUR`) and an outdated
CPX21 VPS. The realistic view is stricter:

- Pricing page says VAT is included for EU customers.
- Stripe charges on the VAT-included amount.
- The MVP VPS should be CPX32, not CPX21, because FFmpeg + worker temp files
  need more RAM headroom.
- API costs must be measured per completed job, not guessed once.

Bottom line:

| Scenario at 7 Starter customers | Monthly margin after VAT + Stripe |
| --- | ---: |
| Mixed usage, official providers | ~120 EUR |
| Conservative heavy-story usage | ~75-90 EUR |
| Gross old-style view, before VAT | ~155-160 EUR |

If margin goes negative, the fix is not grey-market API keys. The fix is to
lower frame counts, route models better, add hard spend caps, or move heavy
vision to a legal cheaper provider with invoices and data terms.

## Current V1 credit model

Database source: `db/migrations/0001_init.sql`.

| Plan | Price | Credits | Max video | Clips | Concurrent jobs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Starter | 29 EUR / month | 300 | 30 min | 3 | 1 |

Rule:

```text
1 credit = 1 source video minute
```

Credits are charged after the worker probes real duration:

- estimated credits are debited when the job starts,
- final credits are settled at completion,
- failed jobs are refunded by `job_refund`.

This is good for margin because it keeps billing tied to the cost driver:
source minutes.

## Net revenue per plan

Assumptions:

- France / EU B2C pricing, VAT included.
- VAT = 20%.
- Stripe France standard EEA card = 1.5% + 0.25 EUR.
- USD API costs are treated as EUR 1:1 for a conservative buffer.

### Starter

```text
Gross customer price:          29.00 EUR
VAT included:                 - 4.83 EUR
Stripe fee:                   - 0.69 EUR
Net usable revenue:            23.48 EUR
Credits:                         300
Net revenue per credit:         0.078 EUR
```

For 7 customers:

```text
Gross MRR:                    203.00 EUR
Net after VAT + Stripe:       164.36 EUR
Credits sold:                  2,100
Net revenue per credit:        0.078 EUR
```

### Podcast low-tier option

This is the safer low-ticket offer if you want a cheaper entry plan.

```text
Gross customer price:          15.00 EUR
VAT included:                 - 2.50 EUR
Stripe fee:                   - 0.48 EUR
Net usable revenue:            12.03 EUR
Credits:                         100
Net revenue per credit:         0.120 EUR
```

Verdict: 15 EUR / 100 credits is better margin per credit than Starter. It is
fine for podcast clips if the product copy is clear that it is for simple
podcast footage, not heavy story-first video analysis.

## Fixed monthly costs

Use this for the first public MVP:

| Item | Cash cost / month | Notes |
| --- | ---: | --- |
| Hetzner CPX32 | ~16.79 EUR TTC | 4 vCPU, 8 GB RAM, 160 GB, no backups |
| Hetzner CPX32 + backups | ~20.15 EUR TTC | Recommended once first users are active |
| Domain | ~1 EUR | annual cost averaged monthly |
| Supabase | 0 EUR | free tier at MVP scale |
| Cloudflare Pages | 0 EUR | free tier at MVP scale |
| Cloudflare R2 buffer | ~2 EUR | storage + operations, should be near-zero early |
| Monitoring MVP | 0-5 EUR | Uptime Robot / Sentry free at start |

Fixed cost target with backups:

```text
VPS + R2 + domain = ~23 EUR / month
With small monitoring buffer = ~28 EUR / month
```

Do not start lower than CPX32 unless cash is extremely tight. CPX22/CPX21 can
boot the stack, but FFmpeg renders plus downloaded source videos can make 4 GB
RAM uncomfortable.

## Variable API costs

Current pipeline:

- Transcription: OpenAI `gpt-4o-mini-transcribe`.
- Primary text: OpenRouter DeepSeek.
- Cheap global vision: OpenRouter Qwen VL.
- Deep targeted vision: OpenRouter Gemini Flash on top arcs.
- Fallback: Anthropic Haiku 4.5 only on primary errors.

### Current official/reference prices

OpenAI:

| Model | Reference price |
| --- | ---: |
| `gpt-4o-mini-transcribe` | $1.25 / 1M audio input tokens, $5 / 1M output tokens |
| Worker estimate used today | $0.003 / source minute |

OpenRouter snapshot from `https://openrouter.ai/api/v1/models` on 2026-05-24:

| Role | Current candidate model | Input / 1M | Output / 1M | Notes |
| --- | --- | ---: | ---: | --- |
| Text primary | `deepseek/deepseek-v3.2` | $0.252 | $0.378 | Current code uses `deepseek/deepseek-chat-v3.2`; verify ID before prod |
| Deep vision | `google/gemini-2.5-flash` | $0.300 | $2.500 | Vision/image input also priced by image tokens |
| Cheap vision | `qwen/qwen3-vl-8b-instruct` | $0.080 | $0.500 | cheapest Qwen VL candidate found |
| Cheap vision safer | `qwen/qwen3-vl-32b-instruct` | $0.104 | $0.416 | better likely quality / still cheap |
| Large Qwen VL | `qwen/qwen2.5-vl-72b-instruct` | $0.250 | $0.750 | stronger but more expensive |

Anthropic fallback:

| Model | Input / 1M | Output / 1M |
| --- | ---: | ---: |
| `claude-haiku-4-5` | $1.00 | $5.00 |

Important: OpenRouter prices and model IDs move often. Re-check with:

```bash
curl -s https://openrouter.ai/api/v1/models \
  | jq -r '.data[] | select(.id|test("deepseek|gemini-2.5-flash|qwen.*vl|haiku"; "i")) | [.id, .pricing.prompt, .pricing.completion, .pricing.image] | @tsv'
```

### Pipeline cost guardrails

The V1 pipeline is bounded:

| Guardrail | Current behavior |
| --- | --- |
| Max video length | 30 min per Starter job |
| Max clips | 3 per job |
| Concurrent jobs | 1 per user |
| Story threshold | videos >= 5 min use story-first |
| Video-map frames | max 80 frames under 10 min, 150 frames at 10-30 min |
| Deep vision | top 5 arcs only |
| Deep vision frames | up to 5 frames per segment, max 3 segments per arc |

Worst normal 30-minute job:

```text
video_map frames:      up to 150
deep vision frames:    up to ~75
total vision frames:   up to ~225
```

That is why the API margin is still workable: the whole video is understood,
but deep vision is only spent on candidate moments.

## Margin model at 7 Starter customers

Credits sold:

```text
7 customers x 300 credits = 2,100 source minutes
```

Net revenue after VAT + Stripe:

```text
7 x 23.48 EUR = 164.36 EUR
```

### Base case

| Cost | Monthly estimate |
| --- | ---: |
| CPX32 + backups | 20.15 EUR |
| R2 | 2.00 EUR |
| Domain | 1.00 EUR |
| OpenAI transcription: 2,100 min x 0.003 | 6.30 EUR |
| OpenRouter text + vision mix | 12.00 EUR |
| Anthropic fallback, ~5% | 1.00 EUR |
| **Total** | **42.45 EUR** |
| **Net margin after VAT + Stripe** | **121.91 EUR** |

### Conservative heavy-story case

Assume all customers use the full 300 credits and mostly submit videos over
5 minutes, forcing story-first vision.

| Cost | Monthly estimate |
| --- | ---: |
| CPX32 + backups | 20.15 EUR |
| R2 + storage buffer | 5.00 EUR |
| Domain + monitoring | 6.00 EUR |
| OpenAI transcription | 6.30 EUR |
| OpenRouter heavy vision/text | 35.00-45.00 EUR |
| Anthropic fallback, elevated | 5.00-8.00 EUR |
| **Total** | **77-90 EUR** |
| **Net margin after VAT + Stripe** | **74-87 EUR** |

### Break-even

With base costs around 42-45 EUR/month:

```text
45 EUR / 23.48 EUR net per Starter = 1.9 customers
```

So the business breaks even around 2 Starter customers in a base case, and
around 4 Starter customers in the conservative heavy-story case.

## Max safe API cost per credit

At 7 Starter customers:

```text
Net after VAT + Stripe:       164.36 EUR
Fixed costs before APIs:     ~23.15 EUR
Credits sold:                  2,100
Budget left for APIs:         141.21 EUR
Max API cost per credit:        0.067 EUR
```

A useful rule:

```text
If average API cost stays below 0.03 EUR per source minute, Starter is healthy.
If it rises above 0.05 EUR per source minute, reduce vision or raise price.
If it hits 0.067 EUR per source minute, 7 Starter users are near break-even.
```

## What to measure from day one

The admin finance page already reads the right job columns:

- `transcription_cost_cents`
- `video_map_cost_cents`
- `deep_vision_cost_cents`
- `total_cost_estimate_cents`
- `vision_frames_count`
- `analysis_tokens`
- `fallback_used`

Before public launch, add one manual weekly check:

```sql
select
  count(*) as jobs,
  sum(credits_charged) as credits,
  round(sum(total_cost_estimate_cents) / 100.0, 2) as api_cost_eur,
  round((sum(total_cost_estimate_cents) / nullif(sum(credits_charged), 0)) / 100.0, 4) as api_cost_per_credit
from jobs
where status = 'completed'
  and finished_at > now() - interval '7 days';
```

Decision thresholds:

| Metric | Good | Action needed |
| --- | ---: | ---: |
| API cost / credit | < 0.03 EUR | none |
| API cost / credit | 0.03-0.05 EUR | lower frame counts or model route |
| API cost / credit | > 0.05 EUR | raise price / reduce credits / cap story jobs |
| Fallback rate | < 10% | none |
| Fallback rate | 10-20% | inspect provider failures |
| Fallback rate | > 20% | switch primary model/provider |

## Proxy / China API key policy

Do not run public SaaS production on grey-market shared keys or random proxy
resellers, even if they are cheaper.

Risks:

- provider account bans and sudden outages,
- no invoice / no predictable billing,
- no data processing agreement,
- customer videos, faces, voices, transcripts, and campaign data leave the
  controlled provider path,
- unknown logging/training retention,
- latency and model-routing instability,
- impossible customer trust story if asked where data goes.

Allowed cheaper route:

- legal provider account,
- invoice in your name,
- explicit model IDs,
- documented data retention,
- acceptable DPA / privacy terms,
- API spend caps,
- staging benchmark before production.

If you test a Chinese proxy anyway:

- staging only,
- no real customer videos,
- no user emails or campaign names,
- put it behind a feature flag,
- cap monthly spend,
- never make it the default fallback.

Better options before any grey-market proxy:

1. Use Qwen VL cheaper models for global visual summaries.
2. Reduce `video_map` cap for long videos from 150 to 100 frames if margin is tight.
3. Run deep vision on top 3 arcs instead of top 5.
4. Use Gemini only for uncertain/high-score candidates.
5. Add a monthly story-first quota: e.g. only 120 of 300 Starter credits can be
   spent on videos >= 5 minutes.
6. Create a higher-priced Video plan once real users prove demand.

## Recommended V1 offers

Keep V1 simple publicly:

| Offer | Price | Credits | Margin view |
| --- | ---: | ---: | --- |
| Podcast | 15 EUR / month | 100 | excellent per-credit margin, good entry plan |
| Starter Video | 29 EUR / month | 300 | profitable if API cost/credit < 0.05 EUR |
| Founder | 29 EUR / month locked | 500 max | okay only for first 20 users, never unlimited |

Avoid lifetime unlimited offers. They destroy margin once users discover the
story-first pipeline.

## Immediate corrections to keep before launch

1. Keep CPX32 as the default VPS in deploy docs.
2. Verify OpenRouter model IDs before prod:
   - replace `deepseek/deepseek-chat-v3.2` if invalid,
   - replace `qwen/qwen3-vl-flash` if invalid.
3. Add provider spend caps in dashboards:
   - OpenAI monthly cap,
   - OpenRouter monthly cap,
   - Anthropic monthly cap.
4. Add R2 lifecycle rules:
   - delete source videos after 14 days,
   - delete rendered clips after 60 days unless user exports/downloads.
5. Review real job costs after the first 20 completed jobs.

## Sources checked

- Hetzner price adjustment, CPX32 Germany/Finland: <https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/>
- Hetzner Regular Performance specs / backups: <https://www.hetzner.com/cloud/regular-performance>
- Stripe France pricing: <https://stripe.com/en-fr/pricing>
- Cloudflare R2 pricing: <https://developers.cloudflare.com/r2/pricing/>
- OpenAI GPT-4o mini Transcribe model pricing: <https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe>
- Anthropic Haiku 4.5 pricing: <https://www.anthropic.com/claude/haiku>
- OpenRouter live model pricing endpoint: <https://openrouter.ai/api/v1/models>
