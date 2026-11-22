"""Tests for the context-menu reaction flow with a simulated Telegram tree."""
import unittest

import reaction_menu
from reaction_menu import (find_reaction_item, is_emoji_text, reaction_button_label,
                           start_context_menu_reaction_flow)


class States:
    def __init__(self, node):
        self.node = node

    def contains(self, _key):
        return self.node.showing


class Action:
    def __init__(self, on_do=None, name="click"):
        self.on_do, self.name, self.calls = on_do, name, 0

    def get_n_actions(self):
        return 1

    def get_action_name(self, _index):
        return self.name

    def do_action(self, _index):
        self.calls += 1
        if self.on_do:
            self.on_do()
        return True


class Node:
    def __init__(self, role, name="", children=(), action=None, showing=True):
        self.role, self.name, self.action, self.showing = role, name, action, showing
        self.children, self.parent = [], None
        for child in children:
            self.add(child)

    def add(self, child):
        child.parent = self
        self.children.append(child)
        return child

    def remove(self, child):
        self.children.remove(child)
        child.parent = None

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

    def get_state_set(self):
        return States(self)

    def get_action_iface(self):
        return self.action


class FakeTelegram:
    """Application with a main window; Menu opens a popup, item opens picker."""

    def __init__(self, menu_keys=("Menu",), reaction_item="Добавить реакцию",
                 picker=("👍", "❤", "🔥"), strip=(), unnamed_picker=0):
        self.app = Node("application", "TelegramDesktop")
        self.message = Node("list item", "Иван: привет")
        self.main = self.app.add(Node("frame", "Telegram", [Node("list", "", [self.message])]))
        self.menu_keys, self.reaction_item_name = menu_keys, reaction_item
        self.picker_names, self.strip_names, self.unnamed_picker = picker, strip, unnamed_picker
        self.popup = self.picker = None
        self.applied, self.keys = [], []

    def make_popup(self):
        items = [Node("menu item", "Ответить", action=Action()),
                 Node("menu item", "Копировать текст", action=Action())]
        if self.reaction_item_name:
            items.insert(0, Node("menu item", self.reaction_item_name, action=Action(self.open_picker)))
        strip = [Node("push button", n, action=Action(lambda n=n: self.applied.append(n)))
                 for n in self.strip_names]
        self.popup = self.app.add(Node("popup menu", "", strip + items))

    def open_picker(self):
        buttons = [Node("push button", n, action=Action(lambda n=n: self.applied.append(n)))
                   for n in self.picker_names]
        buttons += [Node("push button", "") for _ in range(self.unnamed_picker)]
        self.picker = self.app.add(Node("window", "", [Node("panel", "", buttons)]))

    def close_all(self):
        for node in (self.picker, self.popup):
            if node is not None and node.parent is not None:
                self.app.remove(node)
        self.popup = self.picker = None

    def key(self, combo):
        self.keys.append("+".join(combo))
        if combo == ("Escape",):
            self.close_all()
        elif "+".join(combo) in self.menu_keys:
            self.make_popup()


class Env:
    def __init__(self, telegram, choice=0):
        self.telegram, self.choice, self.queue, self.offered = telegram, choice, [], None

    def schedule(self, _delay, callback):
        self.queue.append(callback)

    def send_keys(self, combo):
        self.telegram.key(tuple(combo))

    def modifiers_held(self):
        return False

    def choose(self, labels):
        self.offered = labels
        return self.choice

    def run(self):
        for _ in range(10000):
            if not self.queue:
                return
            self.queue.pop(0)()
        raise AssertionError("flow did not finish")


class Controller:
    def __init__(self, focus=None):
        self.messages, self.focus = [], focus

    def present_message_internal(self, message):
        self.messages.append(message)

    def get_current_object_internal(self):
        return self.focus


def run_flow(telegram, choice=0):
    reaction_menu._ACTIVE["flow"] = None
    controller, env = Controller(telegram.message), Env(telegram, choice)
    flow = start_context_menu_reaction_flow(telegram.message, controller, env)
    env.run()
    return flow, controller, env


