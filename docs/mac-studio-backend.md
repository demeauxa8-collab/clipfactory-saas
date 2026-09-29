# ClipFactory — Backend sur le Mac Studio M1 Max

> **Destinataire : Codex, qui tourne sur le Mac Studio M1 Max.** Ce document est la mission complète. Lis-le en entier avant la première commande. Il remplace, pour la phase actuelle, la section 5 de `docs/deploy.md` (mode « tout sur le Mac, sans VPS » déjà prévu en bas de cette section).
>
> **Objectif** : l'API, Redis et le worker tournent 24 h/24 sur le Mac Studio. La transcription se fait **en local** (Whisper sur MLX, GPU Apple). L'API est joignable en HTTPS public. Le site Vercel s'y connecte. Un vrai job va d'un bout à l'autre.
>
> **Définition de « fini »** : `ops/macos/doctor.sh` est entièrement vert, l'URL publique répond `{"status":"ok"}` sur `/health`, et le rapport de passation (§13) est rendu. Claude lancera ensuite un test de connexion depuis un autre Mac.

---

## 0. Règles non négociables

1. **Aucun secret dans git.** Les fichiers `.env` ne sont jamais ajoutés, affichés dans un log, collés dans un message ou un commit. Le repo `demeauxa8-collab/clipfactory-saas` est **public**.
2. **Jamais de push sur `main`**, jamais de force-push, jamais de merge. Tu travailles sur une branche, tu ouvres une PR en brouillon.
3. **Aucune modification de la base Supabase** : pas de migration, pas d'écriture manuelle. Le schéma de prod est déjà à jour.
4. **Aucun changement Stripe**, aucun changement de DNS de `clipfactory.app`. Ce domaine n'est pas confirmé comme appartenant au projet : ne pas s'en servir.
5. **Ne pas toucher aux modèles** choisis dans `models.lock` / `settings.py` : un banc de test est en cours ailleurs, il décidera. Seule exception : l'ajout du backend de transcription locale (§6).
6. **Redis n'est jamais exposé** hors de `127.0.0.1`. Seul le port de l'API passe par le tunnel.
7. **Ne pas toucher au projet Maison / Hermes** ni à ses services launchd s'il y en a sur cette machine.
8. Code, commits, noms de fichiers : **en anglais**. Messages à Augustin : **en français, simples**.
9. **Stop et demande à Augustin** si : une commande exige `sudo` (il la tape lui-même), un compte ou une clé manque, un test échoue et le correctif sort du périmètre, ou tu hésites à supprimer quoi que ce soit.

---

## 1. Architecture cible

```
Navigateur ──► Vercel (Next.js, clipfactory-saas.vercel.app)
                   │  NEXT_PUBLIC_API_URL = https://<studio>.<tailnet>.ts.net
                   ▼
        Tailscale Funnel (HTTPS public, port 443)
                   │
┌──────────────────▼───────────── Mac Studio M1 Max ─────────────────────┐
│  API FastAPI (uvicorn 127.0.0.1:8000)  ──LPUSH job──►  Redis 127.0.0.1  │
│                                                          │ BLPOP         │
│  Worker (python -m app.main) ◄───────────────────────────┘               │
│    yt-dlp + deno ─► ffmpeg (libass) ─► ASR local MLX (Whisper) ─►        │
│    LLM/vision via OpenRouter ─► rendu EDL ─► upload R2                   │
└──────────────────────────────────────────────────────────────────────────┘
        │ Postgres (pooler)          │ S3 API               │ HTTPS
        ▼                            ▼                      ▼
   Supabase (EU)              Cloudflare R2           OpenRouter / OpenAI (secours ASR)
```

Pourquoi ce choix : zéro VPS à payer, l'IP résidentielle réduit les blocages YouTube, le GPU du M1 Max fait la transcription gratuitement. Limites acceptées pour la phase actuelle : un seul job à la fois, dépendance au courant et à la box. Le passage à un VPS (control plane) reste décrit dans `docs/deploy.md` §5.A.

---

## 2. Préparer la machine (Augustin, avec `sudo`)

Codex : affiche ces commandes à Augustin et attends qu'il confirme. Ne les exécute pas toi-même.

```bash
# Ne jamais dormir, redémarrer seul après une coupure de courant
sudo pmset -a sleep 0 disksleep 0 displaysleep 30 autorestart 1 womp 1
pmset -g | egrep 'sleep|autorestart'
```

