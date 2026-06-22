import unittest

from safe_deploy_agent.core import DeployRequest, Role, SafeDeployAgent


class SafeDeployAgentTest(unittest.TestCase):
    def test_commits_safe_canary_deployment(self):
        request = DeployRequest(
            service="payment-api",
            version="v2.4.1",
            environment="production",
            has_tests=True,
            has_rollback=True,
            migration_reversible=True,
            expected_error_budget=0.35,
        )

        ledger = SafeDeployAgent().run(request)

        self.assertTrue(ledger.committed)
        self.assertIn("deploy canary", "\n".join(ledger.execution_steps))
        self.assertTrue(all(approval.accepted for approval in ledger.approvals))

    def test_rejects_deployment_without_rollback(self):
        request = DeployRequest(
            service="payment-api",
            version="v2.4.2",
            environment="production",
            has_tests=True,
            has_rollback=False,
            migration_reversible=True,
            expected_error_budget=0.35,
        )

        ledger = SafeDeployAgent().run(request)

        self.assertFalse(ledger.committed)
        self.assertIn("deployment blocked", ledger.execution_steps[0])
        rollback_vote = [
            approval for approval in ledger.approvals
            if approval.role is Role.ROLLBACK_ENGINEER
        ][0]
        self.assertFalse(rollback_vote.accepted)

    def test_rejects_irreversible_migration(self):
        request = DeployRequest(
            service="billing-worker",
            version="v9.0.0",
            environment="production",
            has_tests=True,
            has_rollback=True,
            migration_reversible=False,
            expected_error_budget=0.5,
        )

        ledger = SafeDeployAgent().run(request)

        self.assertFalse(ledger.committed)
        self.assertIn("irreversible_migration_world", ledger.explain())

    def test_secret_change_requires_security_workflow(self):
        request = DeployRequest(
            service="auth-api",
            version="v1.8.0",
            environment="production",
            has_tests=True,
            has_rollback=True,
            migration_reversible=True,
            expected_error_budget=0.4,
            contains_secret_change=True,
        )

        ledger = SafeDeployAgent().run(request)

        self.assertTrue(any(world.name == "secret_rotation_world" for world in ledger.worlds))
        security_vote = [
            approval for approval in ledger.approvals
            if approval.role is Role.SECURITY_AUDITOR
        ][0]
        self.assertFalse(security_vote.accepted)


if __name__ == "__main__":
    unittest.main()

