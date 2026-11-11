"""Regression tests for repeatable belief choices in keeper_intro.json.

The dialogue manager applies a choice's set_flag dictionary as independent
GameState key/value assignments. Updating both belief keys in each choice
therefore makes the belief axis exclusive across repeated readings.
"""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "dialogue" / "keeper_intro.json"


def apply_choice_flags(flags: dict, choice: dict) -> None:
    """Mirror DialogueManager._apply_flags / GameState.set_flag semantics."""
    flags.update(choice.get("set_flag", {}))


class KeeperIntroBeliefFlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        cls.belief_choices = cls.graph["logbook_choice1"]["choices"]
        cls.trust_choices = cls.graph["logbook_choice2"]["choices"]

    def test_belief_choices_explicitly_set_both_flags(self) -> None:
        skeptic, believer = self.belief_choices

        self.assertEqual(
            skeptic["set_flag"],
            {"skeptic": True, "believer": False},
        )
        self.assertEqual(
            believer["set_flag"],
            {"believer": True, "skeptic": False},
        )

    def test_re_reading_never_leaves_both_belief_flags_true(self) -> None:
        flags = {"trusted_edith": True, "radioed_tom": True}
        sequence = [
            (self.belief_choices[1], True, False),   # believer
            (self.belief_choices[0], False, True),   # skeptic
            (self.belief_choices[1], True, False),   # believer again
            (self.belief_choices[0], False, True),   # skeptic again
        ]

        for choice, expected_believer, expected_skeptic in sequence:
            apply_choice_flags(flags, choice)
            self.assertIs(flags["believer"], expected_believer)
            self.assertIs(flags["skeptic"], expected_skeptic)
            self.assertFalse(flags["believer"] and flags["skeptic"])

        self.assertIs(flags["trusted_edith"], True)
        self.assertIs(flags["radioed_tom"], True)

    def test_trusted_edith_choices_remain_independent(self) -> None:
        for choice, expected_trust in (
            (self.trust_choices[0], True),
            (self.trust_choices[1], False),
        ):
            self.assertEqual(set(choice["set_flag"]), {"trusted_edith"})

            flags = {"believer": True, "skeptic": False}
            apply_choice_flags(flags, choice)

            self.assertIs(flags["trusted_edith"], expected_trust)
            self.assertIs(flags["believer"], True)
            self.assertIs(flags["skeptic"], False)


if __name__ == "__main__":
    unittest.main()
