"""Opt-in, local-only AT-SPI diagnostics for Telegram message reactions.

This report can contain private message text, names and attributes. Never
upload it automatically. Inspect focused descendants and ancestor metadata,
but never traverse sibling messages or invoke accessibility actions.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from .links import _get_value
    from .reactions import _reaction_label
except ImportError:  # Allow standalone unit tests.
    from links import _get_value
    from reactions import _reaction_label

MAX_NODES = 120
MAX_DEPTH = 5
MAX_CHILDREN = 35


def _short(value, limit=400):
    text = repr(value)
    return text[:limit] + ("... [truncated]" if len(text) > limit else "")


def _action_names(obj):
    iface = _get_value(obj, ("query_action", "queryAction"))
    count = _get_value(iface, ("get_n_actions", "getNActions"))
    if not isinstance(count, int):
        return []
    return [
        str(_get_value(iface, ("get_name", "getName"), i) or "")
        for i in range(min(max(0, count), 32))
    ]


def build_reaction_report(root):
    """Create a bounded, read-only description of accessible reaction controls."""
    if root is None:
        raise ValueError("No focused accessible")
    lines = [
        "Telegram reaction AT-SPI diagnostics",
        "Created: " + datetime.now(timezone.utc).isoformat(),
        "WARNING: May contain private message text, names and attributes.",
        "Review and redact before sharing. This report is not uploaded.",
        "Scope: focused object, its descendants, and ancestor metadata only.",
        "",
    ]
    pending = [(root, "focused", 0)]
    seen_ancestors = {id(root)}
    current = root
    for depth in range(1, 4):
        current = _get_value(current, ("get_parent", "getParent"))
        if current is None or id(current) in seen_ancestors:
            break
        seen_ancestors.add(id(current))
        pending.append((current, "ancestor", depth))

    queue = [(root, 0)]
    discovered = {id(root)}
    while queue and len(pending) < MAX_NODES:
        node, depth = queue.pop(0)
        if depth >= MAX_DEPTH:
            continue
        count = _get_value(node, ("get_child_count", "getChildCount"))
        if not isinstance(count, int):
            continue
        for i in range(min(max(0, count), MAX_CHILDREN)):
            child = _get_value(node, ("get_child_at_index", "getChildAtIndex"), i)
            if child is None or id(child) in discovered:
                continue
            discovered.add(id(child))
            pending.append((child, "descendant", depth + 1))
            queue.append((child, depth + 1))
            if len(pending) >= MAX_NODES:
                break

    visited = set()
    for obj, kind, depth in pending[:MAX_NODES]:
        if id(obj) in visited:
            continue
        visited.add(id(obj))
        role = _get_value(obj, ("get_role_name", "getRoleName"))
        name = _get_value(obj, ("get_name", "getName"))
        description = _get_value(obj, ("get_description", "getDescription"))
        attributes = _get_value(obj, ("get_attributes", "getAttributes"))
        actions = _action_names(obj)
        label = _reaction_label(name)
        keywords = ("react", "reaction", "emoji", "реакц", "эмодзи")
        candidate = bool(label or any(
            word in str(value or "").casefold()
            for value in (name, role, description)
            for word in keywords
        ))
        lines.extend([
            "OBJECT " + kind + " depth=" + str(depth),
            "role: " + _short(role),
            "name: " + _short(name),
            "description: " + _short(description),
            "attributes: " + _short(attributes),
            "child_count: " + _short(_get_value(obj, ("get_child_count", "getChildCount"))),
            "action_names: " + _short(actions),
            "reaction_candidate: " + str(candidate),
            "recognized_reaction: " + _short(label),
            "",
        ])
    lines.append("Objects inspected: " + str(len(visited)))
    return "\n".join(lines)


def save_reaction_report(root, target=None):
    report = build_reaction_report(root)
    if target is None:
        target = Path.home() / ".local" / "share" / "orca" / "telegram-reaction-diagnostics.txt"
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(report)
    return target

WINDOW_MAX_NODES = 220
WINDOW_MAX_DEPTH = 7
WINDOW_MAX_CHILDREN = 50
WINDOW_ROLES = ("frame", "window", "dialog", "alert", "file chooser", "popup menu")
POPUP_ROLES = ("popup menu", "menu", "menu item", "dialog", "panel", "tool tip")


def _role(obj):
    return str(_get_value(obj, ("get_role_name", "getRoleName")) or "").casefold()


def _walk_bounded(root, max_nodes=WINDOW_MAX_NODES):
    """Yield bounded descendants; never execute actions."""
    queue, visited = [(root, 0)], set()
    while queue and len(visited) < max_nodes:
        node, depth = queue.pop(0)
        if id(node) in visited:
            continue
        visited.add(id(node))
        yield node, depth
        if depth >= WINDOW_MAX_DEPTH:
            continue
        count = _get_value(node, ("get_child_count", "getChildCount"))
        if isinstance(count, int):
            for index in range(min(max(0, count), WINDOW_MAX_CHILDREN)):
                child = _get_value(node, ("get_child_at_index", "getChildAtIndex"), index)
                if child is not None and id(child) not in visited:
                    queue.append((child, depth + 1))


def build_window_reaction_report(root):
    """Inspect the containing window and popup-like application windows.

    Application siblings are inspected only when they have window-like roles.
    The output is bounded and may contain private chat content.
    """
    if root is None:
        raise ValueError("No focused accessible")
    ancestors, seen = [], set()
    current = root
    for _ in range(20):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        ancestors.append(current)
        current = _get_value(current, ("get_parent", "getParent"))

    window = next((obj for obj in ancestors if _role(obj) in WINDOW_ROLES), None)
    if window is None:
        raise ValueError("No containing AT-SPI window found")
    app = _get_value(window, ("get_parent", "getParent"))
    roots = [("containing_window", window)]
    if app is not None:
        count = _get_value(app, ("get_child_count", "getChildCount"))
        if isinstance(count, int):
            for index in range(min(max(0, count), 30)):
                candidate = _get_value(app, ("get_child_at_index", "getChildAtIndex"), index)
                if candidate is not None and candidate is not window and _role(candidate) in WINDOW_ROLES:
                    roots.append(("other_application_window", candidate))

    lines = [
        "Telegram reaction window AT-SPI diagnostics",
        "Created: " + datetime.now(timezone.utc).isoformat(),
        "WARNING: May contain private messages, names and attributes.",
        "Review and redact before sharing. This report is not uploaded.",
        "Scope: containing window and other window-like objects of the same application.",
        "Limits: 220 objects per window, depth 7, 50 children per node, 30 application children.",
        "",
    ]
    for kind, window_root in roots[:12]:
        lines.append("WINDOW " + kind + " role=" + _short(_role(window_root)))
        inspected = 0
        for obj, depth in _walk_bounded(window_root):
            inspected += 1
            role = _role(obj)
            name = _get_value(obj, ("get_name", "getName"))
            description = _get_value(obj, ("get_description", "getDescription"))
            label = _reaction_label(name)
            keywords = ("react", "reaction", "emoji", "реакц", "эмодзи")
            candidate = bool(label or role in POPUP_ROLES or any(
                word in str(value or "").casefold()
                for value in (name, description) for word in keywords
            ))
            lines.extend([
                "OBJECT depth=" + str(depth) + " popup_or_reaction_candidate=" + str(candidate),
                "role: " + _short(role),
                "name: " + _short(name),
                "description: " + _short(description),
                "attributes: " + _short(_get_value(obj, ("get_attributes", "getAttributes"))),
                "action_names: " + _short(_action_names(obj)),
                "recognized_reaction: " + _short(label),
                "",
            ])
        lines.append("Objects inspected in window: " + str(inspected))
        lines.append("")
    return "\n".join(lines)


def save_window_reaction_report(root, target=None):
    report = build_window_reaction_report(root)
    if target is None:
        target = Path.home() / ".local" / "share" / "orca" / "telegram-reaction-window-diagnostics.txt"
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(report)
    return target
