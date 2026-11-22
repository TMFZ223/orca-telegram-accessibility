"""Reach Telegram Desktop reactions through the message context menu.

Telegram Desktop 7.x does not reliably expose reactions as children of the
focused message. This module drives the same keyboard path a sighted user
would take:

1. keep the focused message, press Menu (fallback Shift+F10, then F10);
2. wait for a showing AT-SPI menu / popup menu;
3. find the menu item mentioning reactions ("Add reaction", "Добавить
   реакцию") and activate it, then wait for the reaction picker;
4. collect emoji buttons and present them in a GTK chooser;
5. activate the chosen emoji button.

Telegram closes its popups when Orca's GTK dialog takes focus, so the picker
is closed before the chooser is shown and reopened (steps 1-3) to apply the
chosen reaction. Only keyboard events and AT-SPI actions are used: no mouse
clicks and no guessed coordinates. Every failure is reported with a reason.
"""
from __future__ import annotations

try:
    from .links import _get_value, _accessible_name
    from .reactions import EMOJI_NAMES, _action_iface, _action_call, _action_index, _reaction_label
except ImportError:  # Standalone unit tests from repository root
    from links import _get_value, _accessible_name
    from reactions import EMOJI_NAMES, _action_iface, _action_call, _action_index, _reaction_label

MENU_KEY_SEQUENCES = (("Menu",), ("Shift", "F10"), ("F10",))
MENU_ROLES = {"menu", "popup menu"}
ITEM_ROLES = {"menu item", "check menu item", "radio menu item", "push button",
              "button", "list item", "toggle button"}
EMOJI_BUTTON_ROLES = ITEM_ROLES | {"table cell", "image", "label"}
REACTION_WORDS = ("реакци", "reaction")
NEGATIVE_WORDS = ("убрать", "удалить", "снять", "remove", "delete", "who reacted", "кто")

POLL_INTERVAL_MS = 100
MENU_TIMEOUT_MS = 1200
PICKER_TIMEOUT_MS = 2000
MODIFIER_TIMEOUT_MS = 1500

_KEYSYMS = {"Menu": 0xFF67, "F10": 0xFFC7, "Shift": 0xFFE1,
            "Return": 0xFF0D, "Escape": 0xFF1B}
_ACTIVE = {"flow": None}


# --------------------------------------------------------------------------
# AT-SPI helpers
# --------------------------------------------------------------------------

def _role(obj):
    return str(_get_value(obj, ("get_role_name", "getRoleName")) or "").strip().casefold()


def _children(obj, limit=80):
    count = _get_value(obj, ("get_child_count", "getChildCount"))
    if not isinstance(count, int):
        return []
    result = []
    for index in range(min(max(0, count), limit)):
        child = _get_value(obj, ("get_child_at_index", "getChildAtIndex"), index)
        if child is not None:
            result.append(child)
    return result


def _parent(obj):
    return _get_value(obj, ("get_parent", "getParent"))


def _is_showing(obj):
    """True unless the object reports a state set without SHOWING."""
    states = _get_value(obj, ("get_state_set", "getState"))
    if states is None:
        return True
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        key = Atspi.StateType.SHOWING
    except Exception:
        key = "showing"
    result = _get_value(states, ("contains",), key)
    return True if result is None else bool(result)


def _walk(root, max_depth=8, max_nodes=800, prune=None):
    """Breadth-first walk yielding (object, depth); bounded for huge trees."""
    queue, seen = [(root, 0)], set()
    while queue and len(seen) < max_nodes:
        obj, depth = queue.pop(0)
        if obj is None or id(obj) in seen:
            continue
        seen.add(id(obj))
        yield obj, depth
        if depth < max_depth and not (prune and prune(obj)):
            queue.extend((child, depth + 1) for child in _children(obj))


def _application(obj):
    app = _get_value(obj, ("get_application", "getApplication"))
    if app is not None:
        return app
    current, last = obj, obj
    for _ in range(64):
        parent = _parent(current)
        if parent is None:
            break
        last, current = current, parent
        if _role(current) == "application":
            return current
    return current if current is not obj else last


def _top_level(obj, app):
    """The application child (window) containing ``obj``."""
    current = obj
    for _ in range(64):
        parent = _parent(current)
        if parent is None or parent is app or _role(parent) == "application":
            return current
        current = parent
    return current


def _ancestors(obj, limit=16):
    current = obj
    for _ in range(limit):
        if current is None:
            return
        yield current
        current = _parent(current)


def _is_within(obj, container):
    return any(node is container for node in _ancestors(obj, 32))


_EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF),
                 (0x2300, 0x23FF), (0x1F1E6, 0x1F1FF),
                 (0xE0020, 0xE007F))
