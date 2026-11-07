# Orca Telegram Accessibility

An experimental Orca user extension intended to improve the accessibility of Telegram Desktop on Linux for blind and low-vision users.

The project targets Orca 51.1 and Telegram Desktop, with initial testing focused on Telegram Desktop 7.3.3 under Debian and Fedora, MATE, and X11.

## Goals

- Provide a keyboard-accessible list of links in the focused Telegram message (`Insert+L`).
- Provide a keyboard-accessible reaction picker for the selected message (`Insert+Ctrl+R`).
- Improve access to channel comment controls.
- Provide a keyboard-accessible menu for bot reply/inline buttons (`Insert+Ctrl+M`).
- Improve access to payment and checkout controls.

## Development status

**Early prototype / experimental.** The goals above describe the planned user experience; they are not a claim that every feature is implemented or verified yet.

Telegram Desktop may expose some controls through AT-SPI and omit others, depending on the widget and Telegram build. The extension should use accessible roles, names, relations, and AT-SPI actions where available. It must not rely on guessed screen coordinates as a substitute for missing accessibility information.

## Compatibility targets

- Orca 51.1
- Telegram Desktop 7.3.3 (official Linux build)
- Debian 13 and Fedora
- MATE desktop on X11
- Python 3 and AT-SPI2

Compatibility with other versions and desktop environments is not yet established.

## Planned implementation approach

1. Inspect Telegram's actual AT-SPI accessibility tree and record which controls and actions are exposed.
2. Implement small, independently testable AT-SPI discovery and link-extraction helpers.
3. Integrate keyboard commands and accessible dialogs through the supported Orca user-extension API for the target Orca version.
4. Add feature support incrementally, only where the application exposes a reliable target or action.
5. Test with Orca and Telegram Desktop on the target systems; document limitations and reproducible test cases.

## Repository layout

The implementation and test layout will be added on the `ifat_1` development branch.

## Contributing and bug reports

Please include:
- Orca version and Telegram Desktop version.
- Distribution, desktop environment, and display server (X11/Wayland).
- The relevant action and expected versus actual screen-reader output.
- If possible, a sanitized AT-SPI tree excerpt (do not include private messages, contact details, or payment information).

## License

No license has been selected yet. Until a license is added, the repository should be treated as all-rights-reserved; do not assume that reuse or redistribution is permitted.
