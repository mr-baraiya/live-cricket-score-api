import unittest
from services.cricket_math import (
    overs_to_balls,
    balls_to_overs_display,
    calculate_run_rate,
)
from scraper.normalizer import normalize_status, MatchStatusEnum, is_live_status, is_upcoming_status
from scraper.parser_utils import (
    extract_teams_from_title,
    clean_team_name,
    deduplicate_repeated_text,
)


class TestCricketMathAndNormalizer(unittest.TestCase):
    def test_overs_to_balls(self):
        self.assertEqual(overs_to_balls("17.4"), 106)
        self.assertEqual(overs_to_balls(17.4), 106)
        self.assertEqual(overs_to_balls(20), 120)
        self.assertEqual(overs_to_balls("0.0"), 0)
        self.assertIsNone(overs_to_balls(None))

    def test_balls_to_overs_display(self):
        self.assertEqual(balls_to_overs_display(106), 17.4)
        self.assertEqual(balls_to_overs_display(120), 20.0)
        self.assertEqual(balls_to_overs_display(0), 0.0)
        self.assertIsNone(balls_to_overs_display(None))

    def test_calculate_run_rate(self):
        # 80 runs in 17.4 overs (106 balls = 17.666 overs) -> 80 / (106/6) = 4.53
        self.assertEqual(calculate_run_rate(80, "17.4"), 4.53)
        self.assertIsNone(calculate_run_rate(None, "17.4"))
        self.assertIsNone(calculate_run_rate(50, None))

    def test_normalize_status(self):
        status, text = normalize_status("Stumps")
        self.assertEqual(status, MatchStatusEnum.COMPLETED)

        status, text = normalize_status("India won by 6 wickets")
        self.assertEqual(status, MatchStatusEnum.COMPLETED)

        status, text = normalize_status("Delayed due to rain")
        self.assertEqual(status, MatchStatusEnum.DELAYED)

        status, text = normalize_status("In Progress")
        self.assertEqual(status, MatchStatusEnum.LIVE)
        self.assertTrue(is_live_status(status))

        status, text = normalize_status("Match 10, Preview")
        self.assertEqual(status, MatchStatusEnum.UPCOMING)
        self.assertTrue(is_upcoming_status(status))

    def test_team_extraction(self):
        teams1 = extract_teams_from_title("IND vs SL - Stumps")
        self.assertEqual(teams1, ["IND", "SL"])

        teams2 = extract_teams_from_title("NEZONE vs EZONE - EZONE won")
        self.assertEqual(teams2, ["NEZONE", "EZONE"])

    def test_clean_team_name(self):
        self.assertEqual(clean_team_name("SL - Stumps"), "SL")
        self.assertEqual(clean_team_name("NEZONE - EZONE won"), "NEZONE")

    def test_deduplicate_repeated_text(self):
        self.assertEqual(
            deduplicate_repeated_text("England England Pakistan Pakistan"),
            "England Pakistan"
        )


if __name__ == "__main__":
    unittest.main()
