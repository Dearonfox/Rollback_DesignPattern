from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Role(str, Enum):
    PROPOSER = "proposer"
    SKEPTIC = "skeptic"
    VERIFIER = "verifier"
    RECOVERY_PLANNER = "recovery_planner"


@dataclass(frozen=True)
class Obligation:
    id: str
    description: str


@dataclass(frozen=True)
class Contract:
    obligation: Obligation
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


@dataclass(frozen=True)
class Approval:
    role: Role
    accepted: bool
    reason: str


@dataclass(frozen=True)
class LedgerEntry:
    contract: Contract
    counterfactuals: tuple[CounterfactualWorld, ...]
    approvals: tuple[Approval, ...]
    committed: bool

    def explain(self) -> str:
        status = "COMMITTED" if self.committed else "REJECTED"
        lines = [
            f"Status: {status}",
            f"Obligation: {self.contract.obligation.description}",
            f"Action: {self.contract.action}",
            "Preconditions:",
            *[f"- {item}" for item in self.contract.preconditions],
            "Invariants:",
            *[f"- {item}" for item in self.contract.invariants],
            "Counterfactual worlds:",
            *[
                f"- {world.name}: severity={world.severity}, "
                f"recoverable={world.recoverable}, violated={world.violated_condition}"
                for world in self.counterfactuals
            ],
            "Approvals:",
            *[
                f"- {approval.role.value}: {approval.accepted} ({approval.reason})"
                for approval in self.approvals
            ],
            "Rollback protocol:",
            *[f"- {item}" for item in self.contract.rollback_actions],
        ]
        return "\n".join(lines)


class CounterfactualContractMesh:
    """Reference implementation of the Counterfactual Contract Mesh pattern.

    CCM treats an agent action as a contract that must survive counterfactual
    failure simulation and role-based approval before it can be committed.
    """

    def build_ledger(self, goal: str) -> tuple[LedgerEntry, ...]:
        obligations = self.decompose_goal(goal)
        return tuple(self.negotiate(self.propose_contract(item)) for item in obligations)

    def decompose_goal(self, goal: str) -> list[Obligation]:
        cleaned = goal.strip()
        if not cleaned:
            raise ValueError("goal must not be empty")

        separators = [",", ";", " and ", " then "]
        segments = [cleaned]
        for separator in separators:
            next_segments: list[str] = []
            for segment in segments:
                next_segments.extend(part.strip() for part in segment.split(separator))
            segments = [segment for segment in next_segments if segment]

        if len(segments) == 1:
            segments.append(f"verify result for {cleaned}")

        return [
            Obligation(id=f"obl-{index}", description=segment)
            for index, segment in enumerate(segments, start=1)
        ]

    def propose_contract(self, obligation: Obligation) -> Contract:
        return Contract(
            obligation=obligation,
            action=f"execute obligation: {obligation.description}",
            preconditions=(
                "goal is explicit",
                "required context has been collected",
                "user-visible impact is understood",
            ),
            postconditions=(
                "result addresses the obligation",
                "result can be inspected by the user",
            ),
            invariants=(
                "do not hide uncertainty",
                "do not perform irreversible operations without approval",
                "preserve user-provided constraints",
            ),
            forbidden_states=(
                "silent irreversible side effect",
                "unverified factual claim presented as certain",
                "missing rollback path",
            ),
            rollback_actions=(
                "record the failed assumption",
                "restore the previous safe state when possible",
                "ask for approval if recovery changes external state",
            ),
        )

    def negotiate(self, contract: Contract) -> LedgerEntry:
        worlds = self.simulate_counterfactuals(contract)
        approvals = (
            self.proposer_vote(contract),
            self.skeptic_vote(contract, worlds),
            self.verifier_vote(contract),
            self.recovery_vote(contract, worlds),
        )
        committed = sum(approval.accepted for approval in approvals) >= 3
        return LedgerEntry(
            contract=contract,
            counterfactuals=tuple(worlds),
            approvals=approvals,
            committed=committed,
        )

    def simulate_counterfactuals(
        self, contract: Contract
    ) -> list[CounterfactualWorld]:
        worlds = [
            CounterfactualWorld(
                name="missing_context_world",
                violated_condition="required context has been collected",
                severity=2,
                recoverable=True,
            ),
            CounterfactualWorld(
                name="overconfident_answer_world",
                violated_condition="do not hide uncertainty",
                severity=3,
                recoverable=True,
            ),
        ]

        if not contract.rollback_actions:
            worlds.append(
                CounterfactualWorld(
                    name="irreversible_failure_world",
                    violated_condition="missing rollback path",
                    severity=5,
                    recoverable=False,
                )
            )

        return worlds

    def proposer_vote(self, contract: Contract) -> Approval:
        accepted = bool(contract.action and contract.postconditions)
        return Approval(
            role=Role.PROPOSER,
            accepted=accepted,
            reason="contract has an executable action and target postconditions",
        )

    def skeptic_vote(
        self, contract: Contract, worlds: Iterable[CounterfactualWorld]
    ) -> Approval:
        severe_unrecoverable = [
            world for world in worlds if world.severity >= 4 and not world.recoverable
        ]
        accepted = not severe_unrecoverable and bool(contract.forbidden_states)
        reason = (
            "no severe unrecoverable counterfactual survived"
            if accepted
            else "severe unrecoverable counterfactual detected"
        )
        return Approval(role=Role.SKEPTIC, accepted=accepted, reason=reason)

    def verifier_vote(self, contract: Contract) -> Approval:
        accepted = bool(contract.preconditions and contract.invariants)
        return Approval(
            role=Role.VERIFIER,
            accepted=accepted,
            reason="preconditions and invariants are explicit",
        )

    def recovery_vote(
        self, contract: Contract, worlds: Iterable[CounterfactualWorld]
    ) -> Approval:
        has_recovery = bool(contract.rollback_actions)
        unrecoverable = any(not world.recoverable for world in worlds)
        accepted = has_recovery and not unrecoverable
        reason = (
            "rollback protocol covers simulated failures"
            if accepted
            else "rollback protocol is missing or insufficient"
        )
        return Approval(
            role=Role.RECOVERY_PLANNER,
            accepted=accepted,
            reason=reason,
        )

