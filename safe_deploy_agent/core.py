from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    RELEASE_MANAGER = "release_manager"
    SRE_GUARDIAN = "sre_guardian"
    SECURITY_AUDITOR = "security_auditor"
    ROLLBACK_ENGINEER = "rollback_engineer"


@dataclass(frozen=True)
class DeployRequest:
    service: str
    version: str
    environment: str
    has_tests: bool
    has_rollback: bool
    migration_reversible: bool
    expected_error_budget: float
    contains_secret_change: bool = False


@dataclass(frozen=True)
class DeployContract:
    request: DeployRequest
    action: str
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    invariants: tuple[str, ...]
    forbidden_states: tuple[str, ...]
    rollback_actions: tuple[str, ...]


@dataclass(frozen=True)
class CounterfactualWorld:
    name: str
    violated_condition: str
    severity: int
    recoverable: bool
    mitigation: str


@dataclass(frozen=True)
class Approval:
    role: Role
    accepted: bool
    reason: str


@dataclass(frozen=True)
class DeploymentLedger:
    contract: DeployContract
    worlds: tuple[CounterfactualWorld, ...]
    approvals: tuple[Approval, ...]
    committed: bool
    execution_steps: tuple[str, ...]

    def explain(self) -> str:
        status = "COMMITTED" if self.committed else "REJECTED"
        req = self.contract.request
        lines = [
            f"Status: {status}",
            f"Service: {req.service}",
            f"Version: {req.version}",
            f"Environment: {req.environment}",
            "Contract:",
            f"- action: {self.contract.action}",
            "- preconditions:",
            *[f"  - {item}" for item in self.contract.preconditions],
            "- invariants:",
            *[f"  - {item}" for item in self.contract.invariants],
            "Counterfactual Worlds:",
            *[
                f"- {world.name}: severity={world.severity}, recoverable={world.recoverable}, "
                f"violated={world.violated_condition}, mitigation={world.mitigation}"
                for world in self.worlds
            ],
            "Role Approvals:",
            *[
                f"- {approval.role.value}: {approval.accepted} ({approval.reason})"
                for approval in self.approvals
            ],
            "Execution:",
            *[f"- {step}" for step in self.execution_steps],
        ]
        return "\n".join(lines)


