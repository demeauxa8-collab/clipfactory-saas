# Compare methods with the same models

This lab is private and isolated. It never submits a production job, uses a production
database, changes a service, or uploads sources or clips to GitHub. Use a separate
OpenRouter lab key in an external credentials file, as described in `model-lab.md`.

## Frozen inputs and identities

- Select two sources in a private TOML using the golden source schema.
- Freeze both media files once at 720p. Both methods use those exact hashes.
- Freeze word and sentence timestamps in `transcript.json`; record its SHA-256 in
  the source's `meta.json`. Existing ASR is a sunk cost, disclosed separately.
- New shared ASR uses OpenRouter Whisper Large V3. Its accounting ledger is passed
  into A with `--prior-ledger`, so preparation remains inside the $8 A ceiling.
- Commit the code, freeze its revision under a `pipeline-vtest-...` tag, and retain
  the same `models.premium.lock.toml` and catalog snapshot for both methods.
- No model promotion or production deployment follows this experiment.

## A: the product method

The real `run_job` remains unchanged. Only a hash-verified experimental transcript
input is substituted by the harness. The database is a disposable local cluster.
The default target remains five; this experiment explicitly requests three.

```sh
PYTHONPATH=apps/worker apps/worker/.venv/bin/python apps/worker/scripts/golden_run.py \
  --config /private/experiment/sources.toml --root /private/experiment/A \
  --target-clips 3 --reuse-transcripts --asr-backend openrouter \
  --models-lock apps/worker/models.premium.lock.toml --budget 8.00 \
  --credentials-file /private/experiment/lab.env \
  --catalog /private/experiment/catalog.json \
  --prior-ledger /private/experiment/preparation-ledger.json
```

`A/sources` must point to the shared frozen sources. The existing product prompts,
selection, scoring, framing, captions and rendering are retained. The separate
golden judge is observational and does not alter product delivery.

## B: the editorial method

`scripts/model_lab/premium_workflow.py` and `deliver_workflow.py` preserve the
private method's phrase-ID selection, editorial audit, anchored V2 rendering,
verbatim verification and native-video delivery gate. They accept external paths
and credentials; no private client identifier or original private path is embedded.

To hold models constant, text/audit use the premium lock's text model, framing
uses its deep vision model, and native verification/judging use its judge model.
All requests use OpenRouter. Reasoning budgets and model output floors come from
that same lock. Thus framing is Gemini here, replacing the original method's
Astra framing model. The selector requests 12k output tokens to match the lock's
output floor within the explicit budget. These adaptations are recorded, not
represented as an unmodified historical run.

```sh
PYTHONPATH=apps/worker apps/worker/.venv/bin/python apps/worker/scripts/model_lab/run.py \
  --config /private/experiment/sources.toml --shared-root /private/experiment/shared \
  --root /private/experiment/B --models-lock apps/worker/models.premium.lock.toml \
  --budget 7.00 --credentials-file /private/experiment/lab.env \
  --catalog /private/experiment/catalog.json
```

The gate can reject candidates; budget exhaustion or fewer than six qualified
clips is an incomplete result, never a fabricated delivery. Existing historical
clips and selection responses are not reused as outputs of this experiment.

## Budget and reporting

HTTP interception reserves a bound before every paid request and includes retries,
discarded answers and uncertain failures. `Budget` retains the historical $3
default ceiling; the golden harness explicitly allows up to $8, B up to $7.
OpenRouter STT uses a four-times observed tariff with a 10% margin as its reservation.
Missing provider usage retains that reservation. This is an accounting assumption,
not a guarantee from the provider; a reported cost above the bound halts the run
and is reported as a bound violation.

Run `scripts/model_lab/report.py /private/experiment` to export media to separate
`A/clips` and `B/clips` directories, plus CSV/JSON/Markdown reports with durations,
ending words and costs. A allocates each source's entire cost among delivered
clips. B identifies candidate-specific requests and allocates shared/rejected work.
Cost allocations are explicitly distinguished from direct per-clip API charges.
Human judgment of the outputs remains necessary before claiming a better method.
