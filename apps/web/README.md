# apps/web

React/TypeScript UI (`NFR-ARC-01`). All permission checks shown here are re-verified server-side; this app
never is the source of authorization truth (`FR-ADM-02`).

**Phase 5, task 5.D (2026-08-14): the АЛГОРИТМ outline/table builder is implemented** —
`src/PolicyOutline.tsx` (node/edge table + add-node/add-edge forms + inline validation issues),
`src/SimulationPanel.tsx` (run simulations, per-case "why accepted" execution trace),
`src/TransitionHistory.tsx` (append-only approval/rollback log), `src/exportJson.ts` (machine-readable
export). This is the WCAG-accessible alternative form master plan §12.5 names alongside canvas
(`FR-ALG-07`) — built as a complete UI on its own, not a placeholder for canvas.

**Not yet built** (recorded as gaps, `docs/decisions/OPEN-QUESTIONS.md` 2026-08-14 task 5.D entry, not
silently reduced): the drag-and-drop canvas editor (zoom/minimap/live impact counters/search-by-node),
version diff view, human-readable PDF/Markdown export. Command Center, tender detail, and deep links
(the rest of `PLAN-MISSION-1.md`'s original Phase 2+ scope for this app) also remain unbuilt.

## Dev commands

```bash
cd apps/web
npm install
npm run dev     # Vite dev server
npm test        # Vitest + Testing Library
npm run build   # tsc --noEmit + vite build
```

The UI's own login form only sets the dev-only `X-Dev-User` header (`apps/api_tender/deps.py` —
`D-IDP`, a real IdP integration, is still an open decision).
