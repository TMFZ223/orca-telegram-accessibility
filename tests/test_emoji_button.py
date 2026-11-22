"""Tests for the experimental unnamed emoji button in an open popup."""
import unittest
from reactions import _unnamed_emoji_button, try_open_emoji_button


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
    def __init__(self, role, name="", children=(), action=None):
        self.role, self.name, self.children, self.action = role, name, list(children), action
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

    def query_action(self):
        return self.action


class Controller:
    def __init__(self):
        self.messages = []

    def present_message_internal(self, message):
        self.messages.append(message)


class EmojiButtonTests(unittest.TestCase):
    def test_only_matching_popup_button_activated(self):
        action = Action()
        label = Node("label", "В этом сообщении эмодзи из 3 наборов.")
        button = Node("push button", "", [label], action)
        item = Node("menu item", "Ответить")
        popup = Node("popup menu", "TelegramDesktop", [item, button])
        controller = Controller()
        self.assertTrue(try_open_emoji_button(item, controller))
        self.assertEqual(action.calls, 1)

    def test_no_action_is_not_clicked(self):
        button = Node("push button", "", [Node("label", "В этом сообщении эмодзи из 3 наборов.")])
        item = Node("menu item", "Ответить")
        Node("popup menu", "TelegramDesktop", [item, button])
        controller = Controller()
        self.assertTrue(try_open_emoji_button(item, controller))
        self.assertIn("no accessible activation action", controller.messages[0])

    def test_no_popup_does_not_activate(self):
        button = Node("push button", "", [Node("label", "В этом сообщении эмодзи из 3 наборов.")], Action())
        self.assertIsNone(_unnamed_emoji_button(button))

    def test_ambiguous_buttons_not_activated(self):
        a = Action()
        b = Action()
        label = "В этом сообщении эмодзи из 3 наборов."
        first = Node("push button", "", [Node("label", label)], a)
        second = Node("push button", "", [Node("label", label)], b)
        item = Node("menu item", "Ответить")
        Node("popup menu", "", [item, first, second])
        self.assertFalse(try_open_emoji_button(item, Controller()))
        self.assertEqual((a.calls, b.calls), (0, 0))


if __name__ == "__main__":
    unittest.main()
