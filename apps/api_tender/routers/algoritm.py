"""АЛГОРИТМ policy-graph HTTP routes (Phase 5, task 5.D,
docs/reports/PLAN-MISSION-5.md Section3 task 5.D). First HTTP surface over
packages/algorithm -- 5.A/5.B/5.C built a pure backend with none. Every
route here is a thin wrapper over an already-real packages/algorithm
function; no business logic is added at this layer, matching every other
router in this app (calibration.py, decision.py).

Domain ValueErrors (PolicyNode construction, ImmutableVersionError,
InvalidTransitionError, GraphInvalidError, MakerCheckerViolation) are
caught at the route boundary and turned into a clean 4xx ApiError -- never
an uncaught 500 (same discipline calibration.py's _validated_outcome
already applies to TenderOutcome/LossReason construction).

Permission strings (`algorithm.policy.*`/`algorithm.simulation.*`) are new
-- permissions are ungoverned free text in this codebase, granted per role
via role_permissions (packages/platform/rbac), the same as every existing
route's permission string; there is no central enum to update."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.algorithm import policy_store, research_dossier_store, simulation_store
from packages.algorithm.policy_model import PolicyEdge, PolicyGraph, PolicyNode
from packages.algorithm.policy_store import (
    GraphInvalidError,
    ImmutableVersionError,
    InvalidTransitionError,
    MakerCheckerViolation,
)
from packages.algorithm.policy_validator import validate_graph
from packages.algorithm.research_dossier_model import ResearchDossier
from packages.algorithm.simulation_engine import SimulationCase, compare_versions, run_simulation
from packages.platform.errors import ApiError
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity

from ..deps import get_connection, get_current_identity

router = APIRouter(tags=["algoritm"])

READ = "algorithm.policy.read"
WRITE = "algorithm.policy.write"
APPROVE = "algorithm.policy.approve"
ACTIVATE = "algorithm.policy.activate"
SIM_READ = "algorithm.simulation.read"
SIM_WRITE = "algorithm.simulation.write"


def _domain_error(exc: Exception) -> ApiError:
    if isinstance(exc, GraphInvalidError):
        return ApiError(
            status_code=422,
            code="graph_invalid",
            message=str(exc),
            details=[{"code": i.code, "message": i.message, "node_key": i.node_key} for i in exc.issues],
        )
    if isinstance(exc, MakerCheckerViolation):
        return ApiError(status_code=409, code="maker_checker_violation", message=str(exc))
    if isinstance(exc, ImmutableVersionError):
        return ApiError(status_code=409, code="version_immutable", message=str(exc))
    if isinstance(exc, InvalidTransitionError):
        return ApiError(status_code=409, code="invalid_transition", message=str(exc))
    return ApiError(status_code=422, code="invalid_request", message=str(exc))


async def _get_version_or_404(conn: AsyncConnection, version_id: int) -> dict[str, Any]:
    version = await policy_store.get_version(conn, policy_version_id=version_id)
    if version is None:
        raise ApiError(status_code=404, code="policy_version_not_found", message=f"policy_version {version_id} not found")
    return version


# ---------------------------------------------------------------- graphs/versions


class PolicyGraphRequest(BaseModel):
    name: str
    owner: str
    description: str | None = None


class PolicyGraphResponse(BaseModel):
    id: int
    name: str
    owner: str
    description: str | None


class PolicyVersionResponse(BaseModel):
    id: int
    policy_graph_id: int
    version_number: int
    status: str
    research_dossier_id: int | None
    created_by: str
    created_at: str


class VersionListResponse(BaseModel):
    items: list[PolicyVersionResponse]


def _version_row_to_response(row: dict[str, Any]) -> PolicyVersionResponse:
    return PolicyVersionResponse(
        id=row["id"],
        policy_graph_id=row["policy_graph_id"],
        version_number=row["version_number"],
        status=row["status"],
        research_dossier_id=row["research_dossier_id"],
        created_by=row["created_by"],
        created_at=row["created_at"].isoformat(),
    )


@router.post("/policy-graphs", response_model=PolicyGraphResponse)
async def post_policy_graph(
    payload: PolicyGraphRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> PolicyGraphResponse:
    try:
        graph = PolicyGraph(name=payload.name, owner=payload.owner, description=payload.description)
    except ValueError as exc:
        raise _domain_error(exc) from exc
    graph_id = await policy_store.create_policy_graph(conn, graph)
    return PolicyGraphResponse(id=graph_id, name=graph.name, owner=graph.owner, description=graph.description)


class DraftVersionRequest(BaseModel):
    version_number: int


@router.post("/policy-graphs/{graph_id}/versions", response_model=PolicyVersionResponse)
async def post_draft_version(
    graph_id: int,
    payload: DraftVersionRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> PolicyVersionResponse:
    version_id = await policy_store.create_draft_version(
        conn, policy_graph_id=graph_id, version_number=payload.version_number, created_by=identity.subject
    )
    return _version_row_to_response(await _get_version_or_404(conn, version_id))


@router.get("/policy-graphs/{graph_id}/versions", response_model=VersionListResponse)
async def get_versions(
    graph_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(READ, get_current_identity)),
) -> VersionListResponse:
    versions = await policy_store.list_versions_by_graph(conn, policy_graph_id=graph_id)
    return VersionListResponse(items=[_version_row_to_response(v) for v in versions])


@router.post("/policy-versions/{version_id}/fork", response_model=PolicyVersionResponse)
async def post_fork(
    version_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> PolicyVersionResponse:
    new_version_id = await policy_store.fork_new_draft_version(
        conn, from_policy_version_id=version_id, created_by=identity.subject
    )
    return _version_row_to_response(await _get_version_or_404(conn, new_version_id))


# ---------------------------------------------------------------- nodes/edges


class PolicyNodeRequest(BaseModel):
    node_key: str
    node_type: str
    title: str
    purpose: str
    owner: str
    execution_mode: str
    input_contract: dict[str, str] = {}
    output_contract: dict[str, str] = {}
    preconditions: list[str] = []
    evidence_requirements: list[str] = []
    reason_codes: list[str] = []
    test_cases: list[dict[str, Any]] = []
    monitoring_metrics: list[str] = []
    timeout_seconds: int | None = None
    retry_policy: dict[str, Any] | None = None
    fallback_node_key: str | None = None
    required_role: str | None = None
    financial_impact: bool = False
    legal_impact: bool = False
    model_or_policy_dependency: str | None = None


class PolicyEdgeRequest(BaseModel):
    from_node_key: str
    to_node_key: str
    condition_label: str | None = None


class PolicyVersionContentResponse(BaseModel):
    version: PolicyVersionResponse
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


def _row_for_response(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in ("id", "created_at")}


@router.get("/policy-versions/{version_id}", response_model=PolicyVersionContentResponse)
async def get_version_content(
    version_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(READ, get_current_identity)),
) -> PolicyVersionContentResponse:
    version = await _get_version_or_404(conn, version_id)
    nodes = await policy_store.list_nodes(conn, policy_version_id=version_id)
    edges = await policy_store.list_edges(conn, policy_version_id=version_id)
    return PolicyVersionContentResponse(
        version=_version_row_to_response(version),
        nodes=[_row_for_response(n) for n in nodes],
        edges=[_row_for_response(e) for e in edges],
    )


@router.post("/policy-versions/{version_id}/nodes", response_model=PolicyVersionContentResponse)
async def post_nodes(
    version_id: int,
    payload: list[PolicyNodeRequest],
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> PolicyVersionContentResponse:
    await _get_version_or_404(conn, version_id)
    try:
        nodes = [
            PolicyNode(
                policy_version_id=version_id,
                node_key=p.node_key,
                node_type=p.node_type,
                title=p.title,
                purpose=p.purpose,
                owner=p.owner,
                execution_mode=p.execution_mode,
                input_contract=p.input_contract,
                output_contract=p.output_contract,
                preconditions=tuple(p.preconditions),
                evidence_requirements=tuple(p.evidence_requirements),
                reason_codes=tuple(p.reason_codes),
                test_cases=tuple(p.test_cases),
                monitoring_metrics=tuple(p.monitoring_metrics),
                timeout_seconds=p.timeout_seconds,
                retry_policy=p.retry_policy,
                fallback_node_key=p.fallback_node_key,
                required_role=p.required_role,
                financial_impact=p.financial_impact,
                legal_impact=p.legal_impact,
                model_or_policy_dependency=p.model_or_policy_dependency,
            )
            for p in payload
        ]
    except ValueError as exc:
        raise _domain_error(exc) from exc

    try:
        await policy_store.add_nodes(conn, nodes)
    except ImmutableVersionError as exc:
        raise _domain_error(exc) from exc

    return await get_version_content(version_id, conn=conn, identity=identity)


@router.post("/policy-versions/{version_id}/edges", response_model=PolicyVersionContentResponse)
async def post_edges(
    version_id: int,
    payload: list[PolicyEdgeRequest],
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> PolicyVersionContentResponse:
    await _get_version_or_404(conn, version_id)
    try:
        edges = [
            PolicyEdge(
                policy_version_id=version_id,
                from_node_key=p.from_node_key,
                to_node_key=p.to_node_key,
                condition_label=p.condition_label,
            )
            for p in payload
        ]
    except ValueError as exc:
        raise _domain_error(exc) from exc

    try:
        await policy_store.add_edges(conn, edges)
    except ImmutableVersionError as exc:
        raise _domain_error(exc) from exc

    return await get_version_content(version_id, conn=conn, identity=identity)


# ---------------------------------------------------------------- validation/lifecycle


class ValidationIssueResponse(BaseModel):
    code: str
    message: str
    node_key: str | None


class ValidationResultResponse(BaseModel):
    issues: list[ValidationIssueResponse]


@router.post("/policy-versions/{version_id}/validate", response_model=ValidationResultResponse)
async def post_validate(
    version_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(READ, get_current_identity)),
) -> ValidationResultResponse:
    """FR-ALG-01's edit-time check -- calls the same DB-free
    policy_validator.validate_graph a future canvas editor could call
    client-side; this route just makes it reachable over HTTP against
    already-persisted content without submitting for approval."""
    await _get_version_or_404(conn, version_id)
    nodes = await policy_store.list_nodes(conn, policy_version_id=version_id)
    edges = await policy_store.list_edges(conn, policy_version_id=version_id)
    issues = validate_graph(nodes, edges)
    return ValidationResultResponse(
        issues=[ValidationIssueResponse(code=i.code, message=i.message, node_key=i.node_key) for i in issues]
    )


class TransitionRequest(BaseModel):
    to_status: str
    reason: str | None = None


class ReasonRequest(BaseModel):
    reason: str | None = None


@router.post("/policy-versions/{version_id}/transition", response_model=PolicyVersionResponse)
async def post_transition(
    version_id: int,
    payload: TransitionRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> PolicyVersionResponse:
    """Every transition EXCEPT risk_review->approved (post_submit_for_approval)
    and approved/suspended->active (post_activate), which have their own
    dedicated, more heavily-gated routes below."""
    try:
        await policy_store.transition_version_status(
            conn, policy_version_id=version_id, to_status=payload.to_status, changed_by=identity.subject, reason=payload.reason
        )
    except InvalidTransitionError as exc:
        raise _domain_error(exc) from exc
    return _version_row_to_response(await _get_version_or_404(conn, version_id))


@router.post("/policy-versions/{version_id}/submit-for-approval", response_model=PolicyVersionResponse)
async def post_submit_for_approval(
    version_id: int,
    payload: ReasonRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(APPROVE, get_current_identity)),
) -> PolicyVersionResponse:
    try:
        await policy_store.submit_for_approval(
            conn, policy_version_id=version_id, changed_by=identity.subject, reason=payload.reason
        )
    except (GraphInvalidError, InvalidTransitionError) as exc:
        raise _domain_error(exc) from exc
    return _version_row_to_response(await _get_version_or_404(conn, version_id))


@router.post("/policy-versions/{version_id}/activate", response_model=PolicyVersionResponse)
async def post_activate(
    version_id: int,
    payload: ReasonRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(ACTIVATE, get_current_identity)),
) -> PolicyVersionResponse:
    try:
        await policy_store.activate_version(
            conn, policy_version_id=version_id, changed_by=identity.subject, reason=payload.reason
        )
    except (MakerCheckerViolation, InvalidTransitionError) as exc:
        raise _domain_error(exc) from exc
    return _version_row_to_response(await _get_version_or_404(conn, version_id))


class KillSwitchRequest(BaseModel):
    reason: str


@router.post("/policy-versions/{version_id}/kill-switch", response_model=PolicyVersionResponse)
async def post_kill_switch(
    version_id: int,
    payload: KillSwitchRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(ACTIVATE, get_current_identity)),
) -> PolicyVersionResponse:
    try:
        await policy_store.kill_switch(conn, policy_version_id=version_id, changed_by=identity.subject, reason=payload.reason)
    except ValueError as exc:
        raise _domain_error(exc) from exc
    return _version_row_to_response(await _get_version_or_404(conn, version_id))


class TransitionResponse(BaseModel):
    id: int
    policy_version_id: int
    from_status: str
    to_status: str
    changed_by: str
    changed_at: str
    reason: str | None


class TransitionListResponse(BaseModel):
    items: list[TransitionResponse]


@router.get("/policy-versions/{version_id}/transitions", response_model=TransitionListResponse)
async def get_transitions(
    version_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(READ, get_current_identity)),
) -> TransitionListResponse:
    rows = await policy_store.list_transitions_by_version(conn, policy_version_id=version_id)
    return TransitionListResponse(
        items=[
            TransitionResponse(
                id=r["id"],
                policy_version_id=r["policy_version_id"],
                from_status=r["from_status"],
                to_status=r["to_status"],
                changed_by=r["changed_by"],
                changed_at=r["changed_at"].isoformat(),
                reason=r["reason"],
            )
            for r in rows
        ]
    )


# ---------------------------------------------------------------- simulation


class SimulationCaseRequest(BaseModel):
    case_id: str
    inputs: dict[str, Any] = {}
    human_overrides: dict[str, str] = {}
    monetary_amount: str | None = None
    monetary_currency: str | None = None
    actual_outcome_label: str | None = None


class SimulateRequest(BaseModel):
    case_set_label: str
    case_source: str
    cases: list[SimulationCaseRequest]


class SimulationRunResponse(BaseModel):
    id: int
    policy_version_id: int
    compared_against_version_id: int | None
    case_set_label: str
    case_source: str
    case_count: int
    completed_count: int
    awaiting_human_count: int
    undetermined_count: int
    terminal_distribution: dict[str, int]
    reason_code_distribution: dict[str, int]
    monetary_range: dict[str, Any] | None
    monetary_amount_uncurrencied_count: int
    run_by: str
    run_at: str
    notes: str | None


def _parse_amount(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ApiError(status_code=422, code="invalid_monetary_amount", message=f"not a valid decimal: {value!r}") from exc


def _run_row_to_response(row: dict[str, Any]) -> SimulationRunResponse:
    return SimulationRunResponse(
        id=row["id"],
        policy_version_id=row["policy_version_id"],
        compared_against_version_id=row["compared_against_version_id"],
        case_set_label=row["case_set_label"],
        case_source=row["case_source"],
        case_count=row["case_count"],
        completed_count=row["completed_count"],
        awaiting_human_count=row["awaiting_human_count"],
        undetermined_count=row["undetermined_count"],
        terminal_distribution=row["terminal_distribution"],
        reason_code_distribution=row["reason_code_distribution"],
        monetary_range=row["monetary_range"],
        monetary_amount_uncurrencied_count=row["monetary_amount_uncurrencied_count"],
        run_by=row["run_by"],
        run_at=row["run_at"].isoformat(),
        notes=row["notes"],
    )


@router.post("/policy-versions/{version_id}/simulate", response_model=SimulationRunResponse)
async def post_simulate(
    version_id: int,
    payload: SimulateRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(SIM_WRITE, get_current_identity)),
) -> SimulationRunResponse:
    await _get_version_or_404(conn, version_id)
    nodes = await policy_store.list_nodes(conn, policy_version_id=version_id)
    edges = await policy_store.list_edges(conn, policy_version_id=version_id)

    cases = [
        SimulationCase(
            case_id=c.case_id,
            inputs=c.inputs,
            human_overrides=c.human_overrides,
            monetary_amount=_parse_amount(c.monetary_amount),
            monetary_currency=c.monetary_currency,
            actual_outcome_label=c.actual_outcome_label,
        )
        for c in payload.cases
    ]
    try:
        traces = run_simulation(nodes, edges, cases)
    except ValueError as exc:
        raise _domain_error(exc) from exc

    run_id = await simulation_store.record_simulation_run(
        conn,
        policy_version_id=version_id,
        case_set_label=payload.case_set_label,
        case_source=payload.case_source,
        traces=traces,
        run_by=identity.subject,
        cases=cases,
    )
    run = await simulation_store.get_simulation_run(conn, run_id=run_id)
    assert run is not None
    return _run_row_to_response(run)


@router.get("/simulation-runs/{run_id}", response_model=SimulationRunResponse)
async def get_run(
    run_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(SIM_READ, get_current_identity)),
) -> SimulationRunResponse:
    run = await simulation_store.get_simulation_run(conn, run_id=run_id)
    if run is None:
        raise ApiError(status_code=404, code="simulation_run_not_found", message=f"simulation run {run_id} not found")
    return _run_row_to_response(run)


class CaseTracesResponse(BaseModel):
    items: list[dict[str, Any]]


@router.get("/simulation-runs/{run_id}/case-traces", response_model=CaseTracesResponse)
async def get_case_traces(
    run_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(SIM_READ, get_current_identity)),
) -> CaseTracesResponse:
    return CaseTracesResponse(items=await simulation_store.list_case_traces(conn, run_id=run_id))


@router.get("/policy-versions/{version_id}/simulation-runs", response_model=list[SimulationRunResponse])
async def get_runs_for_version(
    version_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(SIM_READ, get_current_identity)),
) -> list[SimulationRunResponse]:
    runs = await simulation_store.list_simulation_runs_by_version(conn, policy_version_id=version_id)
    return [_run_row_to_response(r) for r in runs]


class CompareRequest(BaseModel):
    case_set_label: str
    cases: list[SimulationCaseRequest]


@router.post("/policy-versions/{version_id}/compare/{other_version_id}", response_model=SimulationRunResponse)
async def post_compare(
    version_id: int,
    other_version_id: int,
    payload: CompareRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(SIM_WRITE, get_current_identity)),
) -> SimulationRunResponse:
    await _get_version_or_404(conn, version_id)
    await _get_version_or_404(conn, other_version_id)
    nodes_a = await policy_store.list_nodes(conn, policy_version_id=version_id)
    edges_a = await policy_store.list_edges(conn, policy_version_id=version_id)
    nodes_b = await policy_store.list_nodes(conn, policy_version_id=other_version_id)
    edges_b = await policy_store.list_edges(conn, policy_version_id=other_version_id)

    cases = [SimulationCase(case_id=c.case_id, inputs=c.inputs, human_overrides=c.human_overrides) for c in payload.cases]
    try:
        comparisons = compare_versions(nodes_a, edges_a, nodes_b, edges_b, cases)
    except ValueError as exc:
        raise _domain_error(exc) from exc

    run_id = await simulation_store.record_comparison_run(
        conn,
        policy_version_id=version_id,
        compared_against_version_id=other_version_id,
        case_set_label=payload.case_set_label,
        comparisons=comparisons,
        run_by=identity.subject,
    )
    run = await simulation_store.get_simulation_run(conn, run_id=run_id)
    assert run is not None
    return _run_row_to_response(run)


# ---------------------------------------------------------------- research dossiers


class ResearchDossierRequest(BaseModel):
    decision_statement: str
    owners: list[str]
    approvers: list[str]
    source_register: list[dict[str, Any]]
    assumptions: list[str]
    data_dictionary: dict[str, str]
    formula_or_decision_table: dict[str, Any]
    coefficients_and_rationale: dict[str, Any]
    validation_design: dict[str, Any]
    test_dataset_manifest: dict[str, Any]
    results_and_limitations: dict[str, Any]
    security_privacy_analysis: dict[str, Any]
    monitoring_criteria: dict[str, Any]
    retirement_criteria: dict[str, Any]
    fairness_analysis: dict[str, Any] | None = None
    approved_at: str | None = None
    effective_from: str | None = None


class ResearchDossierResponse(BaseModel):
    id: int
    decision_statement: str
    approved_at: str | None


@router.post("/research-dossiers", response_model=ResearchDossierResponse)
async def post_research_dossier(
    payload: ResearchDossierRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> ResearchDossierResponse:
    try:
        dossier = ResearchDossier(
            decision_statement=payload.decision_statement,
            owners=tuple(payload.owners),
            approvers=tuple(payload.approvers),
            source_register=tuple(payload.source_register),
            assumptions=tuple(payload.assumptions),
            data_dictionary=payload.data_dictionary,
            formula_or_decision_table=payload.formula_or_decision_table,
            coefficients_and_rationale=payload.coefficients_and_rationale,
            validation_design=payload.validation_design,
            test_dataset_manifest=payload.test_dataset_manifest,
            results_and_limitations=payload.results_and_limitations,
            security_privacy_analysis=payload.security_privacy_analysis,
            monitoring_criteria=payload.monitoring_criteria,
            retirement_criteria=payload.retirement_criteria,
            created_by=identity.subject,
            fairness_analysis=payload.fairness_analysis,
            approved_at=payload.approved_at,
            effective_from=payload.effective_from,
        )
    except ValueError as exc:
        raise _domain_error(exc) from exc
    dossier_id = await research_dossier_store.store_research_dossier(conn, dossier)
    return ResearchDossierResponse(id=dossier_id, decision_statement=dossier.decision_statement, approved_at=dossier.approved_at)


@router.get("/research-dossiers/{dossier_id}", response_model=dict[str, Any])
async def get_research_dossier_route(
    dossier_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(READ, get_current_identity)),
) -> dict[str, Any]:
    dossier = await research_dossier_store.get_research_dossier(conn, dossier_id=dossier_id)
    if dossier is None:
        raise ApiError(status_code=404, code="research_dossier_not_found", message=f"research dossier {dossier_id} not found")
    return dossier


class LinkDossierRequest(BaseModel):
    research_dossier_id: int


@router.post("/policy-versions/{version_id}/link-dossier", response_model=PolicyVersionResponse)
async def post_link_dossier(
    version_id: int,
    payload: LinkDossierRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission(WRITE, get_current_identity)),
) -> PolicyVersionResponse:
    await _get_version_or_404(conn, version_id)
    await research_dossier_store.link_dossier_to_version(
        conn, policy_version_id=version_id, research_dossier_id=payload.research_dossier_id
    )
    return _version_row_to_response(await _get_version_or_404(conn, version_id))
