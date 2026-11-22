"""Unit tests for safe reaction discovery without a live Telegram instance."""
import unittest

from reactions import collect_reactions, activate_reaction, _reaction_label


class FakeAction:
    def __init__(self, name="click", outcome=True):
        self.name, self.outcome, self.calls = name, outcome, []

    def get_n_actions(self):
        return 1

    def get_name(self, index):
        return self.name

    def do_action(self, index):
        self.calls.append(index)
        return self.outcome


class FakeAccessible:
    def __init__(self, name="", children=(), action=None):
        self.name, self.children, self.action = name, list(children), action

    def get_name(self):
        return self.name

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def query_action(self):
        return self.action


class ReactionTests(unittest.TestCase):
    def test_named_reactions_and_spoken_emoji(self):
        self.assertEqual(_reaction_label("👍"), "Thumbs up")
        self.assertEqual(_reaction_label("Reaction: ❤️"), "Heart")
        self.assertEqual(_reaction_label("React with 😂"), "Laugh")

    def test_only_explicit_actionable_reactions(self):
        clickable = FakeAccessible("Reaction: 👍", action=FakeAction())
        nonactionable = FakeAccessible("Reaction: ❤️")
        ordinary = FakeAccessible("Delete message", action=FakeAction())
        self.assertEqual(
            [(name, index) for name, _, index in collect_reactions(
                FakeAccessible(children=[clickable, nonactionable, ordinary]))],
            [("Thumbs up", 0)],
        )

    def test_no_reactions_no_activation(self):
        self.assertEqual(collect_reactions(None), [])
        self.assertEqual(collect_reactions(FakeAccessible("Hello")), [])

    def test_activation_only_on_request(self):
        action = FakeAction()
        control = FakeAccessible("React with 😂", action=action)
        items = collect_reactions(control)
        self.assertEqual(action.calls, [])
        self.assertTrue(activate_reaction(items[0]))
        self.assertEqual(action.calls, [0])

    def test_failed_action_is_reported(self):
        item = collect_reactions(FakeAccessible("👍", action=FakeAction(outcome=False)))[0]
        self.assertFalse(activate_reaction(item))

    def test_unrelated_sibling_is_not_scanned(self):
        focused = FakeAccessible("Current message")
        other = FakeAccessible("Reaction: ❤️", action=FakeAction())
        parent = FakeAccessible(children=[focused, other])
        focused.get_parent = lambda: parent
        self.assertEqual(collect_reactions(focused), [])

    def test_duplicate_reactions(self):
        root = FakeAccessible(children=[
            FakeAccessible("👍", action=FakeAction()),
            FakeAccessible("Reaction: 👍", action=FakeAction()),
        ])
        self.assertEqual(len(collect_reactions(root)), 1)


if __name__ == "__main__":
    unittest.main()