- Réglages système › Utilisateurs : **ouverture de session automatique** sur le compte qui fera tourner ClipFactory. Les LaunchAgents ne démarrent qu'après ouverture de session. Si FileVault est actif, l'ouverture automatique est impossible : après une coupure de courant il faudra taper le mot de passe une fois. Le noter dans le rapport.
- Mises à jour macOS automatiques : **désactiver l'installation automatique** (sinon redémarrages surprises).
- Espace disque : garder **≥ 40 Go libres**. Vérifier `df -h ~`.

---

## 3. Outils système

```bash
# Homebrew doit exister (/opt/homebrew). Sinon : Augustin l'installe.
brew update
brew install python@3.12 git gh deno redis yt-dlp tailscale jq
```

**FFmpeg avec libass (obligatoire pour les sous-titres).** La formule Homebrew par défaut a déjà été vue sans libass sur une machine d'Augustin. Vérifie d'abord :

```bash
brew install ffmpeg
ffmpeg -hide_banner -filters | egrep ' (ass|subtitles) ' || echo "LIBASS MANQUANT"
```

Si « LIBASS MANQUANT » :

```bash
brew uninstall ffmpeg
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-libass --with-freetype --with-fontconfig
ffmpeg -hide_banner -filters | egrep ' (ass|subtitles) '   # doit afficher ass et subtitles
```

Redis local, lié à localhost uniquement :

```bash
grep -E '^(bind|protected-mode)' /opt/homebrew/etc/redis.conf   # attendu : bind 127.0.0.1 ::1 / protected-mode yes
brew services start redis
redis-cli ping    # PONG
```

---

## 4. Le code

Un checkout **dédié à la prod**, séparé de tout checkout de dev :

```bash
git clone https://github.com/demeauxa8-collab/clipfactory-saas.git ~/clipfactory-prod
cd ~/clipfactory-prod
git fetch origin
# Base : la branche de consolidation si elle existe sur GitHub, sinon main.
git ls-remote --heads origin consolidate/pipeline-v1
git switch -c feat/mac-studio-backend origin/consolidate/pipeline-v1   # ou origin/main
```

Lis avant d'écrire du code : `docs/pipeline.md`, `docs/v1-scope.md`, `docs/api-contract.md`, `docs/deploy.md`, et la carte `docs/pipeline-map-2026-09-29.md` (branche `origin/docs/pipeline-map` : `git show origin/docs/pipeline-map:docs/pipeline-map-2026-09-29.md`).

Environnements Python (un par app) :

```bash
python3.12 -m venv apps/api/.venv    && apps/api/.venv/bin/pip install -U pip && apps/api/.venv/bin/pip install -e 'apps/api[dev]'
python3.12 -m venv apps/worker/.venv && apps/worker/.venv/bin/pip install -U pip && apps/worker/.venv/bin/pip install -e 'apps/worker[dev]'
apps/api/.venv/bin/pytest apps/api -q
apps/worker/.venv/bin/pytest apps/worker -q
```

Les deux suites doivent passer **avant** toute modification. Note le nombre de tests et de skips.

---

## 5. Secrets (`.env`)

Augustin transfère lui-même (AirDrop, clé USB — **jamais** par git, chat ou mail) ses deux fichiers depuis son MacBook :

- `~/clipfactory-saas/apps/api/.env` → `~/clipfactory-prod/apps/api/.env`
- `~/clipfactory-saas/apps/worker/.env` → `~/clipfactory-prod/apps/worker/.env`

Puis :

```bash
chmod 600 ~/clipfactory-prod/apps/*/.env
git -C ~/clipfactory-prod status --porcelain | grep -F '.env' && echo "ALERTE : .env suivi par git"   # ne doit rien afficher
```

Compare les **noms** de variables (jamais les valeurs) avec les `.env.example` et signale les manquantes :

```bash
for a in api worker; do comm -13 <(grep -oE '^[A-Z0-9_]+' apps/$a/.env | sort) <(grep -oE '^[A-Z0-9_]+' apps/$a/.env.example | sort) | sed "s/^/$a manque: /"; done
```

Valeurs à **ajuster pour le Mac Studio** (édite les fichiers sans les afficher) :

