"""Unit tests for passive reaction AT-SPI interface diagnostics."""
import os
import tempfile
import unittest
from pathlib import Path

from reaction_interfaces import build_reaction_interface_report, save_reaction_interface_report


class Component:
    def get_extents(self, coordinate_type):
        return (10, 20, 30, 40)


class Action:
    def __init__(self):
        self.invoked = False

    def get_n_actions(self):
        return 1

    def get_name(self, index):
        return "click"

    def do_action(self, index):
        self.invoked = True


class Node:
    def __init__(self, role, name, children=(), component=None, action=None):
        self.role, self.name = role, name
        self.children = list(children)
        self.component, self.action = component, action
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

    def query_component(self):
        return self.component

    def query_action(self):
        return self.action


class InterfaceReportTests(unittest.TestCase):
    def test_reports_geometry_without_actions(self):
        action = Action()
        reaction = Node("table cell", "Реакции", component=Component(), action=action)
        message = Node("list item", "Message", [reaction])
        report = build_reaction_interface_report(message)
        self.assertIn("Реакции", report)
        self.assertIn("screen=(10, 20, 30, 40)", report)
        self.assertIn("Selection=False", report)
        self.assertIn("click", report)
        self.assertFalse(action.invoked)

    def test_excludes_sibling_messages(self):
        focused = Node("list item", "Current")
        sibling = Node("list item", "PRIVATE SIBLING")
        Node("list", "Messages", [focused, sibling])
        report = build_reaction_interface_report(focused)
        self.assertNotIn("PRIVATE SIBLING", report)

    def test_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "interfaces.txt"
            save_reaction_interface_report(Node("list item", "Message"), path)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_missing_focus(self):
        with self.assertRaises(ValueError):
            build_reaction_interface_report(None)


if __name__ == "__main__":
    unittest.main()
