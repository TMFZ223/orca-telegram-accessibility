# Orca Telegram Accessibility

An experimental [Orca](https://github.com/GNOME/orca) user extension that aims to make **Telegram Desktop on Linux** easier to use with a screen reader. The project is developed with blind and low-vision users in mind.

It targets Orca 51.1 and the official Telegram Desktop Linux build. Initial manual testing is intended for Telegram Desktop 7.3.3 on Debian 13 and Fedora, using MATE on X11.

> **Status: early prototype.** The link-list command is implemented as an initial vertical slice. The other requested Telegram workflows are planned and are not implemented yet. The project has not yet been validated in a live Orca + Telegram session.

## Project goals

- **Message links — `Insert+L`:** collect links exposed by the current accessible message and present them in a keyboard-operable list. Enter opens the selected HTTP(S) or mailto link in the default handler; Escape closes the dialog.
- **Message reactions — `Insert+Ctrl+R`:** provide a keyboard-accessible reaction picker.
- **Channel comments:** make comment controls and navigation accessible.
- **Bot buttons — `Insert+Ctrl+M`:** list inline/reply keyboard buttons and activate the selected button.
- **Payments:** expose payment and checkout actions with meaningful names, roles, and keyboard operation.

The first prototype includes working discovery/dialog code for the links workflow. The reaction and bot-button shortcuts currently announce that their functionality is not implemented. Channel comment and payment support remain planned.

## Compatibility targets

- Orca 51.1 user-extension API
- Telegram Desktop 7.3.3 (official Linux build)
- Debian 13 and Fedora
- MATE on X11
- Python 3, PyGObject / GTK 3, and AT-SPI2

Other versions and desktop environments are not yet verified.

## Install the prototype

From a clone of this repository, run:

```sh
sh install.sh
orca --approve-extension telegram_accessibility
orca --replace
```

The installer copies the extension package to:

```
${XDG_DATA_HOME:-~/.local/share}/orca/extensions/telegram_accessibility/
```

Orca requires explicit approval of user extensions. Re-approve the extension after updating its files, then restart Orca.

## Run the unit tests

The link-discovery helpers have tests that use lightweight AT-SPI test doubles, so they can run without starting Orca or Telegram:

```sh
python3 -m unittest discover -s tests -v
```

These tests do not replace integration testing with the real applications.

## Accessibility and implementation principles

- Prefer AT-SPI accessible roles, names, relations, text, and actions.
- Never use guessed screen coordinates as a substitute for missing accessibility information.
- Do not trigger actions unless the target and action are identifiable.
- Treat message contents and URLs as untrusted input; only open supported URI schemes.
- Keep keyboard workflows operable without a mouse and ensure dialogs close cleanly.

Telegram Desktop may expose some controls through AT-SPI and omit others depending on the widget and build. When a control is absent from the accessibility tree, the extension must report the limitation rather than pretending it can activate that control reliably.

## Development roadmap

1. Inspect and document Telegram's AT-SPI tree for messages, links, reactions, channel comments, bot keyboards, and payment controls.
2. Verify the extension loads and the link-list command works with Orca 51.1.
3. Add AT-SPI action discovery and reaction selection where Telegram exposes a reliable action.
4. Implement bot keyboard navigation and channel comment controls.
5. Investigate payment controls without interacting with or submitting any real payment during tests.
6. Add repeatable integration test notes for Debian and Fedora.

## Contributing and bug reports

Please include:
- Orca and Telegram Desktop versions.
- Distribution, desktop environment, and display server (X11 or Wayland).
- The action you performed and expected versus actual screen-reader output.
- A sanitized AT-SPI tree excerpt, if possible.

Do not include private messages, account details, authentication data, or payment information in bug reports.

## License

No license has been selected yet. Until a license is added, the repository should be treated as all-rights-reserved; do not assume that reuse or redistribution is permitted.
