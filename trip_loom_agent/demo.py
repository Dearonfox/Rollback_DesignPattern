from __future__ import annotations

import argparse

from .core import RouteLoomAgent, TravelRequest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run TripLoom Agent with the Route Loom Pattern."
    )
    parser.add_argument("--city", default="Jeonju")
    parser.add_argument("--start-hour", type=int, default=10)
    parser.add_argument("--end-hour", type=int, default=19)
    parser.add_argument("--pace", choices=["relaxed", "packed"], default="relaxed")
    parser.add_argument("--rainy", action="store_true")
    args = parser.parse_args()

    request = TravelRequest(
        city=args.city,
        start_hour=args.start_hour,
        end_hour=args.end_hour,
        pace=args.pace,
        rainy=args.rainy,
    )
    itinerary = RouteLoomAgent().build_itinerary(request)
    print(itinerary.explain())


if __name__ == "__main__":
    main()

