"""Unit tests for AT-SPI link discovery using lightweight test doubles."""

import unittest

from links import collect_links, collect_message_links, collect_copied_links, _safe_uri


class FakeHyperlink:
    def __init__(self, uri, name=None):
        self.uri = uri
        self.name = name

    def get_uri(self, _index):
        return self.uri

    def get_name(self):
        return self.name


class FakeHypertext:
    def __init__(self, uris):
        self.uris = uris

    def get_n_links(self):
        return len(self.uris)

    def get_link(self, index):
        return FakeHyperlink(self.uris[index])


class FakeAccessible:
    def __init__(self, name="", text="", children=None, links=None, role="panel"):
        self.name = name
        self.text = text
        self.children = children or []
        self.hypertext = FakeHypertext(links or [])
        self.role = role

    def get_name(self):
        return self.name

    def get_text(self, _start, _end):
        return self.text

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def get_role_name(self):
        return self.role

    def query_hypertext(self):
        return self.hypertext


class LinkDiscoveryTests(unittest.TestCase):
    def test_collects_hypertext_links(self):
        root = FakeAccessible(links=["https://example.com"])
        self.assertEqual(
            collect_links(root),
            [("https://example.com", "https://example.com")],
        )

    def test_collects_plain_text_urls_in_descendants(self):
        child = FakeAccessible(name="Message", text="See https://example.org/docs")
        root = FakeAccessible(children=[child])
        self.assertEqual(
            collect_links(root),
            [("https://example.org/docs", "https://example.org/docs")],
        )

    def test_deduplicates_urls(self):
        child = FakeAccessible(text="https://example.com")
        root = FakeAccessible(links=["https://example.com"], children=[child])
        self.assertEqual(len(collect_links(root)), 1)

    def test_ignores_unsafe_schemes(self):
        self.assertIsNone(_safe_uri("javascript:alert(1)"))
        self.assertIsNone(_safe_uri("data:text/html,hello"))
        self.assertEqual(_safe_uri("www.example.com"), "https://www.example.com")

    def test_url_in_accessible_name(self):
        root = FakeAccessible(name="Open https://example.org/cabinet/?tg=test-token")
        self.assertEqual(
            collect_links(root),
            [("https://example.org/cabinet/?tg=test-token",
              "https://example.org/cabinet/?tg=test-token")],
        )

    def test_url_in_parent_text_without_scanning_siblings(self):
        focused = FakeAccessible(name="Focused element")
        sibling = FakeAccessible(text="https://wrong.example")
        parent = FakeAccessible(text="Message https://example.org/ok",
                                children=[focused, sibling])
        focused.get_parent = lambda: parent
        self.assertEqual(
            collect_message_links(focused),
            [("https://example.org/ok", "https://example.org/ok")],
        )

    def test_telegram_username_in_message(self):
        root = FakeAccessible(text="Читать полностью\\n@linux_potok")
        self.assertEqual(
            collect_links(root),
            [("@linux_potok", "https://t.me/linux_potok")],
        )

    def test_mention_not_extracted_from_url_or_email(self):
        root = FakeAccessible(text="https://example.org/@linux_potok and mail@example.org")
        self.assertEqual(
            collect_links(root),
            [("https://example.org/@linux_potok",
              "https://example.org/@linux_potok")],
        )

    def test_hypertext_named_link(self):
        root = FakeAccessible(links=["https://example.org/article"])
        root.hypertext.get_link = lambda _index: FakeHyperlink(
            "https://example.org/article", "Читать полностью"
        )
        self.assertEqual(
            collect_links(root),
            [("Читать полностью", "https://example.org/article")],
        )

    def test_named_link_in_text_attribute_run(self):
        root = FakeAccessible(text="Читать полностью")
        root.query_text = lambda: root
        root.get_character_count = lambda: len(root.text)
        root.get_attribute_run = lambda offset, include_defaults: (
            ["href:https://www.omgubuntu.co.uk/2026/11/global-menu-gnome-extension"],
            0, len(root.text),
        )
        self.assertEqual(
            collect_links(root),
            [("Читать полностью",
              "https://www.omgubuntu.co.uk/2026/11/global-menu-gnome-extension")],
        )

    def test_copied_named_and_telegram_links(self):
        copied = (
            "Расширение глобального меню GNOME Shell\\n"
            "Читать полностью (https://www.omgubuntu.co.uk/2026/11/global-menu-gnome-extension)\\n"
            "@linux_potok"
        )
        self.assertEqual(
            collect_copied_links(copied),
            [
                ("Читать полностью",
                 "https://www.omgubuntu.co.uk/2026/11/global-menu-gnome-extension"),
                ("@linux_potok", "https://t.me/linux_potok"),
            ],
        )

    def test_copied_links_ignore_unsafe_and_duplicates(self):
        copied = (
            "Статья (https://example.org/article)\\n"
            "https://example.org/article\\n"
            "Опасная (javascript:alert(1))"
        )
        self.assertEqual(
            collect_copied_links(copied),
            [("Статья", "https://example.org/article")],
        )

    def test_handles_missing_root(self):
        self.assertEqual(collect_links(None), [])


if __name__ == "__main__":
    unittest.main()
