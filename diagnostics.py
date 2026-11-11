"""Opt-in AT-SPI diagnostics for the focused Telegram message.

The report can contain private message text and URLs. It is saved locally
with owner-only permissions and is never uploaded by this extension.
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timezone

from .links import _get_value


def _short(value, limit=1000):
    value = repr(value)
    return value[:limit] + ("... [truncated]" if len(value) > limit else "")


def save_accessibility_report(root):
    """Inspect focused accessible, its descendants and ancestor metadata."""
    if root is None:
        raise ValueError("No focused accessible")
    lines = ["Telegram AT-SPI diagnostics", "Created: " + datetime.now(timezone.utc).isoformat(),
             "WARNING: This report may contain private messages and links.", ""]
    pending = [(root, "focused", 0)]
    visited = set()
    current = root
    for depth in range(1, 4):
        current = _get_value(current, ("get_parent", "getParent"))
        if current is None:
            break
        pending.append((current, "ancestor", depth))
    # Traverse descendants only from focused object, not ancestors.
    for obj, kind, depth in pending[:]:
        if kind != "focused":
            continue
        queue = [(obj, 0)]
        while queue and len(pending) < 90:
            node, level = queue.pop(0)
            if level >= 3:
                continue
            count = _get_value(node, ("get_child_count", "getChildCount"))
            if not isinstance(count, int):
                continue
            for index in range(min(count, 30)):
                child = _get_value(node, ("get_child_at_index", "getChildAtIndex"), index)
                if child is not None:
                    pending.append((child, "descendant", level + 1))
                    queue.append((child, level + 1))
    for obj, kind, depth in pending[:90]:
        if id(obj) in visited:
            continue
        visited.add(id(obj))
        lines.append("OBJECT " + kind + " depth=" + str(depth))
        for key, methods in [
            ("role", ("get_role_name", "getRoleName")),
            ("name", ("get_name", "getName")),
            ("description", ("get_description", "getDescription")),
            ("attributes", ("get_attributes", "getAttributes")),
        ]:
            lines.append(key + ": " + _short(_get_value(obj, methods)))
        iface = _get_value(obj, ("query_text", "queryText"))
        if iface is not None:
            count = _get_value(iface, ("get_character_count", "getCharacterCount"))
            lines.append("text_length: " + _short(count))
            lines.append("text: " + _short(_get_value(iface, ("get_text", "getText"), 0,
                                                   min(count, 1000) if isinstance(count, int) else -1)))
            if isinstance(count, int) and count > 0:
                for offset in (0, max(0, count - 1)):
                    attrs = _get_value(iface, ("get_attribute_run", "getAttributeRun"), offset, False)
                    if attrs is None:
                        attrs = _get_value(iface, ("get_attributes", "getAttributes"), offset)
                    lines.append("text_attributes_at_" + str(offset) + ": " + _short(attrs))
        hyper = _get_value(obj, ("query_hypertext", "queryHypertext"))
        if hyper is not None:
            n = _get_value(hyper, ("get_n_links", "getNLinks"))
            lines.append("hypertext_link_count: " + _short(n))
            for i in range(min(n, 30) if isinstance(n, int) else 0):
                link = _get_value(hyper, ("get_link", "getLink"), i)
                lines.append("hyperlink_" + str(i) + ": " + _short((
                    _get_value(link, ("get_name", "getName")),
                    _get_value(link, ("get_uri", "getURI"), 0))))
        lines.append("")
    target = Path.home() / ".local" / "share" / "orca" / "telegram-link-diagnostics.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines))
    except Exception:
        raise
    return target
