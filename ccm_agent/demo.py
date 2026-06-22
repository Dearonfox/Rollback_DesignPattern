from __future__ import annotations

import argparse

from .core import CounterfactualContractMesh


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Counterfactual Contract Mesh pattern demo."
    )
    parser.add_argument("goal", help="User goal to convert into contract ledger entries")
    args = parser.parse_args()

    mesh = CounterfactualContractMesh()
    ledger = mesh.build_ledger(args.goal)
    for index, entry in enumerate(ledger, start=1):
        print(f"=== Ledger Entry {index} ===")
        print(entry.explain())
        if index != len(ledger):
            print()


if __name__ == "__main__":
    main()