class SafeDeployAgent:
    """A deployment agent designed for the Counterfactual Contract Mesh pattern."""

    APPROVAL_THRESHOLD = 3

    def run(self, request: DeployRequest) -> DeploymentLedger:
        contract = self.propose_contract(request)
        worlds = tuple(self.simulate_counterfactuals(contract))
        approvals = tuple(self.collect_approvals(contract, worlds))
        committed = self.is_committed(approvals)
        execution_steps = (
            tuple(self.execute_contract(contract)) if committed else ("deployment blocked before external change",)
        )
        return DeploymentLedger(
            contract=contract,
            worlds=worlds,
            approvals=approvals,
            committed=committed,
            execution_steps=execution_steps,
        )

    def propose_contract(self, request: DeployRequest) -> DeployContract:
        rollback_actions = ()
        if request.has_rollback:
            rollback_actions = (
                f"shift traffic for {request.service} back to previous stable version",
                "restore previous configuration snapshot",
                "open incident note with failed assumption and metrics",
            )

        return DeployContract(
            request=request,
            action=f"canary deploy {request.service}:{request.version} to {request.environment}",
            preconditions=(
                "unit and integration tests passed",
                "rollback mechanism exists",
                "migration is reversible or explicitly approved",
                "error budget is sufficient for canary exposure",
            ),
            postconditions=(
                "new version serves traffic only after health checks pass",
                "latency and error rate remain within SLO",
                "deployment ledger records decision and recovery path",
            ),
            invariants=(
                "never deploy secret changes without security approval",
                "never promote canary when SLO is violated",
                "never perform irreversible migration without rollback alternative",
            ),
            forbidden_states=(
                "production traffic on untested build",
                "schema migration without recovery path",
                "silent SLO regression",
                "rollback action missing",
            ),
            rollback_actions=rollback_actions,
        )

    def simulate_counterfactuals(
        self, contract: DeployContract
    ) -> list[CounterfactualWorld]:
        req = contract.request
        worlds = [
            CounterfactualWorld(
                name="test_gap_world",
                violated_condition="unit and integration tests passed",
                severity=4 if not req.has_tests else 1,
                recoverable=req.has_tests,
                mitigation="block deployment until tests pass",
            ),
            CounterfactualWorld(
                name="latency_spike_world",
                violated_condition="latency and error rate remain within SLO",
                severity=3,
                recoverable=req.has_rollback,
                mitigation="stop canary and shift traffic to stable version",
            ),
            CounterfactualWorld(
                name="irreversible_migration_world",
                violated_condition="migration is reversible or explicitly approved",
                severity=5 if not req.migration_reversible else 2,
                recoverable=req.migration_reversible and req.has_rollback,
                mitigation="require migration backfill plan or manual approval",
            ),
            CounterfactualWorld(
                name="rollback_missing_world",
                violated_condition="rollback action missing",
                severity=5 if not req.has_rollback else 1,
                recoverable=req.has_rollback,
                mitigation="create rollback action before deployment",
            ),
            CounterfactualWorld(
                name="error_budget_exhausted_world",
                violated_condition="error budget is sufficient for canary exposure",
                severity=4 if req.expected_error_budget < 0.2 else 1,
                recoverable=req.expected_error_budget >= 0.2,
                mitigation="postpone deployment until error budget recovers",
            ),
        ]
        if req.contains_secret_change:
            worlds.append(
                CounterfactualWorld(
                    name="secret_rotation_world",
                    violated_condition="never deploy secret changes without security approval",
                    severity=4,
                    recoverable=True,
                    mitigation="require security auditor approval and staged secret rotation",
                )
            )
        return worlds

    def collect_approvals(
        self,
        contract: DeployContract,
        worlds: tuple[CounterfactualWorld, ...],
    ) -> list[Approval]:
        req = contract.request
        severe_unrecoverable = [
            world for world in worlds if world.severity >= 4 and not world.recoverable
        ]
        secret_world_exists = any(world.name == "secret_rotation_world" for world in worlds)
        return [
            Approval(
                role=Role.RELEASE_MANAGER,
                accepted=req.has_tests and req.expected_error_budget >= 0.2,
                reason="release has test evidence and enough error budget"
                if req.has_tests and req.expected_error_budget >= 0.2
                else "release lacks test evidence or error budget",
            ),
            Approval(
                role=Role.SRE_GUARDIAN,
                accepted=not severe_unrecoverable,
                reason="no severe unrecoverable failure world remains"
                if not severe_unrecoverable
                else "severe unrecoverable failure world detected",
            ),
            Approval(
                role=Role.SECURITY_AUDITOR,
                accepted=not secret_world_exists,
                reason="no secret-sensitive deployment path"
                if not secret_world_exists
                else "secret change needs explicit security workflow",
            ),
            Approval(
                role=Role.ROLLBACK_ENGINEER,
                accepted=bool(contract.rollback_actions) and req.migration_reversible,
                reason="rollback protocol and reversible migration exist"
                if contract.rollback_actions and req.migration_reversible
                else "rollback protocol or migration reversibility is insufficient",
            ),
        ]

    def is_committed(self, approvals: tuple[Approval, ...]) -> bool:
        return sum(approval.accepted for approval in approvals) >= self.APPROVAL_THRESHOLD

    def execute_contract(self, contract: DeployContract) -> list[str]:
        req = contract.request
        return [
            f"preflight: verify tests for {req.service}:{req.version}",
            "create deployment checkpoint",
            "deploy canary to 5 percent traffic",
            "monitor SLO metrics for canary window",
            "promote to 100 percent only if invariants hold",
            "write commit ledger with rollback actions",
        ]