_EMOJI_JOINERS = {0x200D, 0xFE0F, 0xFE0E, 0x20E3, 0x3030, 0x303D, 0x3297, 0x3299, 0x00A9, 0x00AE}


def is_emoji_text(text):
    """True for short strings made only of emoji code points."""
    text = str(text or "").strip()
    if not text or len(text) > 16:
        return False
    has_emoji = False
    for char in text:
        code = ord(char)
        if any(low <= code <= high for low, high in _EMOJI_RANGES) or code in _EMOJI_JOINERS:
            has_emoji = has_emoji or code not in (0x200D, 0xFE0F, 0xFE0E)
        elif char in "#*0123456789" and "\u20e3" in text:
            continue
        else:
            return False
    return has_emoji


def reaction_button_label(name):
    """Spoken label for an emoji/reaction button, or None if not a reaction."""
    name = str(name or "").strip()
    explicit = _reaction_label(name)
    if explicit and explicit != name and name in EMOJI_NAMES:
        return f"{name} {explicit}"
    if explicit:
        return explicit
    if is_emoji_text(name):
        return name
    return None


def find_menu_popup(app, focus=None, exclude=None):
    """Return a showing menu/popup menu of the application, if any."""
    for node in _ancestors(focus):
        if _role(node) in MENU_ROLES and _is_showing(node):
            return node
    if app is None:
        return None
    for node, _depth in _walk(app, max_depth=5, max_nodes=600,
                              prune=lambda obj: obj is exclude):
        if node is exclude:
            continue
        if _role(node) in MENU_ROLES and _is_showing(node) and _children(node):
            return node
    return None


def menu_items(popup):
    items = []
    for node, _depth in _walk(popup, max_depth=4, max_nodes=300):
        if node is popup:
            continue
        if _role(node) in ITEM_ROLES and _accessible_name(node) and _is_showing(node):
            items.append(node)
    return items


def find_reaction_item(items):
    """Pick the menu item that opens the reaction picker."""
    matches = [item for item in items
               if any(word in _accessible_name(item).casefold() for word in REACTION_WORDS)]
    preferred = [item for item in matches
                 if not any(word in _accessible_name(item).casefold() for word in NEGATIVE_WORDS)]
    return (preferred or matches or [None])[0]


def collect_emoji_buttons(container, exclude=None):
    """Return [(label, raw name, accessible)] of reaction buttons in a popup."""
    result, seen = [], set()
    for node, _depth in _walk(container, max_depth=10, max_nodes=1500,
                              prune=lambda obj: obj is exclude):
        if node is exclude or _role(node) not in EMOJI_BUTTON_ROLES:
            continue
        name = _accessible_name(node)
        label = reaction_button_label(name)
        if label and name not in seen and _is_showing(node):
            seen.add(name)
            result.append((label, name, node))
    return result


def count_unnamed_buttons(container):
    return sum(1 for node, _ in _walk(container, max_depth=10, max_nodes=1500)
               if _role(node) in ("push button", "button", "toggle button")
               and not _accessible_name(node))


def activate(obj, env):
    """Activate via AT-SPI Action; fall back to keyboard focus + Return."""
    target = _action_index(obj)
    if target is None:
        iface = _action_iface(obj)
        count = _action_call(iface, ("get_n_actions", "getNActions")) if iface else None
        if isinstance(count, int) and count > 0:
            target = (iface, 0)
    if target is not None:
        iface, index = target
        if _action_call(iface, ("do_action", "doAction"), index) is True:
            return True
    component = _get_value(obj, ("get_component_iface", "query_component", "queryComponent")) or obj
    if _get_value(component, ("grab_focus", "grabFocus")) is True:
        env.send_keys(("Return",))
        return True
    return False


# --------------------------------------------------------------------------
# Environment: real GLib/AT-SPI/GTK implementation (replaced in unit tests)
# --------------------------------------------------------------------------

