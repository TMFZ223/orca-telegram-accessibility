"""Read-only geometry, interface and relation diagnostics for focused Telegram messages.

No mouse movement, focus changes, actions or selection changes are performed.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from .links import _get_value
except ImportError:
    from links import _get_value

MAX_CHILDREN = 35
MAX_RELATIONS = 16
MAX_TARGETS = 8


def _safe(value, limit=350):
    result = repr(value)
    return result[:limit] + ("... [truncated]" if len(result) > limit else "")


def _name(obj):
    return str(_get_value(obj, ("get_name", "getName")) or "")


def _children(obj):
    count = _get_value(obj, ("get_child_count", "getChildCount"))
    if not isinstance(count, int):
        return []
    return [
        child for i in range(min(max(0, count), MAX_CHILDREN))
        if (child := _get_value(obj, ("get_child_at_index", "getChildAtIndex"), i)) is not None
    ]


def _interface(obj, names):
    # Only query; never invoke a mutating method on the returned interface.
    return _get_value(obj, names)


def _geometry(obj):
    component = _interface(obj, ("query_component", "queryComponent"))
    if component is None:
        return "not exposed"
    # AT-SPI CoordType.SCREEN = 0, WINDOW = 1. No pointer operations.
    values = []
    for label, coord_type in (("screen", 0), ("window", 1)):
        rect = _get_value(component, ("get_extents", "getExtents"), coord_type)
        if rect is None:
            values.append(label + "=unavailable")
        else:
            try:
                coords = tuple(getattr(rect, k) for k in ("x", "y", "width", "height"))
            except Exception:
                try:
                    coords = tuple(rect)
                except Exception:
                    coords = _safe(rect)
            values.append(label + "=" + _safe(coords))
    return ", ".join(values)


def _states(obj):
    state_set = _get_value(obj, ("get_state_set", "getStateSet"))
    if state_set is None:
        return "not exposed"
    # get_states is non-mutating; numeric values are binding-specific.
    states = _get_value(state_set, ("get_states", "getStates"))
    return _safe(states) if states is not None else "state set present; enumeration unavailable"


def _relations(obj):
    count = _get_value(obj, ("get_n_relations", "getNRelations"))
    if not isinstance(count, int):
        return "unavailable"
    result = []
    for i in range(min(max(0, count), MAX_RELATIONS)):
        rel = _get_value(obj, ("get_relation", "getRelation"), i)
        if rel is None:
            continue
        rel_type = _get_value(rel, ("get_relation_type", "getRelationType"))
        targets_count = _get_value(rel, ("get_n_targets", "getNTargets"))
        targets = []
        if isinstance(targets_count, int):
            for j in range(min(max(0, targets_count), MAX_TARGETS)):
                target = _get_value(rel, ("get_target", "getTarget"), j)
                if target is not None:
                    targets.append((_get_value(target, ("get_role_name", "getRoleName")), _name(target)))
        result.append((rel_type, targets))
    return _safe(result, 1200)


def _describe(obj, label):
    action = _interface(obj, ("query_action", "queryAction"))
    selection = _interface(obj, ("query_selection", "querySelection"))
    component = _interface(obj, ("query_component", "queryComponent"))
    count = _get_value(action, ("get_n_actions", "getNActions"))
    actions = []
    if isinstance(count, int):
        actions = [
            _get_value(action, ("get_name", "getName"), i)
            for i in range(min(max(0, count), 20))
        ]
    return [
        "OBJECT " + label,
        "role: " + _safe(_get_value(obj, ("get_role_name", "getRoleName"))),
        "name: " + _safe(_name(obj)),
        "description: " + _safe(_get_value(obj, ("get_description", "getDescription"))),
        "interfaces: Component=" + str(component is not None) +
        " Action=" + str(action is not None) +
        " Selection=" + str(selection is not None),
        "geometry: " + _geometry(obj),
        "states: " + _states(obj),
        "actions (not invoked): " + _safe(actions),
        "relations: " + _relations(obj),
        "",
    ]


def build_reaction_interface_report(focused):
    if focused is None:
        raise ValueError("No focused accessible")
    ancestors = []
    node, seen = focused, set()
    for _ in range(12):
        if node is None or id(node) in seen:
            break
        seen.add(id(node))
        ancestors.append(node)
        node = _get_value(node, ("get_parent", "getParent"))
    message = next(
        (node for node in ancestors
         if str(_get_value(node, ("get_role_name", "getRoleName")) or "").casefold() == "list item"),
        focused,
    )
    lines = [
        "Telegram reaction AT-SPI interface diagnostics",
        "Created: " + datetime.now(timezone.utc).isoformat(),
        "WARNING: Names and relations may contain private message information.",
        "Local only; redact before sharing. No actions or mouse operations.",
        "Scope: focused object, nearest ancestor message, direct children of that message.",
        "",
    ]
    lines.extend(_describe(focused, "focused"))
    if message is not focused:
        lines.extend(_describe(message, "message"))
    children = _children(message)
    lines.append("Message children inspected: " + str(len(children)))
    for i, child in enumerate(children):
        lines.extend(_describe(child, "message_child_" + str(i)))
    return "\n".join(lines)


def save_reaction_interface_report(focused, target=None):
    report = build_reaction_interface_report(focused)
    if target is None:
        target = Path.home() / ".local" / "share" / "orca" / "telegram-reaction-interfaces.txt"
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(report)
    return target
