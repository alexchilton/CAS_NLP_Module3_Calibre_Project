# menubar - does not work on macOS 26.6.2

CalibreDaily.app builds, installs, runs, and registers its status item.
The icon never appears in the menu bar.
This is an OS bug, not a bug in this code, and it is not worked around here.

## Do not retry these

Each was measured on 2026-09-13 against macOS 26.6.2 (Darwin 25.6.0, build 25G83).

| Tried | Result |
| --- | --- |
| Status item created in `applicationDidFinishLaunching` rather than before `run()` | no change |
| `autosaveName` set, to avoid a generic `Item-N` slot | no change |
| `NSPrincipalClass`, `NSHighResolutionCapable`, `CFBundleVersion` added to Info.plist | no change |
| Regular app with a dock tile instead of `LSUIElement` | no change |
| Launched outside the agent sandbox | no change |
| `killall ControlCenter` | no change |
| `@main` / `NSApplicationMain` instead of a manual `NSApplication.run()` | no change |
| A 12-line minimal `NSStatusItem` app, same bundle and signing | **also invisible** |

That last row is the one that matters.
A textbook minimal status item app fails identically, so nothing in this source is responsible.

## What the system actually does

Control Center accepts the item and then never paints it.
From the unified log, `appStatusItems` subsystem:

    Host properties initialized (bid:...CalibreDailyEnrich-68601)
      State(applicationItem: true, clientRequestsVisibility: true, neverClip: false)
    Created new displayable type DisplayableAppStatusItemType(...)
    Created instance DisplayableId(A1513392) in .menuBar

In-process state is perfect throughout: `isVisible=true`, window non-nil,
`level=25`, `alpha=1.0`, frame `(116, 949, 73, 33)` which is inside the menu bar
band on a 1512x982 screen.
The compositing decision happens a process hop away and fails silently.

`.ephemeral` positioning in that log is a red herring: a bare minimal test binary
gets the same classification, so it is the default for any third-party item
without a permanent slot, not a fault signal.

## Not the cause

- The notch, and menu bar crowding. After freeing space the item sat at a fully
  on-screen position clear of the notch band and still did not draw.
- SF Symbol resolution. A plain text title is equally invisible.
- A menu bar manager. None is installed.
- `com.apple.controlcenter`'s `NSStatusItem Visible Item-N = 0` keys. Those belong
  to Apple's own Control Center modules, alongside AirDrop and Battery. Third-party
  items get no entry in that domain at all, with or without `autosaveName`.
- Ad-hoc signing. Notarized shipping apps hit the same symptom.

## Upstream

Same symptom, same OS, in shipping notarized apps:

- steipete/CodexBar#3377 - reported against 26.6.2 specifically
- p0deje/Maccy#1224, exelban/stats#3120, and BetterDisplay

Apple DTS (forums thread 794920) separately advises against bypassing
`NSApplicationMain()`. That advice was followed here and changed nothing.

## What is used instead

A Shortcuts shortcut pinned to the DOCK - see shortcut.md. Pinning it to the
menu bar fails the same way this app does: the icon appears and then drops out,
because the Shortcuts menu bar extra uses the same appStatusItems path. It runs
`run_daily_interactive.command`, which is the live part of this directory.