| Fichier | Variable | Valeur |
|---|---|---|
| api + worker | `REDIS_URL` | `redis://127.0.0.1:6379/0` |
| api + worker | `ENV` | `prod` |
| api | `CORS_ALLOW_ORIGINS` | `https://clipfactory-saas.vercel.app` (liste explicite, l'API refuse de démarrer en prod sinon) |
| api | `API_BASE_URL` | l'URL Funnel du §8 |
| api | `WEB_BASE_URL` | `https://clipfactory-saas.vercel.app` |
| worker | `WORKER_TMP_DIR` | `/Users/<compte>/clipfactory-work` (créer le dossier) |
| worker | `FFMPEG_BIN` / `FFPROBE_BIN` / `YT_DLP_BIN` | chemins absolus `/opt/homebrew/bin/...` (launchd n'a pas ton PATH) |
| worker | `WORKER_CONCURRENCY` | `1` |
| worker | `YT_DLP_COOKIES_FROM_BROWSER` | vide au départ ; `chrome` seulement si YouTube renvoie des 403 ET qu'Augustin est connecté à YouTube dans Chrome sur ce Mac |
| worker | `ASR_BACKEND` (nouveau, §6) | `mlx_whisper` |

Si `R2_*` est vide ou invalide, **ne bascule pas** en stockage local en silence : stop et préviens Augustin (les clips doivent être téléchargeables depuis le site).

---

## 6. Le seul vrai développement : la transcription locale (MLX)

### Ce qui existe
`apps/worker/app/pipeline/transcribe.py` → `async def transcribe(path) -> Transcript` : extrait l'audio en mp3 mono 16 kHz, appelle OpenAI `whisper-1` avec `response_format="verbose_json"` et `timestamp_granularities=["word", "segment"]`, construit `Transcript` (mots + phrases), fusionne les élisions françaises (`merge_french_elisions`). La branche de consolidation (PR #8) ajoute une correction des mots de durée nulle. **Tout le reste du pipeline suppose des timestamps au mot fiables : c'est l'horloge des coupes.**

### Ce qu'il faut construire
Un backend de transcription enfichable, sans changer le contrat de `transcribe()` :

- Respecte le mécanisme `apps/worker/models.lock.toml` (introduit par la PR #8) : le modèle ASR local se déclare dans le lock, comme les autres étapes.
- `settings.py` : `asr_backend: Literal["openai", "mlx_whisper"] = "openai"` (défaut inchangé pour tout autre environnement), `mlx_whisper_model: str = "mlx-community/whisper-large-v3-turbo"`, `asr_fallback_to_openai: bool = True`. Le `.env` du Studio met `ASR_BACKEND=mlx_whisper`.
- Nouveau module `apps/worker/app/pipeline/asr_mlx.py` :
  - dépendance **optionnelle** `mlx-whisper` (extra `[mlx]` dans `apps/worker/pyproject.toml`, installé seulement sur le Mac : `pip install -e 'apps/worker[dev,mlx]'`). Import paresseux : la CI Linux ne doit jamais l'importer.
  - appel : `mlx_whisper.transcribe(audio_path, path_or_hf_repo=settings.mlx_whisper_model, word_timestamps=True, condition_on_previous_text=False)`, langue auto-détectée.
  - l'appel est bloquant et utilise le GPU : l'exécuter via `asyncio.to_thread`, protégé par un verrou global (un seul décodage à la fois).
  - mapping : chaque `segment` → `TranscriptSentence(text, start, end)` ; chaque `segment["words"][i]` → `TranscriptWord(word.strip(), start, end, probability si dispo)`. Mêmes post-traitements que la voie OpenAI (élisions, durée nulle), **dans une fonction partagée**, pas copiés.
- `transcribe()` choisit le backend selon `settings.asr_backend`. En cas d'exception MLX et si `asr_fallback_to_openai`, log `transcribe.mlx_failed` puis bascule sur `whisper-1`. Le coût enregistré vaut **0** pour MLX.
- Préchauffage : télécharger le modèle une fois (`python -c "import mlx_whisper; mlx_whisper.transcribe('<court.wav>', path_or_hf_repo='mlx-community/whisper-large-v3-turbo')"`) pour que le premier job ne paie pas le téléchargement (~1,6 Go).

### Tests
- Unitaires (tournent partout, sans MLX) : mapping d'une sortie MLX factice → `Transcript` ; sélection du backend ; bascule vers OpenAI sur exception (provider mocké) ; aucun import de `mlx_whisper` quand `asr_backend="openai"`.
- Test local marqué `@pytest.mark.mlx` (exclu de la CI) : transcrit un extrait de 20 s et vérifie mots non vides, timestamps croissants, aucune durée négative.

### Critère d'acceptation (mesure, pas opinion)
Sur les **3 premières minutes** d'une vraie source FR (la vidéo de test que te donnera Augustin, ou n'importe quel épisode de podcast français), compare MLX à `whisper-1` et mets le tableau dans la PR :

| Mesure | Seuil pour activer MLX en prod |
|---|---|
| Part de mots à durée nulle (avant correctif) | ≤ celle de whisper-1 |
| Écart médian des débuts de mots vs whisper-1 | < 150 ms |
| Mots manquants / en trop (alignement difflib) | < 3 % |
| Vitesse | ≥ 10× le temps réel sur le M1 Max |

Si un seuil n'est pas tenu : laisse `ASR_BACKEND=openai` dans le `.env` du Studio, garde le code, et écris pourquoi dans la PR. **Ne force pas.**

---

## 7. Services permanents (launchd)

Mets les **modèles** de fichiers (sans secrets) dans le repo, sous `ops/macos/` :

- `ops/macos/com.clipfactory.api.plist` → `apps/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`, `WorkingDirectory` = `apps/api`.
- `ops/macos/com.clipfactory.worker.plist` → `apps/worker/.venv/bin/python -m app.main`, `WorkingDirectory` = `apps/worker`.
- Dans les deux : `RunAtLoad` et `KeepAlive` à `true`, `ThrottleInterval` 10, `ProcessType` `Interactive` pour le worker (GPU), `EnvironmentVariables.PATH` = `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin`, logs dans `~/Library/Logs/ClipFactory/{api,worker}.{out,err}.log`.
- Les `.env` sont lus par l'application elle-même (pydantic settings), pas recopiés dans les plists.
- `ops/macos/install.sh` : remplace `__HOME__` / `__REPO__` dans les modèles, copie dans `~/Library/LaunchAgents/`, `launchctl bootstrap gui/$(id -u) ...`, puis `launchctl kickstart -k`. Idempotent (bootout avant bootstrap).
- `ops/macos/update.sh` : `git pull --ff-only` sur la branche déployée, réinstalle les deux apps, relance les deux services, lance `doctor.sh`.
- Mise à jour hebdomadaire de yt-dlp (YouTube change souvent) : `brew upgrade yt-dlp` dans `update.sh`, plus une ligne dans le rapport pour qu'Augustin sache le relancer.
- Nettoyage : le worker supprime son dossier de travail en fin de job ; ajoute dans `doctor.sh` une alerte si `WORKER_TMP_DIR` dépasse 20 Go.

Vérifie : `launchctl print gui/$(id -u)/com.clipfactory.worker | egrep 'state|pid'` → `running`, et que les services reviennent seuls après `kill` du process.

---

## 8. Exposer l'API (Tailscale Funnel)

Tailscale donne une URL HTTPS publique stable, gratuite, sans domaine ni port ouvert sur la box. Seule l'API est exposée.

1. Augustin ouvre l'app Tailscale (ou `sudo tailscale up`) et se connecte à son compte. Dans la console Tailscale, il **active Funnel** pour cette machine (Access controls → autoriser `funnel` ; la CLI affiche le lien exact si ce n'est pas fait).
2. Puis :
   ```bash
   tailscale funnel --bg 8000
   tailscale funnel status          # affiche https://<studio>.<tailnet>.ts.net
   curl -s https://<studio>.<tailnet>.ts.net/health   # {"status":"ok"}
   ```
3. Reporte l'URL dans `API_BASE_URL` (api `.env`), relance l'API.
4. **Plus tard (hors mission)** : quand Augustin aura un domaine à lui dans Cloudflare, un Cloudflare Tunnel nommé (`api.<domaine>`) remplacera Funnel sans rien changer d'autre.

Ne jamais exposer Redis, ne jamais `tailscale funnel` un autre port.

---

## 9. Brancher le site

Le site est sur Vercel (`clipfactory-saas.vercel.app`). Il lit `NEXT_PUBLIC_API_URL`.

- Si la CLI Vercel est installée et connectée au bon compte (`vercel whoami`) : mets `NEXT_PUBLIC_API_URL` = l'URL Funnel pour l'environnement **Production**, puis **ne redéploie pas toi-même** : dis à Augustin que c'est prêt, il déclenche le redeploy.
- Sinon : donne à Augustin la valeur exacte à coller dans Vercel › Settings › Environment Variables › Production, puis Redeploy.
- Stripe (webhook `…/stripe/webhook`) : **hors mission**. Note simplement dans le rapport que l'URL du webhook devra pointer vers l'URL Funnel quand Stripe sera activé.

---

## 10. `ops/macos/doctor.sh` — le contrôle qui dit « c'est bon »

Script **lecture seule** (aucun job créé, aucune écriture en base), sortie une ligne par check, `OK` / `KO` + raison courte, code de sortie ≠ 0 si un KO. Il ne doit **jamais** afficher de secret.

| Check | Comment |
|---|---|
| Outils | versions de python, ffmpeg (avec `ass` et `subtitles`), ffprobe, yt-dlp, deno |
| Redis | `redis-cli -u $REDIS_URL ping` = PONG, et bind localhost uniquement |
| API locale | `curl 127.0.0.1:8000/health` |
| API publique | `curl <API_BASE_URL>/health` en HTTPS |
| CORS | requête `OPTIONS` avec `Origin: https://clipfactory-saas.vercel.app` → en-tête `access-control-allow-origin` correct |
| Base | `select 1` via `DATABASE_URL` depuis le venv du worker (pooler : `statement_cache_size=0`) |
| R2 | put / get / delete d'un objet de 1 octet `doctor/<timestamp>` |
| OpenRouter | `GET https://openrouter.ai/api/v1/key` (gratuit) → clé valide |
| OpenAI | `GET https://api.openai.com/v1/models/whisper-1` (gratuit) → 200 |
| ASR local | si `ASR_BACKEND=mlx_whisper` : transcrit 5 s de silence + bip, sans erreur, temps affiché |
| YouTube | `yt-dlp --simulate --remote-components ejs:github <une vidéo publique courte>` → OK |
| Services | api et worker `running` dans launchd |
| Disque | espace libre, taille de `WORKER_TMP_DIR` |
| Veille | `pmset -g` : `sleep 0` |

---

## 11. Validation de bout en bout

1. `doctor.sh` : tout `OK`.
2. Suites de tests api + worker : vertes (même nombre qu'au §4, plus les nouveaux).
3. **Test de connexion par Claude** (depuis un autre Mac) : Augustin lui donne l'URL Funnel. Claude vérifie `/health`, TLS, CORS depuis l'origine Vercel, latence.
4. **Vrai job** : Augustin, connecté sur le site comme un vrai client, lance une vidéo YouTube de 5 à 10 min dans une campagne. Toi, tu suis `~/Library/Logs/ClipFactory/worker.err.log` et tu relèves : durée par étape, backend ASR utilisé, coût, clips produits, téléchargement OK depuis le site. N'insère rien en base toi-même pour « aider » le test.

---

## 12. Exploitation (à mettre dans `ops/macos/README.md`)

- Relancer : `launchctl kickstart -k gui/$(id -u)/com.clipfactory.worker` (idem `api`).
- Logs : `tail -f ~/Library/Logs/ClipFactory/worker.err.log`.
- Mettre à jour : `ops/macos/update.sh`.
- Arrêter proprement (maintenance) : `launchctl bootout gui/$(id -u)/com.clipfactory.worker` — un job en cours est repris ou échoue proprement (vérifier ce que fait le code et l'écrire).
- Après une coupure de courant : le Mac redémarre seul ; si FileVault, taper le mot de passe ; puis `doctor.sh`.

---

## 13. Rapport de passation (à rendre à Augustin, en français)

- URL publique de l'API.
- Sortie complète de `doctor.sh`.
- Branche et lien de la PR brouillon (`feat/mac-studio-backend`), liste des commits.
- Tableau de mesure MLX vs whisper-1 (§6) et décision : `ASR_BACKEND` actif.
- Nombre de tests avant / après.
- Ce qu'Augustin doit faire lui-même (Vercel, Funnel, sudo…), avec les valeurs exactes.
- Ce qui n'a **pas** été fait et pourquoi.
- Risques connus (FileVault, coupure box, yt-dlp à mettre à jour, un job à la fois).

---

## Annexe — pourquoi pas…

- **VPS tout de suite** : 0 client payant aujourd'hui ; le VPS vient au premier client (voir `docs/deploy.md` §5.A). Rien dans ce document ne l'empêche.
- **Ouvrir un port sur la box** : surface d'attaque et IP dynamique. Funnel évite les deux.
- **Parakeet / autre ASR local** : le backend est enfichable ; un banc de modèles est en cours et pourra ajouter `parakeet_mlx` plus tard sans toucher au reste.
- **Utiliser l'abonnement ChatGPT / Codex comme moteur LLM du SaaS** : interdit (conditions d'utilisation, et bannissement au-delà de quelques utilisateurs). Le SaaS utilise OpenRouter / OpenAI avec clés API.
