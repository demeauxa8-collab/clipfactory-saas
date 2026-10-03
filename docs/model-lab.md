# Laboratoire de modèles premium (OpenRouter)

Objectif : tester des modèles premium (GPT-6 Astra Pro, Gemini 3.1 Pro) **sans toucher la production**.
La production garde `apps/worker/models.lock.toml` et sa clé OpenRouter plafonnée.

## Profil premium

`apps/worker/models.premium.lock.toml` (même schéma que le lock de prod, tous les stages présents) :

| Stage | Modèle | Prix $/Mtok (in / out) |
|---|---|---|
| text | `openai/gpt-6-astra-pro` | 10 / 50 |
| vision_deep | `google/gemini-3.1-pro-preview` | 2 / 12 |
| clip_judge | `google/gemini-3.1-pro-preview` | 2 / 12 |
| vision_cheap | `qwen/qwen3-vl-30b-a3b-instruct` | 0,15 / 0,60 |
| transcription_openrouter | `openai/whisper-large-v3` | 0,00185 $/min (observé) |

Les modèles de raisonnement ont un plancher de sortie (`min_output_tokens`) et un budget de
raisonnement plafonné (`reasoning_max_tokens`) : sans cela le JSON est tronqué. Les prix sont
ceux du catalogue `GET https://openrouter.ai/api/v1/models` (au-delà de 200k / 272k tokens de
prompt, le tarif augmente : nos prompts restent en dessous).

## Règles

1. Clé **séparée** : créer dans le dashboard OpenRouter une clé « lab » avec son propre plafond de
   dépense (par ex. 10 $). Ne jamais la mettre dans le `.env` de production.
2. `MODELS_LOCK_PATH` et la clé lab ne s'exportent que dans le shell de l'expérience.
3. Aucune modification du `.env`, du service launchd ni du déploiement.

## Lancer une expérience

Harnais golden (clés lues uniquement dans le fichier `--credentials-file`, mets-y la clé lab
dans `OPENROUTER_API_KEY` ; `OPENAI_API_KEY` doit être non vide mais n'est pas utilisée) :

```sh
PYTHONPATH=apps/worker apps/worker/.venv/bin/python apps/worker/scripts/golden_run.py \
  --config "$HOME/clipfactory-golden/sources.toml" \
  --root "$HOME/clipfactory-golden" --budget 3.00 \
  --models-lock apps/worker/models.premium.lock.toml \
  --credentials-file /absolute/private/lab-worker.env \
  --catalog /absolute/private/openrouter-model-catalog.json
```

Exécution manuelle (hors harnais) :

```sh
cd apps/worker
( export OPENROUTER_API_KEY=sk-or-LAB-KEY \
         MODELS_LOCK_PATH=models.premium.lock.toml \
         ASR_BACKEND=openrouter
  .venv/bin/python -m <ton script> )
```

Un override par stage (`PRIMARY_TEXT_MODEL=openai/gpt-6-astra`, etc.) reste prioritaire sur le lock.
