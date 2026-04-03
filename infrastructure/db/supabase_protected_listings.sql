-- =============================================================================
-- SUPABASE: Tabla protegida de listings minados
--
-- Propósito: Archivo permanente de datos minados. NUNCA se puede perder data.
-- Protecciones:
--   1. RLS habilitado — solo service_role puede escribir
--   2. DELETE bloqueado — nadie borra filas, solo soft-delete
--   3. Trigger de auditoría — registra toda modificación
--   4. Política de INSERT idempotente — ON CONFLICT no pierde data existente
-- =============================================================================

-- ─── Schema ──────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS archive;

-- ─── Tabla principal: archivo permanente de listings ─────────────────────────

CREATE TABLE archive.mined_listings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Origen (sin revelar URLs ni metadata de scraping)
    portal_slug     text NOT NULL,                          -- inmuebles24, lamudi, etc.
    external_id     text NOT NULL,                          -- ID del portal

    -- Clasificación
    operation       text NOT NULL CHECK (operation IN ('venta', 'renta', 'vacacional')),
    property_type   text NOT NULL,

    -- Precio
    price           double precision,
    currency        text CHECK (currency IN ('MXN', 'USD')),
    price_mxn       double precision,                       -- precio normalizado a MXN
    price_per_m2    double precision,
    maintenance_fee double precision,

    -- Ubicación (normalizada, sin direcciones exactas)
    state_code      text,                                   -- código INEGI 2 dígitos
    state_name      text,
    municipality    text,
    city            text,
    colony          text,
    zip_code        text,
    latitude        double precision,
    longitude       double precision,

    -- Atributos físicos
    bedrooms        integer,
    bathrooms       numeric(3,1),
    half_bathrooms  integer,
    parking_spaces  integer,
    construction_m2 double precision,
    land_m2         double precision,
    built_levels    integer,
    antiquity       text,
    construction_years integer,

    -- Estado y condición
    conservation_status text,
    has_balcony     boolean,
    has_elevator    boolean,
    has_storage     boolean,

    -- Features (JSONB arrays)
    extra_rooms     jsonb,
    services        jsonb,
    amenities       jsonb,
    exteriors       jsonb,
    extras          jsonb,

    -- Descripción anonimizada (sin nombres, teléfonos, URLs)
    description     text,

    -- Calidad
    quality_score   double precision,
    completeness    double precision,
    source_count    integer DEFAULT 1,

    -- Deduplicación
    dedup_cluster_id uuid,

    -- Timestamps del minado original
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),

    -- Control de archivo
    archived_at     timestamptz NOT NULL DEFAULT now(),     -- cuándo se archivó en Supabase
    is_deleted      boolean NOT NULL DEFAULT false,         -- soft delete, NUNCA hard delete
    deleted_at      timestamptz,

    -- Constraint: un listing por portal+external_id
    CONSTRAINT uq_portal_external UNIQUE (portal_slug, external_id)
);

-- ─── Índices ─────────────────────────────────────────────────────────────────

CREATE INDEX ix_mined_location
    ON archive.mined_listings (state_code, municipality, city, colony);

CREATE INDEX ix_mined_operation_type
    ON archive.mined_listings (operation, property_type);

CREATE INDEX ix_mined_price
    ON archive.mined_listings (price_mxn)
    WHERE price_mxn IS NOT NULL;

CREATE INDEX ix_mined_archived_at
    ON archive.mined_listings (archived_at);

CREATE INDEX ix_mined_not_deleted
    ON archive.mined_listings (is_deleted)
    WHERE is_deleted = false;

-- ─── RLS: solo service_role puede escribir ───────────────────────────────────

ALTER TABLE archive.mined_listings ENABLE ROW LEVEL SECURITY;

-- Lectura: authenticated users pueden leer (para el dashboard)
CREATE POLICY "Authenticated users can read listings"
    ON archive.mined_listings
    FOR SELECT
    TO authenticated
    USING (is_deleted = false);

