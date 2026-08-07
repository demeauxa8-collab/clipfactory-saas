# Paysage modèles — mesuré, pas supposé

Dernière mise à jour : 2026-08-07.

> Ce doc existe parce que le catalogue bouge vite et que nos choix de modèles
> avaient été faits une fois, par défaut, puis jamais remis en cause. **Tout ce
> qui est chiffré ici vient d'appels réels sur notre propre vidéo de test**
> (`usage.cost` renvoyé par le fournisseur), pas d'estimations ni de benchmarks
> marketing. Les artefacts sont dans `~/clipfactory-data/bench/` (hors repo :
> vidéo source, fixture, sorties brutes).

---

## 0. Règle d'or

> **Aucune seconde émise par un LLM ne part directement dans ffmpeg.**
> Le transcript mot à mot est notre horloge de référence : elle est gratuite,
> exacte, et déjà calculée. On demande au modèle de **citer** la phrase
> d'ouverture et de fermeture, puis on recale les bornes sur les timestamps des
> mots (`boundaries.anchor_arcs_to_transcript`).

Cette règle vient d'une mesure : sur 7 arcs sur 8, les mots cités par le modèle
commençaient **0,7 à 8,1 s après** le `start` qu'il avait lui-même déclaré. Voir
le journal handoff du 2026-08-07.

Corollaire pour le choix des modèles : **l'incapacité d'un modèle à lire l'heure
n'est éliminatoire que là où on lui demande de placer une coupe.** Sur la
video-map et la deep vision, les timecodes viennent des frames qu'on extrait
nous-mêmes — un modèle « aveugle au temps » y est parfaitement utilisable.

---

## 1. Vidéo et audio natifs (OpenRouter)

**Mécanique confirmée** (doc + 40 appels réels) :

- vidéo : `{"type":"video_url","video_url":{"url":"data:video/mp4;base64,…"}}`
  — accepte aussi une **URL publique, y compris YouTube** (testé sur notre vraie
  source, sans aucun téléchargement) ;
- audio : `{"type":"input_audio","input_audio":{"data":<b64>,"format":"mp3"}}`
  — base64 obligatoire, pas d'URL.

**Loi de facturation mesurée** (non documentée par le fournisseur) :

```
Gemini = 91 tokens / seconde de source   (66 image à 1 fps + 25 audio)
```

Vérifiée sur 30 s, 300 s et 595 s, et **indépendante de la résolution et du
fps** : un fichier 480p à 5 fps et le même en 30 fps natif coûtent exactement
pareil. Conséquence pratique : **inutile d'envoyer de la HD, inutile de
sous-échantillonner** — on paie la durée, pas le poids.

### Le piège : la plupart des modèles ne savent pas lire l'heure

Localisation de 7 phrases repères dans 595 s (vérité terrain = timestamps
whisper), erreur moyenne :

| modèle | modalité | erreur moyenne | coût /10 min |
| --- | --- | ---: | ---: |
| **google/gemini-3.6-flash** | vidéo | **0,9 s** | 0,090 $ |
| google/gemini-3.6-flash | audio seul | 24,8 s | 0,031 $ |
| google/gemini-3.5-flash-lite | vidéo | 65,2 s | 0,017 $ |
| google/gemini-3-flash-preview | vidéo | 68,1 s | 0,035 $ |
| google/gemini-3.1-flash-lite | vidéo | 68,4 s | 0,015 $ |

Les trois modèles bon marché renvoient **les mêmes valeurs fausses** (124, 142,
212, 400, 434) : c'est un plafond de famille, pas du bruit — inutile d'espérer
le corriger par du prompt. Certains proposent même des segments à 795-854 s dans
une vidéo qui en fait 595.

**L'audio seul ne suffit pas pour couper** : le même modèle passe de 0,9 s à
24,8 s d'erreur quand on lui retire l'image. C'est la piste image qui lui sert
d'horloge. L'audio natif reste excellent et bon marché pour ce qu'on ne mesure
pas du tout aujourd'hui (débit, énergie, souffle, silences) — comme *feature* de
scoring, jamais comme source de timecode.

### Surdité : à tester avant tout usage audio

Certains modèles annoncés « vidéo » ne perçoivent **que l'image** et lisent le
texte incrusté sans entendre la bande son. Testé : `qwen/qwen3.7-flash` et
`minimax/minimax-m3` répondent explicitement ne pas percevoir le son.
**Test de surdité obligatoire** avant de retenir un candidat pour le clip-judge :
lui demander de transcrire verbatim ce qui est *dit*.

---

## 2. Le clip-judge — la brique manquante la mieux notée

Un juge qui **regarde et écoute** le clip monté avant de le livrer. C'est le
seul étage qui vérifie le produit fini ; aujourd'hui rien ne le fait.

Jeu de test : 6 clips étiquetés au mot près (`bench/proto-video/judge6/`).

| modèle | modalité | publiabilité | bords | coût/clip |
| --- | --- | ---: | ---: | ---: |
| **google/gemini-3.6-flash** | vidéo | **6/6** | **11/12** | 0,0115 $ |
| google/gemini-3.6-flash | audio | 5/6 | 9/12 | 0,0082 $ |
| google/gemini-3.1-flash-lite | vidéo | 3/6 | 8/12 | 0,0009 $ |
| google/gemini-3.1-flash-lite | audio | 3/6 | 8/12 | 0,0005 $ |

Le palier bon marché ne détecte rien (il laisse passer les clips tronqués) :
c'est de l'argent jeté, pas une économie.