class GtkEnvironment:
    def schedule(self, delay_ms, callback):
        from gi.repository import GLib

        def run():
            callback()
            return False
        GLib.timeout_add(max(0, int(delay_ms)), run)

    def _keycode(self, keysym):
        try:
            import gi
            gi.require_version("Gdk", "3.0")
            from gi.repository import Gdk
            keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
            ok, keys = keymap.get_entries_for_keyval(keysym)
            if ok and keys:
                return keys[0].keycode
        except Exception:
            pass
        return None

    def send_keys(self, combo):
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        *modifiers, key = combo
        held = []
        for modifier in modifiers:
            code = self._keycode(_KEYSYMS[modifier])
            if code is not None:
                Atspi.generate_keyboard_event(code, None, Atspi.KeySynthType.PRESS)
                held.append(("code", code))
            else:
                Atspi.generate_keyboard_event(Atspi.ModifierType.SHIFT,
                                              None, Atspi.KeySynthType.LOCKMODIFIERS)
                held.append(("lock", Atspi.ModifierType.SHIFT))
        try:
            Atspi.generate_keyboard_event(_KEYSYMS[key], None, Atspi.KeySynthType.SYM)
        finally:
            for kind, value in reversed(held):
                if kind == "code":
                    Atspi.generate_keyboard_event(value, None, Atspi.KeySynthType.RELEASE)
                else:
                    Atspi.generate_keyboard_event(value, None, Atspi.KeySynthType.UNLOCKMODIFIERS)

    def modifiers_held(self):
        """True while Ctrl/Shift/Alt from the Orca shortcut are still pressed."""
        try:
            import gi
            gi.require_version("Gdk", "3.0")
            from gi.repository import Gdk
            keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
            mask = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
                    | Gdk.ModifierType.MOD1_MASK)
            return bool(keymap.get_modifier_state() & mask)
        except Exception:
            return False

    def choose(self, labels):
        """Modal keyboard-operable chooser; returns the index or None."""
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        dialog = Gtk.Dialog(title="Reactions for current message", flags=Gtk.DialogFlags.MODAL)
        dialog.add_button("_Apply", Gtk.ResponseType.ACCEPT)
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(440, 320)
        store = Gtk.ListStore(str)
        for label in labels:
            store.append([label])
        tree = Gtk.TreeView(model=store)
        tree.set_headers_visible(False)
        tree.append_column(Gtk.TreeViewColumn("Reaction", Gtk.CellRendererText(), text=0))
        tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        tree.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        scroller = Gtk.ScrolledWindow()
        scroller.add(tree)
        dialog.get_content_area().pack_start(scroller, True, True, 8)
        tree.connect("row-activated", lambda *_: dialog.response(Gtk.ResponseType.ACCEPT))
        dialog.get_content_area().show_all()
        tree.grab_focus()
        try:
            if dialog.run() != Gtk.ResponseType.ACCEPT:
                return None
            model, iterator = tree.get_selection().get_selected()
            return None if iterator is None else model.get_path(iterator).get_indices()[0]
        finally:
            dialog.destroy()


# --------------------------------------------------------------------------
# The flow (asynchronous: Orca's key handler must return immediately)
# --------------------------------------------------------------------------

