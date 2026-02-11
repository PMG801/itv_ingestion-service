-- PostgreSQL Initialization Script
-- Ejecutado automáticamente en el primer arranque del contenedor

-- Habilitar PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Crear schema para ITV stations
CREATE SCHEMA IF NOT EXISTS itv;

-- Tabla principal de estaciones ITV
CREATE TABLE IF NOT EXISTS itv.stations (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    address TEXT,
    location GEOMETRY(Point, 4326),  -- PostGIS: SRID 4326 (WGS84)
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    source_system VARCHAR(100) NOT NULL,
    raw_data JSONB,  -- Store original data for audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para optimizar búsquedas
CREATE INDEX IF NOT EXISTS idx_stations_station_id ON itv.stations(station_id);
CREATE INDEX IF NOT EXISTS idx_stations_source_system ON itv.stations(source_system);
CREATE INDEX IF NOT EXISTS idx_stations_created_at ON itv.stations(created_at);

-- Índice espacial para consultas geográficas
CREATE INDEX IF NOT EXISTS idx_stations_location ON itv.stations USING GIST(location);

-- Trigger para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION itv.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_stations_updated_at
    BEFORE UPDATE ON itv.stations
    FOR EACH ROW
    EXECUTE FUNCTION itv.update_updated_at_column();

-- Tabla de auditoría (opcional, para tracking de cambios)
CREATE TABLE IF NOT EXISTS itv.ingestion_log (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    domain VARCHAR(100) NOT NULL,
    source_system VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,  -- 'success', 'failed', 'processing'
    error_message TEXT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_message_id ON itv.ingestion_log(message_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_status ON itv.ingestion_log(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_processed_at ON itv.ingestion_log(processed_at);

-- Grants (el usuario ya es owner, pero por claridad)
GRANT ALL PRIVILEGES ON SCHEMA itv TO itv_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA itv TO itv_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA itv TO itv_user;

-- Log de inicialización
DO $$
BEGIN
    RAISE NOTICE 'ITV Database initialized successfully';
    RAISE NOTICE 'PostGIS version: %', PostGIS_Version();
END $$;