**Preuve qu'il sert à quelque chose** : soumis à notre vrai montage
(setup 0→13,4 s + payoff 564,4→576,5 s), gemini-3.6-flash a répondu *non
publiable* avec pour motif « la dernière phrase est coupée de façon trop abrupte ».
Vérification dans le transcript : le clip s'arrête sur « réussi », la phrase
continuait « aussi ce challenge ». **Exact au mot près.** Il a aussi correctement
identifié le raccord à 13 s et expliqué qu'il se comprend.

---

## 3. Ce qu'on paie aujourd'hui, et les scénarios

| poste | aujourd'hui |
| --- | ---: |
| video_map (80 frames, 4 batches, **sans le son**) | 0,028 $ |
| deep vision (~25 frames sur 5 arcs) | 0,010 $ |
| **total compréhension / job de 10 min** | **0,038 $** |

| scénario | coût/job | écart |
| --- | ---: | ---: |
| Statu quo | 0,038 $ | — |
| **Économe** : map en vidéo native cheap (0,015 $, son inclus) + clip-judge 6 arcs | 0,087 $ | +0,049 $ |
| **Recommandé** : map gemini-3.6-flash (0,100 $) + clip-judge + scoring audio | 0,172 $ | +0,134 $ |

Repère : la vidéo native sur un modèle bon marché coûte **0,015 $ les 10 min avec
le son**, soit **moins que nos 80 frames muettes à 0,028 $**.

> **Non tranché** : le palier `:batch` de Gemini est à moitié tarif et notre
> traitement est asynchrone par nature — l'archi complète tomberait vers 0,09 $.
> Latence et sémantique d'appel non vérifiées : à valider avant d'en dépendre.

À l'échelle : 1 000 jobs/mois × 0,172 $ = 172 $ de compute. C'est le poste le
plus lourd de la pipeline — à trancher **avant** industrialisation, pas après.

---

## 4. Transcription

**La piste OpenAI est un cul-de-sac assumé.** `gpt-4o-transcribe`,
`gpt-4o-mini-transcribe`, et les deux modèles sortis fin juillet 2026
(`gpt-transcribe`, `gpt-live-transcribe`) **ne rendent aucun timestamp mot à
mot** — le cookbook officiel de migration recommande explicitement de *garder*
whisper-1 quand les timestamps sont indispensables. Ils le sont pour nous
(captions karaoké + frontières de coupe). Sujet clos.

| candidat | timestamps mot | $/min | verdict |
| --- | --- | ---: | --- |
| **whisper-1** (actuel) | oui | 0,0060 | référence ; pas de ponctuation dans les mots, pas de confiance |
| **Deepgram Nova-3** | oui, 311/311 valides | **0,0043** | **seul candidat qui passe les 4 contraintes** |
| Mistral Voxtral | annoncés natifs | 0,0030 | texte le plus propre, mais OpenRouter refuse `verbose_json` → 0 timestamp par ce canal |
| whisper-large-v3 (Groq) | 5 % cassés | 0,0015 | **disqualifié** : avale 16 mots d'affilée |

Le cas Groq mérite d'être retenu comme avertissement : le moins cher du lot
**perd du contenu silencieusement** (une phrase entière absente, confirmée par
recoupement avec deux autres moteurs) et casse les timestamps précisément sur
les chiffres et les montants en euros — exactement ce qui compte dans nos
vidéos. Tout candidat « moins cher » doit être stress-testé sur du bruit et de
la musique, pas sur 60 s propres.

**Bénéfice caché d'une migration** : tous les candidats testés renvoient la
ponctuation collée à chaque mot → notre reconstruction manuelle des élisions
françaises (`merge_french_elisions`) deviendrait **supprimable**, pas juste
adaptable.

**Réserve sur Deepgram** : via le wrapper OpenRouter, la confiance par mot est
masquée et les nombres sortent en toutes lettres (« vingt quatre ans » au lieu de
« 24 heures »). Les deux sont probablement corrigeables via l'API Deepgram
native (`smart_format`, `numerals`) — à valider avec une vraie clé avant bascule.

---

## 5. Hygiène : les identifiants de modèles meurent

`qwen/qwen3-vl-flash` et `deepseek/deepseek-chat-v3.2` — les défauts historiques
de `settings.py` — **ont été retirés d'OpenRouter** et renvoyaient un 400. Le job
basculait alors silencieusement sur le fallback. Corrigé le 2026-08-07.

> **À faire** : un contrôle au démarrage du worker qui appelle `/api/v1/models`
> et loggue une erreur si un modèle configuré a disparu. Le catalogue bouge trop
> vite pour qu'on découvre ça par hasard.

---

## 6. Décisions

| étage | choix | statut |
| --- | --- | --- |
| Transcription | whisper-1 | conservé ; Deepgram Nova-3 candidat sérieux, à tester en natif |
| Video map / contexte global | frames + LLM vision | conservé — **les frames donnent des timecodes exacts gratuitement** ; la vidéo native est moins chère mais les modèles abordables ne savent pas dater |
| Composition des arcs | modèle texte via `PRIMARY_TEXT_MODEL` | benchmark de 9 candidats préparé, pas encore lancé |
| Deep vision par segment | frames + LLM vision | conservé |
| **Clip-judge final** | **gemini-3.6-flash, vidéo native** | **non implémenté — meilleur retour sur investissement identifié** |
| Scoring débit/énergie | audio natif cheap, en *feature* | piste ouverte, non implémentée |

**Écartés, avec raison** : `qwen/qwen3.7-flash` et `minimax/minimax-m3` (sourds) ;
toute la famille `flash-lite` et `gemini-3-flash-preview` pour le timecode
(plafond de famille) ; Groq whisper-large-v3 (perte de contenu).