class ReactionMenuFlow:
    def __init__(self, message, controller, env=None):
        self.message = message
        self.controller = controller
        self.env = env or GtkEnvironment()
        self.app = _application(message) if message is not None else None
        self.main_window = _top_level(message, self.app) if message is not None else None
        self.target_name = None   # set when reopening to apply a chosen reaction
        self.target_label = None
        self.popup = None
        self.strip = []
        self.item_name = ""
        self.finished = False

    # -- utilities --------------------------------------------------------
    def say(self, message):
        self.controller.present_message_internal(message)

    def finish(self, message=None):
        if message:
            self.say(message)
        self.finished = True
        if _ACTIVE["flow"] is self:
            _ACTIVE["flow"] = None

    def wait_for(self, probe, on_found, on_timeout, timeout_ms):
        state = {"elapsed": 0}

        def tick():
            try:
                found = probe()
            except Exception:
                found = None
            if found:
                on_found(found)
            elif state["elapsed"] >= timeout_ms:
                on_timeout()
            else:
                state["elapsed"] += POLL_INTERVAL_MS
                self.env.schedule(POLL_INTERVAL_MS, tick)
        self.env.schedule(POLL_INTERVAL_MS, tick)

    def current_focus(self):
        try:
            return self.controller.get_current_object_internal()
        except Exception:
            return None

    def find_popup(self):
        return find_menu_popup(self.app, self.current_focus(), exclude=self.main_window)

    def close_popups(self, count=2):
        for _ in range(count):
            self.env.send_keys(("Escape",))

    # -- step 0: wait until the user releases Ctrl/Shift of the shortcut ----
    def start(self):
        if self.message is None:
            self.finish("Reactions: no focused Telegram message. Move focus to a message in the chat history.")
            return
        state = {"elapsed": 0}

        def check():
            if self.env.modifiers_held() and state["elapsed"] < MODIFIER_TIMEOUT_MS:
                state["elapsed"] += POLL_INTERVAL_MS
                self.env.schedule(POLL_INTERVAL_MS, check)
            else:
                self.open_menu(0)
        self.env.schedule(POLL_INTERVAL_MS, check)

    # -- step 1-2: open the context menu --------------------------------
    def open_menu(self, attempt):
        if attempt == 0:
            self.say("Opening the message menu to find reactions…" if self.target_name is None
                     else "Applying reaction…")
        component = _get_value(self.message, ("get_component_iface", "query_component")) or self.message
        _get_value(component, ("grab_focus", "grabFocus"))
        combo = MENU_KEY_SEQUENCES[attempt]
        try:
            self.env.send_keys(combo)
        except Exception:
            self.finish("Reactions: could not send keyboard events through AT-SPI, "
                        "so the Telegram message menu cannot be opened.")
            return

        def timeout():
            if attempt + 1 < len(MENU_KEY_SEQUENCES):
                self.open_menu(attempt + 1)
            else:
                tried = ", ".join("+".join(keys) for keys in MENU_KEY_SEQUENCES)
                self.finish("Reactions: the Telegram message context menu did not open "
                            f"(tried {tried}). Make sure a message in the chat history "
                            "has keyboard focus and the Telegram window is active.")
        self.wait_for(self.find_popup, self.on_menu, timeout, MENU_TIMEOUT_MS)

    # -- step 3-4: find "Add reaction" and open the picker ---------------
    def on_menu(self, popup):
        self.popup = popup
        self.strip = collect_emoji_buttons(popup)
        items = menu_items(popup)
        item = find_reaction_item(items)
        if self.target_name is not None and self.apply_from(self.strip):
            return
        if item is None:
            if self.strip:
                self.on_picker(self.strip)
                return
            names = [_accessible_name(entry) for entry in items][:12]
            self.close_popups(1)
            listing = ", ".join(names) if names else "no named items"
            self.finish("Reactions: the context menu opened but has no reaction item and "
                        f"no reaction buttons (menu items: {listing}). Reactions may be "
                        "disabled in this chat or not exposed through AT-SPI.")
            return
        self.item_name = _accessible_name(item)
        if not activate(item, self.env):
            self.close_popups(1)
            self.finish(f"Reactions: found the menu item '{self.item_name}' but could not "
                        "activate it through AT-SPI or the keyboard.")
            return
        self.wait_for(self.find_picker, self.on_picker, self.picker_timeout, PICKER_TIMEOUT_MS)

    def picker_containers(self):
        if self.app is None:
            return []
        containers = []
        for window in _children(self.app, limit=40):
            if window is self.main_window or not _is_showing(window):
                continue
            containers.append(window)
        return containers

    def find_picker(self):
        for container in self.picker_containers():
            buttons = collect_emoji_buttons(container, exclude=self.popup)
            if buttons:
                return buttons
        # Telegram may expand the reaction strip inside the same popup.
        expanded = collect_emoji_buttons(self.popup) if self.popup is not None else []
        if len(expanded) > len(self.strip):
            return expanded
        return None

    def picker_timeout(self):
        if self.strip:
            self.on_picker(self.strip)
            return
        unnamed = sum(count_unnamed_buttons(c) for c in self.picker_containers())
        self.close_popups()
        if unnamed:
            self.finish(f"Reactions: '{self.item_name}' opened a panel, but its {unnamed} buttons "
                        "have no accessible names, so the reactions cannot be identified.")
        else:
            self.finish(f"Reactions: activated '{self.item_name}', but no reaction panel "
                        f"appeared in the AT-SPI tree within {PICKER_TIMEOUT_MS // 1000} seconds.")

    # -- step 5-7: choose and apply ---------------------------------------
    def on_picker(self, buttons):
        if self.target_name is not None:
            if not self.apply_from(buttons):
                self.close_popups()
                self.finish(f"Reactions: could not find the reaction {self.target_name} "
                            "again after reopening the picker.")
            return
        self.close_popups()
        labels = [label for label, _name, _obj in buttons]
        try:
            index = self.env.choose(labels)
        except Exception:
            self.finish("Reaction picker unavailable: GTK 3 could not be loaded.")
            return
        if index is None:
            self.finish()
            return
        # The popups were closed for the dialog: reopen and match by name.
        label, name, _button = buttons[index]
        self.target_name, self.target_label = name, label
        self.open_menu(0)

    def apply_from(self, buttons):
        for label, name, button in buttons:
            if name == self.target_name:
                self.apply_button(label, button)
                return True
        return False

    def apply_button(self, label, button):
        if activate(button, self.env):
            self.finish(f"Reaction {label} activated.")
        else:
            self.close_popups()
            self.finish(f"Reactions: could not activate the reaction {label}.")


def start_context_menu_reaction_flow(message, controller, env=None):
    """Entry point used by the Orca command; returns the flow (for tests)."""
    if _ACTIVE["flow"] is not None and not _ACTIVE["flow"].finished:
        controller.present_message_internal("Reactions: the previous reaction request is still running.")
        return None
    flow = ReactionMenuFlow(message, controller, env)
    _ACTIVE["flow"] = flow
    flow.start()
    return flow
