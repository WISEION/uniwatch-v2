-- АЛГОРИТМ page: "only one active version per policy_graph" guard (Phase
-- 5, task 5.B, docs/reports/PLAN-MISSION-5.md Section3 task 5.B row 5 /
-- master plan Section12.4's "activation финансовой policy требует
-- maker/checker" + implicit single-active-version model).
--
-- Nothing before this migration enforced that a graph has at most one
-- `active` version at a time -- packages/algorithm/policy_store.py's new
-- activate_version() auto-suspends the graph's current active version as
-- a courtesy before activating a new one, but that is an application-level
-- convenience, not the guarantee. This partial unique index is the real,
-- structural guarantee (same "structural, not just checked" discipline
-- task 5.A used for content immutability): a second concurrent/buggy
-- activation attempt fails at the database, not just in application code
-- that might have a bug or a race.
CREATE UNIQUE INDEX policy_versions_one_active_per_graph
    ON policy_versions (policy_graph_id)
    WHERE status = 'active';
