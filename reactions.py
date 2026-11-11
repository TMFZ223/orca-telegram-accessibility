"""Conservative AT-SPI reaction discovery and keyboard-operated chooser.

Only explicit, actionable reaction controls are offered. Telegram Desktop may
not expose its available-reactions menu to AT-SPI; in that case do not guess.
"""
from __future__ import annotations

from .links import _get_value, _accessible_name

EMOJI_NAMES = {
    "👍": "Thumbs up", "👎": "Thumbs down", "❤️": "Heart",
    "❤": "Heart", "😂": "Laugh", "🤣": "Rolling on the floor laughing",
    "😮": "Surprised", "😢": "Sad", "😡": "Angry",
    "🔥": "Fire", "👏": "Clap", "🎉": "Celebration",
    "😍": "Heart eyes", "🤔": "Thinking", "🙏": "Folded hands",
}
_ACTION_WORDS = ("click", "press", "activate", "select")


def _reaction_label(name):
    """Return a readable label only for explicitly identified reactions."""
    name = str(name or "").strip()
    if not name:
        return None
    lowered = name.casefold()
    if name in EMOJI_NAMES:
        return EMOJI_NAMES[name]
    for prefix in ("reaction: ", "react with ", "reaction ", "реакция: ", "поставить реакцию "):
        if lowered.startswith(prefix):
            value = name[len(prefix):].strip()
            return EMOJI_NAMES.get(value, value) or None
    return None


def _action_index(obj):
    action = _get_value(obj, ("query_action", "queryAction"))
    if action is None:
        return None
    count = _get_value(action, ("get_n_actions", "getNActions"))
    if not isinstance(count, int):
        return None
    for i in range(min(max(0, count), 32)):
        name = _get_value(action, ("get_name", "getName"), i)
        if str(name or "").strip().casefold() in _ACTION_WORDS:
            return action, i
    return None


def collect_reactions(root, max_nodes=300):
    """Collect (spoken label, accessible, action index) for explicit controls.

    Never scan ancestor siblings: those may belong to other chat messages.
    """
    if root is None:
        return []
    result, visited, pending, seen = [], set(), [root], set()
    while pending and len(visited) < max_nodes:
        obj = pending.pop()
        if id(obj) in visited:
            continue
        visited.add(id(obj))
        label = _reaction_label(_accessible_name(obj))
        target = _action_index(obj) if label else None
        if label and target and label.casefold() not in seen:
            result.append((label, obj, target[1]))
            seen.add(label.casefold())
        count = _get_value(obj, ("get_child_count", "getChildCount"))
        if isinstance(count, int):
            for i in reversed(range(min(max(0, count), max_nodes))):
                child = _get_value(obj, ("get_child_at_index", "getChildAtIndex"), i)
                if child is not None:
                    pending.append(child)
    return result


def activate_reaction(item):
    """Activate the explicit AT-SPI action; never simulate a pointer click."""
    _, obj, index = item
    action = _get_value(obj, ("query_action", "queryAction"))
    return _get_value(action, ("do_action", "doAction"), index) is True


def show_reactions_for_current_object(root, controller):
    reactions = collect_reactions(root)
    if not reactions:
        controller.present_message_internal(
            "No actionable reactions were exposed for this message through AT-SPI."
        )
        return
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
    except Exception:
        controller.present_message_internal("Reaction picker unavailable: GTK 3 could not be loaded.")
        return

    dialog = Gtk.Dialog(title="Reactions for current message", flags=Gtk.DialogFlags.MODAL)
    dialog.add_button("_Apply", Gtk.ResponseType.ACCEPT)
    dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)
    dialog.set_default_size(440, 300)

    store = Gtk.ListStore(str)
    for label, _, _ in reactions:
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
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            model, iterator = tree.get_selection().get_selected()
            if iterator is not None:
                index = model.get_path(iterator).get_indices()[0]
                if not activate_reaction(reactions[index]):
                    controller.present_message_internal("Could not apply the selected reaction.")
    finally:
        dialog.destroy()
