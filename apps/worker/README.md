# ClipFactory worker

Le worker consomme les jobs Redis, analyse une vidéo, compile les passages retenus en EDL et livre des MP4 contrôlés avec leurs manifestes. Le contrat d'exécution est dans `docs/pipeline.md`, à la racine du dépôt. Les fondations expérimentales présentes sur disque ne sont pas toutes activées dans le runner.

## Installation reproductible

Depuis la racine du dépôt, avec Python 3.11 et `uv==0.11.11` :

```bash
uv venv apps/worker/.venv --python 3.11
uv pip sync --python apps/worker/.venv/bin/python apps/worker/requirements.lock
cp apps/worker/.env.example apps/worker/.env
```

Compléter les variables du fichier local. FFmpeg, ffprobe et yt-dlp doivent être disponibles sur le PATH. Le lock inclut les outils de développement et préserve les versions de bibliothèques utilisées pour la validation ; une mise à jour de dépendances doit être vérifiée séparément.

## Exécution

```bash
cd apps/worker
.venv/bin/python -m app.main
```

Connexions attendues : PostgreSQL (`DATABASE_URL`), Redis (`REDIS_URL`), stockage R2 (`R2_*`, ou `STORAGE_BACKEND=local`), OpenAI pour la transcription et OpenRouter pour le texte et la vision. Le fallback Anthropic dépend de la configuration. Le modèle de transcription par défaut du code est `whisper-1` ; les autres modèles et budgets sont définis dans `app/settings.py`.

Un processus exécute actuellement un seul job à la fois. La revendication atomique protège contre les livraisons dupliquées. L'arrêt contrôlé annule le job et attend son nettoyage ; une reprise après arrêt brutal nécessite encore une procédure d'exploitation.

## Tests

Depuis la racine, sans identifiants de production :

```bash
export DATABASE_URL=postgresql://local:local@127.0.0.1:5432/local
export STORAGE_BACKEND=local
export R2_ACCOUNT_ID=local R2_ACCESS_KEY_ID=local R2_SECRET_ACCESS_KEY=local
export R2_ENDPOINT_URL=https://example.com OPENAI_API_KEY=local
export PYTHONPATH=apps/worker
apps/worker/.venv/bin/ruff check apps/worker/app apps/worker/tests apps/worker/scripts/benchmark_clipping.py tests/integration
apps/worker/.venv/bin/python -m pytest apps/worker/tests -q
```

Pour les intégrations, préparer un PostgreSQL local jetable avec une base `clipfactory_test` et un rôle pouvant créer des bases et des rôles. La fixture crée et détruit une base distincte par test ; elle refuse une adresse distante ou un autre nom de base. Elle simule les rôles et la fonction d'identité Supabase, puis applique les migrations du dépôt.

```bash
export CLIPFACTORY_TEST_DATABASE_URL=postgresql://clipfactory_test:test@127.0.0.1:5432/clipfactory_test
apps/worker/.venv/bin/python -m pytest tests/integration/worker -q
uv venv apps/api/.venv --python 3.11
uv pip sync --python apps/api/.venv/bin/python apps/api/requirements.lock
PYTHONPATH=apps/api apps/api/.venv/bin/python -m pytest tests/integration/api -q
# Tests PostgreSQL de séries côté API : migrer la base partagée clipfactory_test une fois
apps/api/.venv/bin/python tests/integration/apply_schema.py
PYTHONPATH=apps/api apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

Le workflow `.github/workflows/pipeline-quality.yml` utilise PostgreSQL 17 avec ses extensions. Le run macOS a utilisé PostgreSQL 16.2 avec `CLIPFACTORY_TEST_BUILTIN_UUID=1`, uniquement pour remplacer la génération UUID de la migration initiale dans un runtime sans extensions contrib. La nouvelle migration de permissions est exécutée sans modification. Ce mode ne représente pas un Supabase hébergé complet.

## Replay vidéo hors ligne

`apps/worker/scripts/benchmark_clipping.py --help` décrit les entrées : source, fixture, transcript et propositions capturées. Comparer une base et une modification avec les mêmes entrées, sans régénérer les propositions. Le script force le même cadrage `fit_blur`, consigne les empreintes des entrées et du code, et conserve MP4, ASS, manifestes et rapport JSON. Il ne remplace pas un test des modèles en direct ou une évaluation humaine du montage.

## Coûts et limites

La durée source mesurée est réservée en crédits avant l'analyse payante. Les échecs remboursent le débit net réel. Les colonnes de coûts fournisseur, de tokens, de temps de rendu et de stockage restent des mesures ou estimations d'exploitation ; elles ne sont pas un rapprochement exhaustif avec les factures des fournisseurs.
