# The launcher that works

A Shortcuts shortcut named **Calibre daily**, pinned to the Dock.
Click it, a Terminal window opens and shows the sweep as it runs.

The menu bar route does not work on this machine - see README.md.
The Dock does.

## Rebuilding it

`calibre-daily.shortcut-source.plist` is the shortcut, unsigned and readable.
One `is.workflow.actions.runshellscript` action:

    open -a Terminal .../menubar/run_daily_interactive.command

To install it from scratch:

    cp calibre-daily.shortcut-source.plist /tmp/unsigned.shortcut
    shortcuts sign -m anyone -i /tmp/unsigned.shortcut -o "/tmp/Calibre daily.shortcut"
    open "/tmp/Calibre daily.shortcut"

It imports straight into the library with no dialog.

## Two things the CLI cannot do

Both are deliberate and need one click each in the Shortcuts GUI.

1. **Shortcuts - Settings - Advanced - Allow Running Scripts.**
   Without it: "this action is a scripting action and your Shortcuts security
   settings don't allow you to run scripting actions". There is no defaults key;
   Apple gates this on purpose. Note it applies to every shortcut, not just this one.
2. **Pinning.** `WFWorkflowTypes = MenuBar` in the source file is not honoured on
   import, and the library is not writable from the CLI. Pin it by hand.

## Checking it works without clicking anything

    shortcuts run "Calibre daily"

Returns immediately; the sweep runs in the Terminal window it opened.
`shortcuts list | grep -i calibre` confirms it is installed.
