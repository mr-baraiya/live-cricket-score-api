import unittest
from services.change_detector import ChangeDetector
from models.commentary import CommentaryItem


class TestChangeDetector(unittest.TestCase):
    def test_deduplication_and_change_detection(self):
        cd = ChangeDetector()

        # Poll 1: Initial delivery 2.5 FIVE
        item1 = CommentaryItem(
            event_id="163017-1-2.5-abc123",
            over=2,
            ball=5,
            event="FIVE",
            runs=5,
            batsman="Kamil Mishara",
            bowler="Manav Suthar",
            text="2.5 Manav Suthar to Kamil Mishara, 5 runs"
        )
        res1 = cd.detect_changes("163017", {}, item1)
        self.assertFalse(res1.changed)  # Initial poll caches state

        # Poll 2: Repeated poll of same 2.5 FIVE delivery -> changed = False
        res2 = cd.detect_changes("163017", {}, item1)
        self.assertFalse(res2.changed)
        self.assertEqual(res2.details, ["No new delivery"])

        # Poll 3: New delivery 2.6 DOT -> changed = True
        item2 = CommentaryItem(
            event_id="163017-1-2.6-def456",
            over=2,
            ball=6,
            event="DOT",
            runs=0,
            batsman="Kamil Mishara",
            bowler="Manav Suthar",
            text="2.6 Manav Suthar to Kamil Mishara, no run"
        )
        res3 = cd.detect_changes("163017", {}, item2)
        self.assertTrue(res3.changed)
        self.assertEqual(res3.event, "DOT")
        self.assertEqual(res3.over, 2)
        self.assertEqual(res3.ball, 6)
        self.assertEqual(res3.event_id, "163017-1-2.6-def456")


if __name__ == "__main__":
    unittest.main()
