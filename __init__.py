"""Orca extension for improving Telegram Desktop accessibility."""

from orca.extension import Extension
from orca import keybindings
from orca.command import KeyboardCommand

from .links import show_links_for_current_object


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

    def __init__(self) -> None:
        super().__init__()
        self.mark_as_user_extension("telegram_accessibility")

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
                "telegram_list_reactions",
                self.reactions_not_implemented,
                self.GROUP_LABEL,
                "Reaction picker (planned; not implemented yet)",
                desktop_keybinding=keybindings.KeyBinding(
                    "r", keybindings.ORCA_CTRL_MODIFIER_MASK
                ),
                laptop_keybinding=keybindings.KeyBinding(
                    "r", keybindings.ORCA_CTRL_MODIFIER_MASK
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

    def reactions_not_implemented(self) -> bool:
        self.controller.present_message_internal(
            "Telegram reaction picker is not implemented yet."
        )
        return True

    def bot_buttons_not_implemented(self) -> bool:
        self.controller.present_message_internal(
            "Telegram bot button menu is not implemented yet."
        )
        return True
