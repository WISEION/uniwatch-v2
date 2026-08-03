# apps/worker

Separate Python worker process (`NFR-ARC-03`). Runs durable jobs: ingestion, document/BOQ processing, reconciliation, notification generation, transactional outbox consumers (`FR-JOB-01..08`). No long-running network/IO happens inside `apps/api` request handlers — it happens here.

Not implemented yet — this is task 0.B (worker-connector), not 0.A.
