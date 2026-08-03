# Architecture Decision Records

ADRs are numbered sequentially and never renumbered or deleted. A superseded ADR is marked `Superseded by ADR-000N` in its own file and stays in place for history.

| ADR | Title | Requirements |
|---|---|---|
| [0001](0001-modular-monolith-boundaries.md) | Modular monolith with enforced domain boundaries | NFR-ARC-05..07, DM-01, INV-02 |
| [0002](0002-technology-stack.md) | Technology stack | NFR-ARC-01..04, NFR-ARC-06 |
| [0003](0003-data-authority-and-provenance.md) | Data authority and provenance: four immutable layers | DM-01..06, INV-01, INV-02, INV-04, INV-05, INV-11, INV-12 |
| [0004](0004-synthetic-real-isolation.md) | Synthetic/real vendor data isolation | FR-VND-06, NEG-04, INV-11 |
| [0005](0005-authority-model.md) | Human/algorithm/ML authority model | FR-AUT-01..06, INV-06, INV-07, INV-13, INV-14 |

Required by `NFR-ARC-07` for every boundary/stack/data-authority decision. Kept current per `NFR-DOC-01`.
