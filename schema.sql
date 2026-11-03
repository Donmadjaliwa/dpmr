-- SUD-KIVU IRL DIGITAL : schéma PostgreSQL de référence
-- (l'API crée aussi les tables automatiquement via SQLAlchemy)
CREATE TABLE utilisateurs (
  id SERIAL PRIMARY KEY, login TEXT UNIQUE NOT NULL, nom TEXT NOT NULL,
  role TEXT NOT NULL, commune TEXT, mdp_hash TEXT NOT NULL, actif BOOLEAN DEFAULT TRUE);
CREATE TABLE contribuables (
  id_contribuable TEXT PRIMARY KEY, nom TEXT NOT NULL, type TEXT, telephone TEXT, commune TEXT);
CREATE TABLE biens (
  id_bien TEXT PRIMARY KEY, id_contribuable TEXT REFERENCES contribuables,
  commune TEXT NOT NULL, quartier TEXT, avenue TEXT, type_bien TEXT, usage TEXT NOT NULL,
  nb_logements INT DEFAULT 1, occupation TEXT, statut TEXT DEFAULT 'En vérification',
  lat DOUBLE PRECISION, lon DOUBLE PRECISION);
CREATE TABLE contrats (
  id_contrat TEXT PRIMARY KEY, id_bien TEXT REFERENCES biens, locataire TEXT,
  loyer_mensuel NUMERIC(12,2), periodicite TEXT, debut DATE, fin DATE);
CREATE TABLE declarations (
  ref TEXT PRIMARY KEY, id_bien TEXT REFERENCES biens, periode INT NOT NULL,
  loyer_annuel_declare NUMERIC(14,2) NOT NULL, taux_applique NUMERIC(6,2) NOT NULL,
  montant_du NUMERIC(14,2) NOT NULL, date DATE, statut TEXT, canal TEXT,
  UNIQUE (id_bien, periode));
CREATE TABLE paiements (
  ref_paiement TEXT PRIMARY KEY, ref_decl TEXT REFERENCES declarations,
  montant NUMERIC(14,2) NOT NULL CHECK (montant > 0), date DATE, canal TEXT,
  confirme BOOLEAN DEFAULT FALSE);
CREATE TABLE parametres (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
CREATE TABLE audit (
  id BIGSERIAL PRIMARY KEY, horodatage TIMESTAMPTZ DEFAULT now(), utilisateur TEXT,
  action TEXT, dossier TEXT, ancienne TEXT, nouvelle TEXT);
CREATE INDEX ON biens (commune); CREATE INDEX ON declarations (id_bien);
CREATE INDEX ON paiements (ref_decl);
