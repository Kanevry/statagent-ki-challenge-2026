--
-- PostgreSQL database dump
--

\restrict kicmeta

-- Dumped from database version 16.15 (Homebrew)
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: meta; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA meta;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: freigabe; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.freigabe (
    id bigint NOT NULL,
    protokoll_id bigint NOT NULL,
    name text NOT NULL,
    zeitpunkt timestamp with time zone DEFAULT now() NOT NULL,
    entscheidung text NOT NULL,
    begruendung text,
    objekt_typ text,
    objekt_ref text,
    CONSTRAINT freigabe_entscheidung_check CHECK ((entscheidung = ANY (ARRAY['ja'::text, 'nein'::text]))),
    CONSTRAINT freigabe_ja_mit_objekt CHECK (((entscheidung = 'nein'::text) OR (objekt_typ IS NOT NULL))),
    CONSTRAINT freigabe_name_check CHECK ((name <> ''::text)),
    CONSTRAINT freigabe_nein_mit_begruendung CHECK (((entscheidung = 'ja'::text) OR (COALESCE(begruendung, ''::text) <> ''::text))),
    CONSTRAINT freigabe_objekt_typ_check CHECK ((objekt_typ = ANY (ARRAY['datei'::text, 'regel'::text, 'lieferung'::text, 'antwort'::text])))
);


--
-- Name: freigabe_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

ALTER TABLE meta.freigabe ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME meta.freigabe_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: protokoll; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.protokoll (
    id bigint NOT NULL,
    zeit timestamp with time zone DEFAULT now() NOT NULL,
    uc text NOT NULL,
    akteur text NOT NULL,
    name text NOT NULL,
    anweisung text NOT NULL,
    wirkung text,
    vorschlag_typ text,
    status text DEFAULT 'offen'::text NOT NULL,
    modell text,
    provider text,
    ref text,
    commit_hash text,
    CONSTRAINT protokoll_akteur_check CHECK ((akteur = ANY (ARRAY['agent'::text, 'mensch'::text]))),
    CONSTRAINT protokoll_anweisung_check CHECK ((anweisung <> ''::text)),
    CONSTRAINT protokoll_name_check CHECK ((name <> ''::text)),
    CONSTRAINT protokoll_status_check CHECK ((status = ANY (ARRAY['offen'::text, 'freigegeben'::text, 'abgelehnt'::text]))),
    CONSTRAINT protokoll_uc_check CHECK ((uc <> ''::text))
);


--
-- Name: protokoll_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

ALTER TABLE meta.protokoll ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME meta.protokoll_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: freigabe freigabe_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.freigabe
    ADD CONSTRAINT freigabe_pkey PRIMARY KEY (id);


--
-- Name: protokoll protokoll_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.protokoll
    ADD CONSTRAINT protokoll_pkey PRIMARY KEY (id);


--
-- Name: freigabe_protokoll_id_idx; Type: INDEX; Schema: meta; Owner: -
--

CREATE INDEX freigabe_protokoll_id_idx ON meta.freigabe USING btree (protokoll_id);


--
-- Name: protokoll_ref_idx; Type: INDEX; Schema: meta; Owner: -
--

CREATE INDEX protokoll_ref_idx ON meta.protokoll USING btree (ref) WHERE (ref IS NOT NULL);


--
-- Name: protokoll_uc_status_id_idx; Type: INDEX; Schema: meta; Owner: -
--

CREATE INDEX protokoll_uc_status_id_idx ON meta.protokoll USING btree (uc, status, id DESC);


--
-- Name: freigabe freigabe_protokoll_id_fkey; Type: FK CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.freigabe
    ADD CONSTRAINT freigabe_protokoll_id_fkey FOREIGN KEY (protokoll_id) REFERENCES meta.protokoll(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict kicmeta

