"""АЛГОРИТМ policy-graph structural validator (Phase 5, task 5.B,
docs/reports/PLAN-MISSION-5.md Section3 / master plan Section12.6). Pure
functions, no DB -- operates on the same node/edge dict shape
policy_store.list_nodes()/list_edges() already return, so it can be called
either against already-persisted content (policy_store.submit_for_approval)
or against an in-progress draft an editor UI hasn't saved yet (FR-ALG-01's
"проверка ... на этапе редактирования" -- editing-time check).

Phase 5's node-type set has no separate Terminal/Notification-escalation
type (master plan Section12.2 names eight; PLAN-MISSION-5.md Section1 and
policy_model.ACTIVATABLE_NODE_TYPES restrict this phase to four:
human/rule/gate/data_quality). "Start node"/"terminal" below are therefore
read structurally -- a start node is any node with no incoming edge, a
terminal is any node with no outgoing edge -- rather than a dedicated node
type, so no new field is invented to express either.

Two Section12.6 checklist items are NOT checked here, and are recorded in
docs/decisions/OPEN-QUESTIONS.md as honest gaps rather than invented:
"все side effects идут через outbox" (no node in this phase's schema
carries an explicit side-effect concept) and "hard constraints не спрятаны
в soft weights"/"веса суммируются по утверждённой схеме" (no
weighting/scoring schema exists anywhere in this codebase -- D-FIN/TBD-04
forbid inventing one)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NodeDict = dict[str, Any]
EdgeDict = dict[str, Any]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    node_key: str | None = None


def _dangling_reference_issues(nodes: list[NodeDict], edges: list[EdgeDict]) -> list[ValidationIssue]:
    node_keys = {n["node_key"] for n in nodes}
    issues: list[ValidationIssue] = []
    for edge in edges:
        if edge["from_node_key"] not in node_keys:
            issues.append(
                ValidationIssue(
                    "dangling_reference",
                    f"edge references unknown from_node_key {edge['from_node_key']!r}",
                    edge["from_node_key"],
                )
            )
        if edge["to_node_key"] not in node_keys:
            issues.append(
                ValidationIssue(
                    "dangling_reference",
                    f"edge references unknown to_node_key {edge['to_node_key']!r}",
                    edge["to_node_key"],
                )
            )
    for node in nodes:
        fallback = node.get("fallback_node_key")
        if fallback is not None and fallback not in node_keys:
            issues.append(
                ValidationIssue(
                    "dangling_reference",
                    f"node {node['node_key']!r} fallback_node_key references unknown node {fallback!r}",
                    node["node_key"],
                )
            )
    return issues


def _build_adjacency(nodes: list[NodeDict], clean_edges: list[EdgeDict]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Reachability/terminal/cycle purposes all use the graph's *shape*,
    which includes a node's fallback_node_key as an implicit edge -- a
    node reachable only via another node's fallback (an escape hatch a
    human never draws as an explicit PolicyEdge) is a real, intentional
    part of the graph, not an orphan. Dangling fallback references were
    already reported by _dangling_reference_issues and are excluded here
    by construction (clean_edges/valid node_keys only)."""
    node_keys = {n["node_key"] for n in nodes}
    out_adj: dict[str, list[str]] = {k: [] for k in node_keys}
    incoming_adj: dict[str, list[str]] = {k: [] for k in node_keys}
    for edge in clean_edges:
        out_adj[edge["from_node_key"]].append(edge["to_node_key"])
        incoming_adj[edge["to_node_key"]].append(edge["from_node_key"])
    for node in nodes:
        fallback = node.get("fallback_node_key")
        if fallback is not None and fallback in node_keys:
            out_adj[node["node_key"]].append(fallback)
            incoming_adj[fallback].append(node["node_key"])
    return out_adj, incoming_adj


def _reachability_issues(
    nodes: list[NodeDict], out_adj: dict[str, list[str]], incoming_adj: dict[str, list[str]]
) -> list[ValidationIssue]:
    node_keys = {n["node_key"] for n in nodes}
    if not node_keys:
        return [ValidationIssue("empty_graph", "graph has no nodes")]
    if len(node_keys) == 1:
        return []  # a single node is trivially its own start and terminal

    # A node with zero incoming AND zero outgoing edges is disconnected from
    # the rest of a multi-node graph -- not a legitimate entry point, so it
    # is excluded from start_nodes and reported directly rather than ever
    # being silently "reachable from itself."
    islands = {k for k in node_keys if not incoming_adj.get(k) and not out_adj.get(k)}
    issues = [
        ValidationIssue("unreachable_node", f"node {k!r} has no edges at all -- disconnected from the graph", k)
        for k in sorted(islands)
    ]

    start_nodes = {k for k in node_keys - islands if not incoming_adj.get(k)}
    if not start_nodes:
        issues.append(
            ValidationIssue("no_start_node", "no non-isolated node has zero incoming edges -- graph has no entry point")
        )
        return issues

    seen: set[str] = set(start_nodes)
    frontier = list(start_nodes)
    while frontier:
        current = frontier.pop()
        for nxt in out_adj.get(current, ()):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)

    issues += [
        ValidationIssue("unreachable_node", f"node {k!r} is not reachable from any start node", k)
        for k in sorted(node_keys - seen - islands)
    ]

    terminals = {k for k in node_keys if not out_adj.get(k)}
    if not (terminals & seen):
        issues.append(
            ValidationIssue(
                "no_reachable_terminal",
                "no terminal node (zero outgoing edges) is reachable from a start node",
            )
        )
    return issues


