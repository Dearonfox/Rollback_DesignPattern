from __future__ import annotations

import argparse
import json

from .core import demo_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Rollback-First Agent demo.")
    parser.add_argument(
        "message",
        nargs="?",
        default="내일 오후 3시에 운영체제 공부 일정 추가해줘",
    )
    parser.add_argument("--rollback", type=int, help="Rollback an executed action id")
    args = parser.parse_args()

    agent = demo_agent()
    if args.rollback:
        result = agent.rollback(args.rollback)
    else:
        result = agent.run(args.message)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

