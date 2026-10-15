# SiteLens terminal design

The canonical cover depicts a brass survey instrument over a midnight atlas. The CLI uses that language through a quiet fieldwork workspace, parchment copy, brass section headings, and cyan focus. Artwork remains unchanged.

| Token | Color | Role |
| --- | --- | --- |
| Midnight | `#061c2c` | Screen background |
| Deep water | `#102e40` | Inputs and notes |
| Parchment | `#f5e7c8` | Main text |
| Signal cyan | `#71d7e6` | Focus and primary actions |
| Brass | `#d6b879` | Brand and section headings |
| Error | `#ffb5ad` | Error accent, always accompanied by text |

Typography inherits the terminal font and zoom. Bold text and spacing establish hierarchy; the application never changes terminal or desktop configuration. There are no animated decorations. Comfortable and compact density support different window sizes and preferences.

Plan crawl, Field notes, and Appearance are separate tabs. Advanced request and report settings collapse behind a descriptive label. The workspace is centered at a maximum width of 96 terminal columns. Start, Stop, and a fixed-slot keyboard guide live in a separate bottom dock. The guide changes between two and four rows only on window resize; content length, focus, and tab selection cannot move its slots. Main limit fields use two columns on wide windows and one on narrow windows. Presets fill editable settings; custom CLI limits survive initialization. Counts describe collected, failed, queued, and scheduled URLs rather than implying a known total crawl size. Field notes retain the latest 500 lines; full failures can be exported through the error report setting.

Log events enter a bounded queue and flush in one batch every 200 ms. Unchanged counters do not redraw, and scrolling up preserves the reading position. Display overflow is summarized without affecting exported data. Help is a modal dialog and completion does not steal focus.

All controls support keyboard navigation and mouse activation. Select choices use arrows; Tab and Shift+Tab move focus. Visible labels and textual states prevent color-only communication. Light, high contrast, terminal-color, NO_COLOR, and linear command modes provide alternatives. Screen-reader compatibility requires testing with actual assistive technology; a full-screen TUI alone cannot establish universal accessibility.

The interface uses Textual's widget, theme, and focus systems: https://textual.textualize.io/guide/widgets/ and https://textual.textualize.io/guide/design/. Crawl policy lives in AsyncCrawler; the optional on_event callback supplies status without coupling crawling to terminal widgets.
