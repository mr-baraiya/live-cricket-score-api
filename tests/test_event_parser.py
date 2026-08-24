import unittest
from scraper.event_parser import EventParser


class TestEventParser(unittest.TestCase):
    def test_five_runs_delivery(self):
        text = "2.5 Manav Suthar to Kamil Mishara, 5 runs, nice and slow, turns in and Mishara works it towards mid-wicket. Jaiswal swoops down and shies at the striker's end. It is a poor throw and no one is backing up. The ball races away for four extra runs.."
        event, runs, dismissal = EventParser.parse_delivery_event(text)
        self.assertEqual(event, "FIVE")
        self.assertEqual(runs, 5)
        self.assertIsNone(dismissal["dismissal_type"])

    def test_false_lbw_appeal_not_wicket(self):
        text = "2.3 Manav Suthar to Prabath Jayasuriya, no run, loud appeal for LBW. Suthar and everyone close to Jayasuriya were interested. Gill has a word and decides against the review. This is the arm-ball, skids on and pings Jayasuriya on the back pad. He was beaten for pace. The impact was on leg-stump and ball-tracking shows it to be clipping leg-stump, umpire's call"
        event, runs, dismissal = EventParser.parse_delivery_event(text)
        self.assertNotEqual(event, "WICKET")
        self.assertEqual(event, "DOT")
        self.assertEqual(runs, 0)

    def test_real_wicket_dismissal(self):
        text = "2.2 Manav Suthar to Prabath Jayasuriya, OUT, c Jaiswal b Manav Suthar, Prabath Jayasuriya caught at silly point for 1 run!"
        event, runs, dismissal = EventParser.parse_delivery_event(text, "OUT")
        self.assertEqual(event, "WICKET")
        self.assertEqual(dismissal["dismissal_type"], "caught")
        self.assertEqual(dismissal["fielder"], "Jaiswal")

    def test_stable_event_id(self):
        id1 = EventParser.generate_event_id("163017", 1, 2, 5, "2.5 Manav Suthar to Kamil Mishara, 5 runs")
        id2 = EventParser.generate_event_id("163017", 1, 2, 5, "2.5 Manav Suthar to Kamil Mishara, 5 runs")
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("163017-1-2.5-"))


if __name__ == "__main__":
    unittest.main()
