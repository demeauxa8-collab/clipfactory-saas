-- DRAFT — migration 0005 (job leasing / parallel workers)
-- NE PAS placer dans db/migrations/ tant que le design n'est pas validé.
-- Additive et sans risque : ajoute des colonnes nullables + index.
-- Voir docs/architecture/parallel-workers.md

-- ============================================================
-- jobs : colonnes de lease pour le claim atomique + reaper
-- ============================================================

alter table public.jobs
  add column if not exists claimed_at        timestamptz,
  add column if not exists heartbeat_at      timestamptz,
  add column if not exists attempts          integer not null default 0;
-- worker_id text existe déjà (migration 0001) — enfin utilisé.

-- Index pour le claim : plus vieux job queued en premier.
-- (idx_jobs_status_queued_at existe déjà en 0001 ; on garde.)

-- Index pour le reaper : trouver vite les jobs running au heartbeat périmé.
create index if not exists idx_jobs_heartbeat_running
  on public.jobs (heartbeat_at)
  where status in ('downloading', 'transcribing', 'analyzing', 'rendering');

-- ============================================================
-- Notes de promotion
-- ============================================================
-- - Si on garde retry_count (0002) au lieu de `attempts`, supprimer la colonne
--   ci-dessus et utiliser retry_count partout dans le code parallèle.
-- - lease_expires_at non ajouté : on calcule l'expiration à la volée
--   (heartbeat_at < now() - JOB_LEASE_SECONDS) plutôt que de stocker une date.
