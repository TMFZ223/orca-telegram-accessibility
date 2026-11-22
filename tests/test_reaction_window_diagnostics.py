"""Tests for read-only active-window reaction diagnostics."""
import unittest

from reaction_diagnostics import build_window_reaction_report


class Node:
    def __init__(self, role, name="", children=()):
        self.role, self.name, self.children = role, name, list(children)
        self.parent = None
        for child in self.children:
            child.parent = self

    def get_role_name(self):
        return self.role

    def get_name(self):
        return self.name

    def get_parent(self):
        return self.parent

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]


class WindowReportTests(unittest.TestCase):
    def test_window_and_popup_are_reported(self):
        focused = Node("list item", "message")
        window = Node("frame", "Telegram", [focused])
        popup = Node("dialog", "Reactions", [Node("menu item", "Reaction: 👍")])
        Node("application", "Telegram", [window, popup])
        report = build_window_reaction_report(focused)
        self.assertIn("WINDOW containing_window", report)
        self.assertIn("WINDOW other_application_window", report)
        self.assertIn("Thumbs up", report)
        self.assertIn("popup_or_reaction_candidate=True", report)

    def test_non_window_application_sibling_excluded(self):
        focused = Node("list item", "message")
        window = Node("frame", "Telegram", [focused])
        other = Node("list", "unrelated application sibling")
        Node("application", "Telegram", [window, other])
        report = build_window_reaction_report(focused)
        self.assertNotIn("unrelated application sibling", report)

    def test_no_window_is_error(self):
        with self.assertRaises(ValueError):
            build_window_reaction_report(Node("list item", "message"))


if __name__ == "__main__":
    unittest.main()
