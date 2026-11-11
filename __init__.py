"""Orca extension for improving Telegram Desktop accessibility."""

from orca.extension import Extension
from orca import keybindings
from orca.command import KeyboardCommand

from .links import show_links_for_current_object
from .reactions import show_reactions_for_current_object
from .diagnostics import save_accessibility_report
from .reaction_diagnostics import save_reaction_report


class TelegramAccessibilityExtension(Extension):
    """Keyboard-accessible helpers for Telegram Desktop."""

    GROUP_LABEL = "Telegram Accessibility"
    DESCRIPTION = (
        "Accessibility helpers for Telegram Desktop, beginning with "
        "a keyboard-accessible list of links in the current message."
    )
    VERSION = "0.1.0"
    AUTHOR = "TMFZ223 and contributors"
    WEBSITE = "https://github.com/TMFZ223/orca-telegram-accessibility"

    def _get_commands(self):
        return [
            KeyboardCommand(
                "telegram_list_message_links",
                self.list_message_links,
                self.GROUP_LABEL,
                "Lists links in the current Telegram message",
                desktop_keybinding=keybindings.KeyBinding(
                    "l", keybindings.ORCA_MODIFIER_MASK
                ),
                laptop_keybinding=keybindings.KeyBinding(
                    "l", keybindings.ORCA_MODIFIER_MASK
                ),
            ),
            KeyboardCommand(
                "telegram_diagnose_links",
                self.diagnose_links,
                self.GROUP_LABEL,
                "Save AT-SPI link diagnostics for the current Telegram message",
                desktop_keybinding=keybindings.KeyBinding(
                    "l", keybindings.ORCA_CTRL_MODIFIER_MASK
                ),
                laptop_keybinding=keybindings.KeyBinding(
                    "l", keybindings.ORCA_CTRL_MODIFIER_MASK
                ),
            ),
            KeyboardCommand(
                "telegram_list_reactions",
                self.list_reactions,
                self.GROUP_LABEL,
                "List and apply exposed Telegram message reactions",
                desktop_keybinding=keybindings.KeyBinding(
                    "r", keybindings.ORCA_CTRL_MODIFIER_MASK
                ),
                laptop_keybinding=keybindings.KeyBinding(
                    "r", keybindings.ORCA_CTRL_MODIFIER_MASK
                ),
            ),
            KeyboardCommand(
                "telegram_diagnose_reactions",
                self.diagnose_reactions,
                self.GROUP_LABEL,
                "Save read-only AT-SPI reaction diagnostics for the focused message",
                desktop_keybinding=keybindings.KeyBinding(
                    "r", (keybindings.ORCA_CTRL_MODIFIER_MASK | keybindings.SHIFT_MODIFIER_MASK)
                ),
                laptop_keybinding=keybindings.KeyBinding(
                    "r", (keybindings.ORCA_CTRL_MODIFIER_MASK | keybindings.SHIFT_MODIFIER_MASK)
                ),
            ),
            KeyboardCommand(
                "telegram_bot_buttons",
                self.bot_buttons_not_implemented,
                self.GROUP_LABEL,
                "Bot button menu (planned; not implemented yet)",
                desktop_keybinding=keybindings.KeyBinding(
                    "m", keybindings.ORCA_CTRL_MODIFIER_MASK
                ),
                laptop_keybinding=keybindings.KeyBinding(
                    "m", keybindings.ORCA_CTRL_MODIFIER_MASK
                ),
            ),
        ]

    def list_message_links(self) -> bool:
        obj = self.controller.get_current_object_internal()
        show_links_for_current_object(obj, self.controller)
        return True

    def diagnose_links(self) -> bool:
        obj = self.controller.get_current_object_internal()
        try:
            path = save_accessibility_report(obj)
            self.controller.present_message_internal(
                "Telegram accessibility report saved to " + str(path)
            )
        except Exception:
            self.controller.present_message_internal(
                "Could not save Telegram accessibility report."
            )
        return True

    def list_reactions(self) -> bool:
        obj = self.controller.get_current_object_internal()
        show_reactions_for_current_object(obj, self.controller)
        return True

    def diagnose_reactions(self) -> bool:
        obj = self.controller.get_current_object_internal()
        try:
            path = save_reaction_report(obj)
            self.controller.present_message_internal(
                "Telegram reaction report saved to " + str(path)
            )
        except Exception:
            self.controller.present_message_internal(
                "Could not save Telegram reaction diagnostics."
            )
        return True

    def bot_buttons_not_implemented(self) -> bool:
        self.controller.present_message_internal(
            "Telegram bot button menu is not implemented yet."
        )
        return True
