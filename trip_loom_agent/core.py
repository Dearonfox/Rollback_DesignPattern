from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable


@dataclass(frozen=True)
class TravelRequest:
    city: str
    start_hour: int
    end_hour: int
    pace: str = "relaxed"
    interests: tuple[str, ...] = ("landmark", "food", "cafe")
    rainy: bool = False


@dataclass(frozen=True)
class Place:
    name: str
    category: str
    district: str
    duration_minutes: int
    open_hour: int
    close_hour: int
    indoor: bool
    fatigue: int
    score: float


@dataclass(frozen=True)
class Slot:
    start: int
    end: int
    place: Place
    note: str = ""


@dataclass(frozen=True)
class Tension:
    slot_index: int
    kind: str
    severity: int
    message: str


@dataclass(frozen=True)
class Itinerary:
    request: TravelRequest
    slots: tuple[Slot, ...]
    tensions: tuple[Tension, ...]
    trace: tuple[str, ...]

    def explain(self) -> str:
        lines = [
            f"TripLoom itinerary for {self.request.city}",
            f"pace={self.request.pace}, rainy={self.request.rainy}",
            "Schedule:",
        ]
        for slot in self.slots:
            lines.append(
                f"- {slot.start:02d}:00-{slot.end:02d}:00 "
                f"{slot.place.name} ({slot.place.category}, {slot.place.district})"
            )
            if slot.note:
                lines.append(f"  note: {slot.note}")
        lines.append("Remaining tensions:")
        if not self.tensions:
            lines.append("- none")
        else:
            lines.extend(
                f"- slot {tension.slot_index}: {tension.kind} "
                f"severity={tension.severity} {tension.message}"
                for tension in self.tensions
            )
        lines.append("Trace:")
        lines.extend(f"- {item}" for item in self.trace)
        return "\n".join(lines)