class HelperTests(unittest.TestCase):
    def test_emoji_detection(self):
        self.assertTrue(is_emoji_text("👍"))
        self.assertTrue(is_emoji_text("❤️"))
        self.assertFalse(is_emoji_text("Ответить"))
        self.assertFalse(is_emoji_text(""))
        self.assertEqual(reaction_button_label("👍"), "👍 Thumbs up")
        self.assertEqual(reaction_button_label("🦄"), "🦄")
        self.assertIsNone(reaction_button_label("Копировать"))

    def test_reaction_item_prefers_add_over_remove(self):
        items = [Node("menu item", "Убрать реакцию"), Node("menu item", "Add Reaction")]
        self.assertEqual(find_reaction_item(items).name, "Add Reaction")
        self.assertIsNone(find_reaction_item([Node("menu item", "Ответить")]))


class FlowTests(unittest.TestCase):
    def test_menu_item_picker_choose_and_apply(self):
        telegram = FakeTelegram()
        flow, controller, env = run_flow(telegram, choice=2)
        self.assertEqual(env.offered, ["👍 Thumbs up", "❤ Heart", "🔥 Fire"])
        self.assertEqual(telegram.applied, ["🔥"])
        self.assertTrue(flow.finished)
        self.assertIn("Reaction 🔥 Fire activated.", controller.messages)
        # Menu opened twice: once to list, once to apply after the dialog.
        self.assertEqual(telegram.keys.count("Menu"), 2)

    def test_falls_back_to_shift_f10(self):
        telegram = FakeTelegram(menu_keys=("Shift+F10",))
        _flow, _controller, env = run_flow(telegram, choice=0)
        self.assertEqual(telegram.applied, ["👍"])
        self.assertIn("Shift+F10", telegram.keys)

    def test_menu_never_opens_reports_reason(self):
        telegram = FakeTelegram(menu_keys=())
        _flow, controller, env = run_flow(telegram)
        self.assertIsNone(env.offered)
        self.assertIn("context menu did not open", controller.messages[-1])
        self.assertIn("Shift+F10", controller.messages[-1])

    def test_no_reaction_item_lists_menu_items(self):
        telegram = FakeTelegram(reaction_item=None)
        _flow, controller, env = run_flow(telegram)
        self.assertIsNone(env.offered)
        self.assertIn("no reaction item", controller.messages[-1])
        self.assertIn("Ответить", controller.messages[-1])
        self.assertEqual(telegram.applied, [])

    def test_reaction_strip_in_menu_without_item(self):
        telegram = FakeTelegram(reaction_item=None, strip=("👍", "😢"))
        _flow, _controller, env = run_flow(telegram, choice=1)
        self.assertEqual(env.offered, ["👍 Thumbs up", "😢 Sad"])
        self.assertEqual(telegram.applied, ["😢"])

    def test_picker_with_unnamed_buttons_reports_reason(self):
        telegram = FakeTelegram(picker=(), unnamed_picker=5)
        _flow, controller, _env = run_flow(telegram)
        self.assertIn("5 buttons have no accessible names", controller.messages[-1])

    def test_picker_never_appears(self):
        telegram = FakeTelegram(picker=())
        _flow, controller, _env = run_flow(telegram)
        self.assertIn("no reaction panel appeared", controller.messages[-1])

    def test_cancel_applies_nothing(self):
        telegram = FakeTelegram()
        flow, _controller, _env = run_flow(telegram, choice=None)
        self.assertEqual(telegram.applied, [])
        self.assertTrue(flow.finished)
        self.assertIsNone(telegram.popup)

    def test_no_focused_message(self):
        reaction_menu._ACTIVE["flow"] = None
        controller = Controller()
        env = Env(FakeTelegram())
        start_context_menu_reaction_flow(None, controller, env)
        self.assertIn("no focused Telegram message", controller.messages[-1])


class WiringTests(unittest.TestCase):
    def test_no_direct_reactions_starts_context_menu_flow(self):
        import reactions
        calls = []
        original = reaction_menu.start_context_menu_reaction_flow
        reaction_menu.start_context_menu_reaction_flow = lambda obj, ctl: calls.append(obj)
        try:
            message = Node("list item", "Hello")
            reactions.show_reactions_for_current_object(message, Controller(message))
        finally:
            reaction_menu.start_context_menu_reaction_flow = original
        self.assertEqual(calls, [message])

    def test_gi_style_action_without_query_action(self):
        import reactions
        button = Node("push button", "Reaction: 👍", action=Action())
        found = reactions.collect_reactions(Node("panel", "", [button]))
        self.assertEqual([label for label, _obj, _i in found], ["Thumbs up"])
        self.assertTrue(reactions.activate_reaction(found[0]))
        self.assertEqual(button.action.calls, 1)


if __name__ == "__main__":
    unittest.main()
