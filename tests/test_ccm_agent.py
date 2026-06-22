import unittest

from ccm_agent.core import (
    Contract,
    CounterfactualContractMesh,
    Obligation,
    Role,
)


class CounterfactualContractMeshTest(unittest.TestCase):
    def test_commits_contracts_with_recovery_protocol(self):
        mesh = CounterfactualContractMesh()
        ledger = mesh.build_ledger("analyze interviews, produce product improvements")

        self.assertEqual(len(ledger), 2)
        self.assertTrue(all(entry.committed for entry in ledger))
        self.assertTrue(
            all(entry.contract.rollback_actions for entry in ledger)
        )

    def test_rejects_contract_without_rollback(self):
        mesh = CounterfactualContractMesh()
        contract = Contract(
            obligation=Obligation(id="obl-x", description="publish external update"),
            action="publish external update",
            preconditions=("goal is explicit",),
            postconditions=("update is visible",),
            invariants=("do not perform irreversible operations without approval",),
            forbidden_states=("missing rollback path",),
            rollback_actions=(),
        )

        entry = mesh.negotiate(contract)

        self.assertFalse(entry.committed)
        recovery_approval = [
            approval for approval in entry.approvals
            if approval.role is Role.RECOVERY_PLANNER
        ][0]
        self.assertFalse(recovery_approval.accepted)

    def test_explanation_contains_counterfactuals_and_approvals(self):
        mesh = CounterfactualContractMesh()
        entry = mesh.build_ledger("summarize research notes")[0]
        explanation = entry.explain()

        self.assertIn("Counterfactual worlds", explanation)
        self.assertIn("Approvals", explanation)
        self.assertIn("Rollback protocol", explanation)

    def test_empty_goal_is_invalid(self):
        mesh = CounterfactualContractMesh()

        with self.assertRaises(ValueError):
            mesh.build_ledger("   ")


if __name__ == "__main__":
    unittest.main()