def _tarjan_sccs(node_keys: set[str], out_adj: dict[str, list[str]]) -> list[list[str]]:
    """Standard Tarjan's algorithm, iterative recursion depth aside -- graphs
    in this domain are policy graphs authored by a human in an editor, not
    generated data structures with pathological depth."""
    index_counter = [0]
    stack: list[str] = []
    lowlink: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    result: list[list[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True

        for w in out_adj.get(v, ()):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            component: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == v:
                    break
            result.append(component)

    for v in sorted(node_keys):
        if v not in index:
            strongconnect(v)
    return result


def _cycle_issues(nodes: list[NodeDict], out_adj: dict[str, list[str]]) -> list[ValidationIssue]:
    node_keys = {n["node_key"] for n in nodes}
    node_by_key = {n["node_key"]: n for n in nodes}
    issues: list[ValidationIssue] = []

    for component in _tarjan_sccs(node_keys, out_adj):
        is_cycle = len(component) > 1 or component[0] in out_adj.get(component[0], ())
        if not is_cycle:
            continue
        comp_set = set(component)
        valid_exit = False
        for key in component:
            node = node_by_key[key]
            if node.get("node_type") == "human":
                valid_exit = True
                break
            retry_policy = node.get("retry_policy")
            fallback = node.get("fallback_node_key")
            max_attempts = retry_policy.get("max_attempts") if isinstance(retry_policy, dict) else None
            if isinstance(max_attempts, int) and max_attempts > 0 and fallback is not None and fallback not in comp_set:
                valid_exit = True
                break
        if not valid_exit:
            issues.append(
                ValidationIssue(
                    "unbounded_cycle_no_exit",
                    f"cycle {sorted(component)} has no human node and no bounded-retry node with an external fallback",
                    ",".join(sorted(component)),
                )
            )
    return issues


def _io_type_mismatch_issues(nodes: list[NodeDict], clean_edges: list[EdgeDict]) -> list[ValidationIssue]:
    node_by_key = {n["node_key"]: n for n in nodes}
    issues: list[ValidationIssue] = []
    for edge in clean_edges:
        from_node = node_by_key[edge["from_node_key"]]
        to_node = node_by_key[edge["to_node_key"]]
        out_contract = from_node.get("output_contract") or {}
        in_contract = to_node.get("input_contract") or {}
        for key in sorted(set(out_contract) & set(in_contract)):
            if out_contract[key] != in_contract[key]:
                issues.append(
                    ValidationIssue(
                        "io_type_mismatch",
                        f"edge {edge['from_node_key']!r}->{edge['to_node_key']!r}: field {key!r} is "
                        f"{out_contract[key]!r} on output vs {in_contract[key]!r} on input",
                        edge["from_node_key"],
                    )
                )
    return issues


def validate_graph_structure(nodes: list[NodeDict], edges: list[EdgeDict]) -> tuple[ValidationIssue, ...]:
    issues = _dangling_reference_issues(nodes, edges)

    node_keys = {n["node_key"] for n in nodes}
    clean_edges = [e for e in edges if e["from_node_key"] in node_keys and e["to_node_key"] in node_keys]
    out_adj, incoming_adj = _build_adjacency(nodes, clean_edges)

    issues += _reachability_issues(nodes, out_adj, incoming_adj)
    issues += _cycle_issues(nodes, out_adj)
    issues += _io_type_mismatch_issues(nodes, clean_edges)
    return tuple(issues)


def check_branch_coverage(nodes: list[NodeDict], edges: list[EdgeDict]) -> tuple[ValidationIssue, ...]:
    """FR-ALG-04. Requires the covers_condition convention documented above
    the module (and in docs/decisions/OPEN-QUESTIONS.md at this task's
    close-out) on Rule nodes' otherwise-opaque test_cases entries."""
    edges_by_from: dict[str, list[EdgeDict]] = {}
    for edge in edges:
        edges_by_from.setdefault(edge["from_node_key"], []).append(edge)

    issues: list[ValidationIssue] = []
    for node in nodes:
        if node.get("node_type") != "rule":
            continue
        node_key = node["node_key"]
        outgoing = edges_by_from.get(node_key, [])
        if not outgoing:
            continue
        test_cases = node.get("test_cases") or ()
        if not test_cases:
            issues.append(
                ValidationIssue("no_test_cases", f"rule node {node_key!r} has outgoing branches but zero test cases", node_key)
            )
            continue
        labels = {e["condition_label"] for e in outgoing if e.get("condition_label")}
        covered = {tc.get("covers_condition") for tc in test_cases if isinstance(tc, dict)}
        for label in sorted(labels - covered):
            issues.append(
                ValidationIssue(
                    "uncovered_branch",
                    f"rule node {node_key!r} branch {label!r} has no test case with matching covers_condition",
                    node_key,
                )
            )
    return tuple(issues)


def validate_graph(nodes: list[NodeDict], edges: list[EdgeDict]) -> tuple[ValidationIssue, ...]:
    """The one function 5.D's future editor calls at edit time (FR-ALG-01),
    and the one policy_store.submit_for_approval calls as its gate
    (FR-ALG-03/FR-ALG-04) before allowing a risk_review->approved
    transition. Returns every issue found, not just the first."""
    return validate_graph_structure(nodes, edges) + check_branch_coverage(nodes, edges)
