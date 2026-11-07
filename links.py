"""AT-SPI link discovery and a small GTK link chooser.

The helpers deliberately use feature detection: AT-SPI bindings differ
slightly between distributions, and Telegram may expose different interfaces
depending on its build. Missing interfaces result in fewer discovered links,
not guessed coordinates or synthetic clicks.
"""

from __future__ import annotations

import re
import webbrowser
from urllib.parse import urlparse

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\u0000-\u001f]+")
_ALLOWED_SCHEMES = {"http", "https", "mailto"}
_MENTION_RE = re.compile(r"(?<![\\w@])@([A-Za-z0-9_]{5,32})(?![\\w])")


def _get_value(obj, names, *args):
    for name in names:
        method = getattr(obj, name, None)
        if callable(method):
            try:
                return method(*args)
            except Exception:
                continue
    return None


def _safe_uri(uri):
    if not isinstance(uri, str):
        return None
    uri = uri.strip().rstrip(".,;:!?)\u005d}")
    if uri.lower().startswith("www."):
        uri = "https://" + uri
    try:
        scheme = urlparse(uri).scheme.lower()
    except ValueError:
        return None
    return uri if scheme in _ALLOWED_SCHEMES else None


def _text_links(text):
    """Discover literal URLs and Telegram public usernames in visible text."""
    found = []
    spans = []
    for match in _URL_RE.finditer(text):
        safe = _safe_uri(match.group())
        if safe:
            found.append((match.group(), safe))
            spans.append(match.span())
    for match in _MENTION_RE.finditer(text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        username = match.group(1)
        found.append(("@" + username, "https://t.me/" + username))
    return found


def _open_link(uri):
    """Prefer the installed Telegram URI handler for public Telegram links."""
    parsed = urlparse(uri)
    if parsed.scheme == "https" and parsed.hostname in {"t.me", "telegram.me"}:
        username = parsed.path.strip("/")
        if re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            try:
                import gi
                from gi.repository import Gio
                app = Gio.AppInfo.get_default_for_uri_scheme("tg")
                if app is not None:
                    return bool(app.launch_uris(["tg://resolve?domain=" + username], None))
            except Exception:
                pass
    return webbrowser.open(uri)


def _accessible_name(obj):
    name = _get_value(obj, ("get_name", "getName"))
    return str(name).strip() if name else ""


def _hypertext_links(obj):
    hypertext = _get_value(obj, ("query_hypertext", "queryHypertext"))
    if hypertext is None:
        return []

    count = _get_value(hypertext, ("get_n_links", "getNLinks"))
    if not isinstance(count, int):
        return []

    found = []
    for index in range(max(0, count)):
        link = _get_value(hypertext, ("get_link", "getLink"), index)
        if link is None:
            continue
        uri = _get_value(link, ("get_uri", "getURI"), 0)
        label = _get_value(link, ("get_name", "getName")) or uri
        safe = _safe_uri(uri)
        if safe:
            found.append((str(label or safe), safe))
    return found


def _attribute_links(attributes, label):
    """Read URI-bearing AT-SPI attributes, including text formatting runs."""
    if isinstance(attributes, dict):
        items = attributes.items()
    else:
        items = []
        for item in attributes or []:
            key, separator, value = str(item).partition(":")
            if separator:
                items.append((key, value))
    found = []
    for key, value in items:
        if str(key).strip().lower() in {"uri", "href", "url", "link", "link-url", "link-target"}:
            safe = _safe_uri(str(value))
            if safe:
                found.append((label or safe, safe))
    return found


def _text_attribute_links(text_iface, text):
    """Find named hyperlinks exposed as per-range AT-SPI text attributes."""
    count = _get_value(text_iface, ("get_character_count", "getCharacterCount"))
    if not isinstance(count, int) or count <= 0:
        return []
    found = []
    offset = 0
    # Bound work for long chat messages or malformed AT-SPI implementations.
    for _ in range(min(count, 4096)):
        result = _get_value(text_iface, ("get_attribute_run", "getAttributeRun"), offset, False)
        if result is None:
            result = _get_value(text_iface, ("get_attributes", "getAttributes"), offset)
        if not isinstance(result, (tuple, list)) or len(result) < 3:
            break
        attrs, start, end = result[:3]
        if not isinstance(start, int) or not isinstance(end, int):
            break
        if end <= offset:
            break
        label = _get_value(text_iface, ("get_text", "getText"), max(0, start), end)
        found.extend(_attribute_links(attrs, str(label or "").strip()))
        offset = end
        if offset >= count:
            break
    return found


def _object_links(obj):
    found = []
    role = _get_value(obj, ("get_role_name", "getRoleName")) or ""
    role = str(role).lower()
    name = _accessible_name(obj)

    # Some toolkits expose URI information on the accessible object itself.
    attrs = _get_value(obj, ("get_attributes", "getAttributes")) or []
    if isinstance(attrs, dict):
        attrs = [f"{key}:{value}" for key, value in attrs.items()]
    found.extend(_attribute_links(attrs, name))

    if "link" in role or "hyperlink" in role:
        hyperlink = _get_value(obj, ("query_hyperlink", "queryHyperlink"))
        uri = _get_value(hyperlink, ("get_uri", "getURI"), 0) if hyperlink else None
        safe = _safe_uri(uri)
        if safe:
            found.append((name or safe, safe))

    found.extend(_hypertext_links(obj))

    # Telegram can expose the whole message as an accessible name.
    found.extend(_text_links(name))

    # A text-only fallback is useful for messages whose URLs are spoken as
    # plain text and are not represented by AT-SPI Hyperlink objects.
    text_iface = _get_value(obj, ("query_text", "queryText"))
    found.extend(_text_attribute_links(text_iface, ""))
    length = _get_value(text_iface, ("get_character_count", "getCharacterCount"))
    text = _get_value(text_iface, ("get_text", "getText"), 0, length if isinstance(length, int) and length >= 0 else -1)
    if not text:
        text = _get_value(obj, ("get_text", "getText"), 0, -1)
    if text:
        found.extend(_text_links(str(text)))
    return found


def collect_links(root, max_nodes=500):
    """Return unique (label, URI) pairs found below an AT-SPI accessible."""
    if root is None:
        return []

    links = []
    seen_uris = set()
    visited = set()
    pending = [root]

    while pending and len(visited) < max_nodes:
        obj = pending.pop()
        identity = id(obj)
        if identity in visited:
            continue
        visited.add(identity)

        try:
            candidates = _object_links(obj)
        except Exception:
            candidates = []

        for label, uri in candidates:
            if uri not in seen_uris:
                seen_uris.add(uri)
                links.append((label or uri, uri))

        count = _get_value(obj, ("get_child_count", "getChildCount"))
        if not isinstance(count, int):
            continue
        for index in reversed(range(max(0, min(count, max_nodes)))):
            child = _get_value(obj, ("get_child_at_index", "getChildAtIndex"), index)
            if child is not None:
                pending.append(child)

    return links


def collect_message_links(root):
    """Search the focused object, then only ancestor text (never sibling messages)."""
    links = collect_links(root)
    if links:
        return links
    current = root
    seen = {id(root)}
    for _ in range(3):
        parent = _get_value(current, ("get_parent", "getParent"))
        if parent is None or id(parent) in seen:
            break
        seen.add(id(parent))
        # Do not traverse siblings: a container may hold many chat messages.
        links = _object_links(parent)
        if links:
            return list(dict((uri, (label, uri)) for label, uri in links).values())
        current = parent
    return []


def show_links_for_current_object(root, controller):
    """Show the discovered links in a modal, keyboard-operable GTK dialog."""
    links = collect_message_links(root)
    if not links:
        controller.present_message_internal("No links found in the current accessible message.")
        return
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
    except Exception as error:
        controller.present_message_internal(
            "Telegram link list is unavailable: GTK 3 could not be loaded."
        )
        return

    dialog = Gtk.Dialog(
        title="Links in current message",
        flags=Gtk.DialogFlags.MODAL,
    )
    dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)
    dialog.add_button("_Close", Gtk.ResponseType.CLOSE)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)
    dialog.set_default_size(640, 320)

    store = Gtk.ListStore(str, str)
    for label, uri in links:
        store.append([label, uri])

    tree = Gtk.TreeView(model=store)
    tree.set_headers_visible(True)
    renderer = Gtk.CellRendererText()
    column = Gtk.TreeViewColumn("Link", renderer, text=0)
    column.set_resizable(True)
    tree.append_column(column)
    tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

    if links:
        tree.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
    else:
        empty = Gtk.Label(
            label="No links were exposed in the current accessible message."
        )
        empty.set_line_wrap(True)
        dialog.get_content_area().pack_start(empty, True, True, 12)

    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroller.add(tree)
    if links:
        dialog.get_content_area().pack_start(scroller, True, True, 8)

    tree.connect("row-activated", lambda *_args: dialog.response(Gtk.ResponseType.ACCEPT))
    dialog.get_content_area().show_all()

    response = dialog.run()
    if response == Gtk.ResponseType.ACCEPT and links:
        model, iterator = tree.get_selection().get_selected()
        if iterator is not None:
            uri = model.get_value(iterator, 1)
            try:
                if not _open_link(uri):
                    controller.present_message_internal("Could not open the selected link.")
            except Exception:
                controller.present_message_internal("Could not open the selected link.")

    dialog.destroy()
