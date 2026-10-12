-- Schéma D1 du SaaS PostAgent. Rejouable : tout est en IF NOT EXISTS.
-- Les dates sont des chaînes ISO 8601 en UTC (toISOString), donc comparables
-- telles quelles. Chaque table métier porte user_id : aucune requête ne lit
-- un post sans filtrer sur son propriétaire.

CREATE TABLE IF NOT EXISTS users (
  id               TEXT PRIMARY KEY,
  person_urn       TEXT NOT NULL UNIQUE,
  name             TEXT,
  token_enc        TEXT NOT NULL,          -- jeton LinkedIn chiffré (AES-GCM), jamais en clair
  token_expires_at TEXT NOT NULL,
  consent_at       TEXT NOT NULL,          -- dernier consentement explicite (API Terms §5.2)
  created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,             -- empreinte SHA-256 du cookie, pas sa valeur
  user_id    TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_states (
  state      TEXT PRIMARY KEY,
  invite_ok  INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL,
  text         TEXT NOT NULL,
  -- Pas de DEFAULT : une visibilité absente est une erreur, pas un choix.
  visibility   TEXT NOT NULL CHECK (visibility IN ('PUBLIC', 'CONNECTIONS')),
  media_kind   TEXT CHECK (media_kind IN ('image', 'document', 'carousel')),
  media_title  TEXT,
  media_data   BLOB,                       -- image ou PDF déposé ; vidé après publication
  carousel     TEXT,                       -- pages du carrousel en JSON, rendues à la publication
  scheduled_at TEXT NOT NULL,
  status       TEXT NOT NULL CHECK (status IN ('scheduled', 'publishing', 'published', 'failed', 'stale', 'cancelled')),
  post_id      TEXT,                       -- identifiant LinkedIn : sans lui le post est irrécupérable
  error        TEXT,
  created_at   TEXT NOT NULL,
  published_at TEXT
);

CREATE INDEX IF NOT EXISTS posts_dus ON posts (status, scheduled_at);
CREATE INDEX IF NOT EXISTS posts_membre ON posts (user_id, scheduled_at);
