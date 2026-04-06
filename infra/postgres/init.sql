-- PostgreSQL Initialization Script
-- Ejecutado automáticamente en el primer arranque del contenedor

-- ============================================================================
-- EXTENSIONES
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- pg_trgm: Para búsquedas fuzzy/similitud en texto (índice GIN trigram)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS itv;

-- ============================================================================
-- PERMISOS
-- ============================================================================

-- Garantizar que el usuario de la aplicación tenga permisos completos
GRANT ALL PRIVILEGES ON SCHEMA itv TO itv_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA itv TO itv_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA itv TO itv_user;

-- Permisos para objetos futuros creados por Alembic
ALTER DEFAULT PRIVILEGES IN SCHEMA itv GRANT ALL ON TABLES TO itv_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA itv GRANT ALL ON SEQUENCES TO itv_user;

-- ============================================================================
-- LOG DE INICIALIZACIÓN
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'ITV Database Environment Initialized';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'PostGIS version: %', PostGIS_Version();
    RAISE NOTICE 'Schema created: itv';
    RAISE NOTICE 'Extensions enabled: postgis, postgis_topology, pg_trgm';
    RAISE NOTICE '----------------------------------------';
    RAISE NOTICE 'Tables will be managed by Alembic migrations';
    RAISE NOTICE 'Run: alembic upgrade head';
    RAISE NOTICE '========================================';
END $$;
