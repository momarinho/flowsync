-- Extensão para geração de UUID
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ====================================================================
-- CAMADA 1: STAGING (Auditoria e Ingestão Bruta em Alta Velocidade)
-- ====================================================================
CREATE TABLE IF NOT EXISTS staging_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL, -- Ex: 'MAERSK', 'MSC', 'HAPAG_LLOYD', 'SANTOS_PORT'
    raw_payload JSONB NOT NULL,
    signature VARCHAR(255),
    status VARCHAR(30) DEFAULT 'PENDING', -- 'PENDING', 'PROCESSED', 'QUARANTINED'
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_status ON staging_events(status);
CREATE INDEX IF NOT EXISTS idx_staging_provider ON staging_events(provider);

-- ====================================================================
-- CAMADA 2: CORE (Tabelas Canônicas de Comércio Exterior com ACID)
-- ====================================================================
CREATE TABLE IF NOT EXISTS core_shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_number VARCHAR(100) UNIQUE NOT NULL,
    bill_of_lading VARCHAR(100) NOT NULL,
    container_number VARCHAR(15) NOT NULL, -- Padrão ISO 6346 (ex: MSCU1234567)
    origin_port VARCHAR(10) NOT NULL,      -- UN/LOCODE (ex: 'BRSSZ' Santos)
    destination_port VARCHAR(10) NOT NULL, -- UN/LOCODE (ex: 'CNSHA' Xangai)
    incoterm VARCHAR(5) NOT NULL,          -- 'FOB', 'CIF', 'EXW', 'DDP', etc.
    declared_value NUMERIC(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,          -- 'USD', 'BRL', 'EUR'
    current_status VARCHAR(50) NOT NULL,   -- 'BOOKED', 'IN_TRANSIT', 'CUSTOMS_CLEARANCE', 'DELIVERED'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS core_shipment_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID REFERENCES core_shipments(id) ON DELETE CASCADE,
    event_code VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(100),
    occurred_at TIMESTAMPTZ NOT NULL,
    -- Chave composta de idempotência para evitar duplicação de eventos de navio/porto
    idempotency_hash VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ====================================================================
-- CAMADA 3: QUARENTENA (Isolamento de Contratos Quebrados sem Falhar API)
-- ====================================================================
CREATE TABLE IF NOT EXISTS quarantine_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staging_event_id UUID REFERENCES staging_events(id) ON DELETE SET NULL,
    provider VARCHAR(50) NOT NULL,
    raw_payload JSONB NOT NULL,
    rejection_reason VARCHAR(100) NOT NULL, -- 'CONTRACT_VALIDATION_FAILED', 'INVALID_SIGNATURE'
    validation_errors JSONB NOT NULL,       -- Relatório detalhado de validação Zod
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quarantine_resolved ON quarantine_events(resolved);

-- ====================================================================
-- VIEWS ANALÍTICAS (Métricas de Integração para Observabilidade e BI)
-- ====================================================================
CREATE OR REPLACE VIEW v_integration_metrics AS
SELECT
    COUNT(*) AS total_ingested,
    COUNT(*) FILTER (WHERE status = 'PROCESSED') AS total_processed,
    COUNT(*) FILTER (WHERE status = 'QUARANTINED') AS total_quarantined,
    ROUND(
        (COUNT(*) FILTER (WHERE status = 'PROCESSED')::NUMERIC / NULLIF(COUNT(*), 0) * 100), 2
    ) AS success_rate_percentage
FROM staging_events;
