import unittest

from trip_loom_agent.core import RouteLoomAgent, TravelRequest


class RouteLoomAgentTest(unittest.TestCase):
    def test_builds_itinerary_without_remaining_tension_for_normal_day(self):
        request = TravelRequest(
            city="Jeonju",
            start_hour=10,
            end_hour=19,
            pace="relaxed",
            rainy=False,
        )

        itinerary = RouteLoomAgent().build_itinerary(request)

        self.assertGreaterEqual(len(itinerary.slots), 4)
        self.assertEqual(itinerary.tensions, ())
        self.assertIn("wove initial route", "\n".join(itinerary.trace))

    def test_reweaves_outdoor_slots_on_rainy_day(self):
        request = TravelRequest(
            city="Jeonju",
            start_hour=10,
            end_hour=19,
            pace="relaxed",
            rainy=True,
        )

        itinerary = RouteLoomAgent().build_itinerary(request)

        self.assertTrue(any("local reweave" in item for item in itinerary.trace))
        self.assertTrue(all(slot.place.indoor for slot in itinerary.slots))

    def test_invalid_time_window_is_rejected(self):
        request = TravelRequest(city="Jeonju", start_hour=12, end_hour=12)

        with self.assertRaises(ValueError):
            RouteLoomAgent().build_itinerary(request)


if __name__ == "__main__":
    unittest.main()

