from __future__ import annotations

import argparse

from .core import DeployRequest, SafeDeployAgent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SafeDeploy Agent with the Counterfactual Contract Mesh pattern."
    )
    parser.add_argument("--service", default="payment-api")
    parser.add_argument("--version", default="v2.4.1")
    parser.add_argument("--environment", default="production")
    parser.add_argument("--tests", action="store_true", help="Mark tests as passed")
    parser.add_argument("--rollback", action="store_true", help="Mark rollback as available")
    parser.add_argument(
        "--reversible-migration",
        action="store_true",
        help="Mark database migration as reversible",
    )
    parser.add_argument("--error-budget", type=float, default=0.35)
    parser.add_argument("--secret-change", action="store_true")
    args = parser.parse_args()

    request = DeployRequest(
        service=args.service,
        version=args.version,
        environment=args.environment,
        has_tests=args.tests,
        has_rollback=args.rollback,
        migration_reversible=args.reversible_migration,
        expected_error_budget=args.error_budget,
        contains_secret_change=args.secret_change,
    )
    ledger = SafeDeployAgent().run(request)
    print(ledger.explain())


if __name__ == "__main__":
    main()

