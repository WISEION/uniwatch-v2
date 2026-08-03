-- Platform core: RBAC (deny-by-default), idempotency, audit.
-- FR-ADM-01..05, INV-08, FR-PLT-03

CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- permissions -> roles is configuration, not code (FR-ADM-03).
CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL REFERENCES roles (id),
    permission_id BIGINT NOT NULL REFERENCES permissions (id),
    PRIMARY KEY (role_id, permission_id)
);

-- Users are disabled, never deleted (FR-ADM-04, INV-08): no DELETE statement
-- is ever issued against this table by application code.
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES roles (id),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotency key store for mutating routes (FR-PLT-03). The key together
-- with route + request fingerprint disambiguates a replay from a genuinely
-- new request that happens to reuse a client-supplied key.
CREATE TABLE idempotency_keys (
    idempotency_key TEXT NOT NULL,
    route TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    response_status INTEGER,
    response_body JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (idempotency_key, route)
);

-- Append-only audit log (FR-ADM-05): actor snapshot, object, version, reason,
-- correlation id. Never updated or deleted by application code.
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_version INTEGER,
    reason TEXT,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
