import unittest
from bs4 import BeautifulSoup
from scraper.parser_utils import safe_int, safe_float, clean_text, categorize_ball_event
from scraper.selectors import find_first_matching


class TestParserUtils(unittest.TestCase):
    def test_safe_int(self):
        self.assertEqual(safe_int("45"), 45)
        self.assertEqual(safe_int("187 runs"), 187)
        self.assertIsNone(safe_int(None))
        self.assertIsNone(safe_int("N/A"))

    def test_safe_float(self):
        self.assertEqual(safe_float("18.3"), 18.3)
        self.assertEqual(safe_float("100.00%"), 100.0)
        self.assertIsNone(safe_float(None))
        self.assertIsNone(safe_float("abc"))

    def test_clean_text(self):
        self.assertEqual(
            clean_text("  India   vs Sri Lanka  View match performance"),
            "India vs Sri Lanka"
        )
        self.assertIsNone(clean_text(None))

    def test_extract_teams_from_title(self):
        from scraper.parser_utils import extract_teams_from_title
        self.assertEqual(
            extract_teams_from_title("India vs Sri Lanka, 2nd Test"),
            ["India", "Sri Lanka"]
        )
        self.assertEqual(
            extract_teams_from_title("IDream Tiruppur Tamizhans vs Vida Kovai Kings, Eliminator"),
            ["IDream Tiruppur Tamizhans", "Vida Kovai Kings"]
        )

    def test_categorize_ball_event(self):
        self.assertEqual(
            categorize_ball_event("18.3 Player A to Player B, 4 runs, boundary through covers", "FOUR"),
            "FOUR"
        )
        self.assertEqual(
            categorize_ball_event("18.4 Player A to Player B, OUT, caught at mid-off", "WICKET"),
            "WICKET"
        )
        self.assertEqual(
            categorize_ball_event("18.1 Player A to Player B, 1 run to deep mid-wicket"),
            "SINGLE"
        )
        self.assertEqual(
            categorize_ball_event("18.2 Player A to Player B, no run"),
            "DOT"
        )
        self.assertEqual(
            categorize_ball_event("18.5 Player A to Player B, 6 runs, high over long-on"),
            "SIX"
        )
        self.assertEqual(
            categorize_ball_event("18.6 Player A to Player B, 1 wide"),
            "WIDE"
        )

    def test_selectors_fallback(self):
        html_doc = """
        <div>
            <a href="/live-cricket-scores/163017/ind-vs-sl">Match Link</a>
            <div class="scorecard-bat-grid">Grid content</div>
        </div>
        """
        soup = BeautifulSoup(html_doc, "lxml")
        live_match = find_first_matching(soup, "live_matches")
        self.assertIsNotNone(live_match)
        self.assertIn("/live-cricket-scores/163017", live_match["href"])


if __name__ == "__main__":
    unittest.main()
