"""Regression tests for dialogue validator entry-point and reachability rules."""

import json
import tempfile
import unittest
from pathlib import Path

from validate_dialogue import validate_file


ROOT = Path(__file__).resolve().parents[1]
ENDING_GRAPH = ROOT / "data" / "dialogue" / "endings.json"


class DialogueValidatorEntryPointTests(unittest.TestCase):
    def _validate_temp_graph(self, filename: str, graph: dict):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / filename
        path.write_text(json.dumps(graph), encoding="utf-8")
        return validate_file(path)

    def test_actual_endings_graph_has_no_false_unreachable_warning(self) -> None:
        errors, warnings = validate_file(ENDING_GRAPH)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_next_target_is_still_an_error(self) -> None:
        graph = {
            "logbook": {"speaker": "", "text": "Believer is a story word.", "next": "missing_node"},
            "radio": {"speaker": "", "text": "Radio", "next": None},
            "door": {"speaker": "", "text": "Door", "next": None},
        }

        errors, _warnings = self._validate_temp_graph("keeper_intro.json", graph)
        self.assertTrue(any("'next' points to missing node 'missing_node'" in e for e in errors))

    def test_missing_choice_target_is_still_an_error(self) -> None:
        graph = {
            "logbook": {
                "speaker": "",
                "text": "The text mentions skeptic but does not define a flag.",
                "choices": [{"text": "Choose", "next": "missing_choice_target"}],
            },
            "radio": {"speaker": "", "text": "Radio", "next": None},
            "door": {"speaker": "", "text": "Door", "next": None},
        }

        errors, _warnings = self._validate_temp_graph("keeper_intro.json", graph)
        self.assertTrue(any("'next' -> missing node 'missing_choice_target'" in e for e in errors))

    def test_genuinely_unreachable_node_is_still_warned(self) -> None:
        graph = {
            "logbook": {"speaker": "", "text": "Logbook", "next": None},
            "radio": {"speaker": "", "text": "Radio", "next": None},
            "door": {"speaker": "", "text": "Door", "next": None},
            "orphan_node": {"speaker": "", "text": "Unconnected node", "next": None},
        }

        errors, warnings = self._validate_temp_graph("keeper_intro.json", graph)
        self.assertEqual(errors, [])
        self.assertTrue(any("orphan_node: unreachable from entry points" in w for w in warnings))

    def test_missing_configured_entry_is_reported(self) -> None:
        graph = {
            "logbook": {"speaker": "", "text": "Logbook", "next": None},
        }

        errors, warnings = self._validate_temp_graph("keeper_intro.json", graph)
        self.assertEqual(errors, [])
        self.assertTrue(any("missing configured entry point(s)" in w for w in warnings))
        self.assertFalse(any("no configured entry point present" in w for w in warnings))

    def test_endings_does_not_treat_generic_start_as_its_entry(self) -> None:
        graph = {
            "start": {"speaker": "", "text": "Wrong default entry for endings", "next": None},
        }

        errors, warnings = self._validate_temp_graph("endings.json", graph)
        self.assertEqual(errors, [])
        self.assertTrue(any("missing configured entry point(s)" in w for w in warnings))
        self.assertTrue(any("no configured entry point present" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