class RouteLoomAgent:
    """Reference implementation of the Route Loom Pattern.

    Route Loom does not simply rank places. It weaves places into a temporal
    route, checks constraint tension, and locally reweaves only the broken parts.
    """

    def build_itinerary(self, request: TravelRequest) -> Itinerary:
        self._validate_request(request)
        trace = [
            "extracted travel preferences",
            "created temporal skeleton",
            "generated candidate place pool",
        ]
        places = self.place_pool(request)
        slots = self.weave_route(request, places)
        trace.append("wove initial route into time slots")
        tensions = self.check_tension(request, slots)
        trace.append(f"detected {len(tensions)} initial tensions")
        if tensions:
            slots, reweave_trace = self.local_reweave(request, slots, tensions, places)
            trace.extend(reweave_trace)
            tensions = self.check_tension(request, slots)
            trace.append(f"detected {len(tensions)} tensions after local reweaving")
        return Itinerary(
            request=request,
            slots=tuple(slots),
            tensions=tuple(tensions),
            trace=tuple(trace),
        )

    def place_pool(self, request: TravelRequest) -> list[Place]:
        return [
            Place("Hanok Village", "landmark", "old-town", 90, 9, 21, False, 3, 9.5),
            Place("Gyeonggijeon Shrine", "history", "old-town", 60, 9, 18, False, 2, 8.8),
            Place("Jeonju Nanjang", "museum", "old-town", 70, 10, 19, True, 1, 8.6),
            Place("Local Bibimbap Lunch", "food", "old-town", 60, 11, 15, True, 1, 9.2),
            Place("Makgeolli Alley", "food", "west-town", 80, 17, 23, True, 2, 8.1),
            Place("Riverside Walk", "walk", "river", 70, 8, 20, False, 3, 7.9),
            Place("Quiet Hanok Cafe", "cafe", "old-town", 60, 10, 22, True, 1, 8.7),
            Place("Craft Market", "shopping", "old-town", 50, 11, 20, True, 1, 7.8),
            Place("Observation Pavilion", "view", "hill", 60, 10, 18, False, 4, 8.0),
            Place("Covered Culture Arcade", "shopping", "old-town", 90, 10, 21, True, 1, 8.2),
        ]

    def weave_route(self, request: TravelRequest, places: Iterable[Place]) -> list[Slot]:
        skeleton = self.temporal_skeleton(request)
        selected: list[Slot] = []
        used: set[str] = set()
        places_by_score = sorted(places, key=lambda place: place.score, reverse=True)

        for start, end, target_category in skeleton:
            candidate = self._best_place_for_slot(
                places_by_score,
                used,
                target_category,
                start,
                end,
                request,
            )
            if candidate is None:
                continue
            used.add(candidate.name)
            selected.append(Slot(start=start, end=end, place=candidate))
        return selected

    def temporal_skeleton(self, request: TravelRequest) -> list[tuple[int, int, str]]:
        if request.end_hour - request.start_hour < 4:
            return [
                (request.start_hour, request.start_hour + 1, "landmark"),
                (request.start_hour + 1, request.start_hour + 2, "cafe"),
                (request.start_hour + 2, request.end_hour, "food"),
            ]
        return [
            (request.start_hour, request.start_hour + 2, "landmark"),
            (request.start_hour + 2, request.start_hour + 3, "food"),
            (request.start_hour + 3, request.start_hour + 4, "history"),
            (request.start_hour + 4, request.start_hour + 5, "cafe"),
            (request.start_hour + 5, request.end_hour, "walk"),
        ]

    def check_tension(self, request: TravelRequest, slots: list[Slot]) -> list[Tension]:
        tensions: list[Tension] = []
        fatigue_limit = 12 if request.pace == "relaxed" else 15
        total_fatigue = 0
        previous_district = ""

        for index, slot in enumerate(slots):
            place = slot.place
            if slot.start < place.open_hour or slot.end > place.close_hour:
                tensions.append(
                    Tension(index, "opening_hours", 5, f"{place.name} is closed")
                )
            if request.rainy and not place.indoor:
                tensions.append(
                    Tension(index, "weather", 4, f"{place.name} is outdoor on rainy day")
                )
            if previous_district and previous_district != place.district:
                total_fatigue += 2
            total_fatigue += place.fatigue
            if total_fatigue > fatigue_limit:
                tensions.append(
                    Tension(index, "fatigue", 3, "route exceeds fatigue budget")
                )
            if slot.start in {12, 18} and place.category not in {"food", "cafe"}:
                tensions.append(
                    Tension(index, "meal_rhythm", 2, "meal-time slot lacks food or cafe")
                )
            previous_district = place.district
        return tensions

    def local_reweave(
        self,
        request: TravelRequest,
        slots: list[Slot],
        tensions: list[Tension],
        places: list[Place],
    ) -> tuple[list[Slot], list[str]]:
        trace: list[str] = []
        repaired = list(slots)
        used = {slot.place.name for slot in repaired}

        for tension in sorted(tensions, key=lambda item: item.severity, reverse=True):
            slot = repaired[tension.slot_index]
            replacement = self._replacement_for_tension(
                request=request,
                places=places,
                used=used - {slot.place.name},
                slot=slot,
                tension=tension,
            )
            if replacement and replacement.name != slot.place.name:
                repaired[tension.slot_index] = replace(
                    slot,
                    place=replacement,
                    note=f"locally rewoven because of {tension.kind}",
                )
                used.discard(slot.place.name)
                used.add(replacement.name)
                trace.append(
                    f"local reweave: replaced {slot.place.name} with "
                    f"{replacement.name} for {tension.kind}"
                )
        return repaired, trace

    def _replacement_for_tension(
        self,
        request: TravelRequest,
        places: list[Place],
        used: set[str],
        slot: Slot,
        tension: Tension,
    ) -> Place | None:
        candidates = [place for place in places if place.name not in used]
        candidates = [
            place
            for place in candidates
            if slot.start >= place.open_hour and slot.end <= place.close_hour
        ]
        if tension.kind == "weather":
            candidates = [place for place in candidates if place.indoor]
        if tension.kind == "meal_rhythm":
            candidates = [place for place in candidates if place.category in {"food", "cafe"}]
        if tension.kind == "fatigue":
            candidates = [
                place
                for place in candidates
                if place.fatigue <= 1 and place.district == slot.place.district
            ]
        if not candidates:
            return None
        if request.rainy:
            candidates.sort(key=lambda place: (not place.indoor, -place.score))
        else:
            candidates.sort(key=lambda place: -place.score)
        return candidates[0]

    def _best_place_for_slot(
        self,
        places: list[Place],
        used: set[str],
        target_category: str,
        start: int,
        end: int,
        request: TravelRequest,
    ) -> Place | None:
        preferred = [
            place
            for place in places
            if place.name not in used
            and place.category == target_category
            and start >= place.open_hour
            and end <= place.close_hour
        ]
        if not preferred and target_category == "landmark":
            preferred = [
                place
                for place in places
                if place.name not in used
                and place.category in {"landmark", "history", "museum"}
                and start >= place.open_hour
                and end <= place.close_hour
            ]
        if not preferred:
            preferred = [place for place in places if place.name not in used]
        if request.rainy:
            preferred.sort(key=lambda place: (not place.indoor, -place.score))
        else:
            preferred.sort(key=lambda place: -place.score)
        return preferred[0] if preferred else None

    def _validate_request(self, request: TravelRequest) -> None:
        if request.start_hour >= request.end_hour:
            raise ValueError("start_hour must be earlier than end_hour")
        if request.end_hour - request.start_hour < 3:
            raise ValueError("travel window must be at least 3 hours")
