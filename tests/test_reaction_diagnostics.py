"""Tests for bounded, read-only reaction diagnostics."""
import os
import tempfile
import unittest
from pathlib import Path

from reaction_diagnostics import build_reaction_report, save_reaction_report


class Action:
    def __init__(self):
        self.calls = 0

    def get_n_actions(self):
        return 1

    def get_name(self, index):
        return "click"

    def do_action(self, index):
        self.calls += 1
        return True


class Node:
    def __init__(self, name="", children=(), action=None):
        self.name, self.children, self.action = name, list(children), action
        self.parent = None

    def get_name(self):
        return self.name

    def get_role_name(self):
        return "push button"

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def get_parent(self):
        return self.parent

    def query_action(self):
        return self.action


class ReactionDiagnosticsTests(unittest.TestCase):
    def test_reports_actions_without_triggering_them(self):
        action = Action()
        node = Node("Reaction: 👍", action=action)
        report = build_reaction_report(node)
        self.assertIn("reaction_candidate: True", report)
        self.assertIn("Thumbs up", report)
        self.assertIn("click", report)
        self.assertEqual(action.calls, 0)

    def test_ancestor_siblings_are_not_scanned(self):
        focused = Node("Focused")
        sibling = Node("PRIVATE SIBLING")
        parent = Node("Parent", [focused, sibling])
        focused.parent = parent
        report = build_reaction_report(focused)
        self.assertIn("Parent", report)
        self.assertNotIn("PRIVATE SIBLING", report)

    def test_report_saved_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reaction-report.txt"
            self.assertEqual(save_reaction_report(Node("Reaction: ❤️"), path), path)
            self.assertIn("Heart", path.read_text(encoding="utf-8"))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_missing_focus(self):
        with self.assertRaises(ValueError):
            build_reaction_report(None)


if __name__ == "__main__":
    unittest.main()