-- Service role puede leer todo (incluyendo soft-deleted)
CREATE POLICY "Service role full read"
    ON archive.mined_listings
    FOR SELECT
    TO service_role
    USING (true);

-- Solo service_role puede insertar
CREATE POLICY "Service role can insert"
    ON archive.mined_listings
    FOR INSERT
    TO service_role
    WITH CHECK (true);

-- Solo service_role puede actualizar (para enrich y soft-delete)
CREATE POLICY "Service role can update"
    ON archive.mined_listings
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

-- NADIE puede hacer DELETE — esto es la protección clave
-- No hay policy FOR DELETE = DELETE está bloqueado por RLS

-- ─── Tabla de auditoría ──────────────────────────────────────────────────────

CREATE TABLE archive.audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name  text NOT NULL,
    record_id   uuid NOT NULL,
    action      text NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'SOFT_DELETE')),
    changed_by  text NOT NULL DEFAULT current_setting('request.jwt.claim.sub', true),
    changes     jsonb,                                      -- campos que cambiaron
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_audit_record ON archive.audit_log (record_id);
CREATE INDEX ix_audit_created ON archive.audit_log (created_at);

-- ─── Trigger: auditar todo cambio ────────────────────────────────────────────

CREATE OR REPLACE FUNCTION archive.fn_audit_mined_listings()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_action text;
    v_changes jsonb;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_action := 'INSERT';
        v_changes := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        -- Detectar soft-delete
        IF NEW.is_deleted = true AND OLD.is_deleted = false THEN
            v_action := 'SOFT_DELETE';
        ELSE
            v_action := 'UPDATE';
        END IF;

        -- Solo guardar campos que cambiaron
        v_changes := jsonb_object_agg(key, value)
            FROM jsonb_each(to_jsonb(NEW))
            WHERE to_jsonb(NEW) ->> key IS DISTINCT FROM to_jsonb(OLD) ->> key;
    END IF;

    INSERT INTO archive.audit_log (table_name, record_id, action, changes)
    VALUES ('mined_listings', NEW.id, v_action, v_changes);

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_audit_mined_listings
    AFTER INSERT OR UPDATE ON archive.mined_listings
    FOR EACH ROW
    EXECUTE FUNCTION archive.fn_audit_mined_listings();

-- ─── Trigger: forzar soft-delete (prevención extra) ──────────────────────────
-- Si alguien intenta un DELETE real, convertirlo en soft-delete

CREATE OR REPLACE FUNCTION archive.fn_prevent_hard_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- En lugar de borrar, marcar como soft-deleted
    UPDATE archive.mined_listings
    SET is_deleted = true, deleted_at = now()
    WHERE id = OLD.id;

    -- Auditar el intento
    INSERT INTO archive.audit_log (table_name, record_id, action, changes)
    VALUES ('mined_listings', OLD.id, 'SOFT_DELETE',
            jsonb_build_object('note', 'Hard DELETE intercepted and converted to soft-delete'));

    -- Cancelar el DELETE real
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_prevent_hard_delete
    BEFORE DELETE ON archive.mined_listings
    FOR EACH ROW
    EXECUTE FUNCTION archive.fn_prevent_hard_delete();

-- ─── Vista: listings activos (conveniencia) ──────────────────────────────────

CREATE VIEW archive.active_listings AS
SELECT * FROM archive.mined_listings
WHERE is_deleted = false;

-- ─── Comentarios ─────────────────────────────────────────────────────────────

COMMENT ON TABLE archive.mined_listings IS
    'Archivo permanente de listings minados. NUNCA hacer hard delete. Datos protegidos por RLS + triggers.';

COMMENT ON TABLE archive.audit_log IS
    'Log de auditoría inmutable. Registra todo cambio a mined_listings.';

COMMENT ON TRIGGER trg_prevent_hard_delete ON archive.mined_listings IS
    'Intercepta DELETE y lo convierte en soft-delete. Los datos nunca se pierden.';
