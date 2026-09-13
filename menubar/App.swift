// Menu bar item for the calibre daily enrich sweep.
//
// No dock icon, no window: an NSStatusItem whose menu is rebuilt every time it
// opens, from the two files daily_enrich.sh already maintains -
//   data/logs/daily-enrich.lock/pid   is it running, and as what pid
//   data/logs/daily-latest-summary.txt  what the last run moved
// so there is no second source of truth to keep in step with the script.

import Cocoa

let repoPath   = "/Users/alexchilton/CAS_NLP_Module3_Calibre_Project"
let logDir     = repoPath + "/data/logs"
let lockDir    = logDir + "/daily-enrich.lock"
let summaryFile = logDir + "/daily-latest-summary.txt"
let runner     = repoPath + "/menubar/run_daily_interactive.command"
let watcher    = repoPath + "/menubar/watch_log.command"

func todayLog() -> String {
    let f = DateFormatter()
    f.dateFormat = "yyyyMMdd"
    return logDir + "/daily-" + f.string(from: Date()) + ".log"
}

func shortTime(_ date: Date?) -> String {
    guard let date = date else { return "unknown" }
    let f = DateFormatter()
    f.dateFormat = Calendar.current.isDateInToday(date) ? "HH:mm" : "d MMM HH:mm"
    return f.string(from: date)
}

func modified(_ path: String) -> Date? {
    let attrs = try? FileManager.default.attributesOfItem(atPath: path)
    return attrs?[.modificationDate] as? Date
}

/// The lock directory alone is not proof: daily_enrich.sh clears a stale one on
/// its next start, so a crash leaves it behind. The recorded pid is the check.
func runningPid() -> Int32? {
    guard FileManager.default.fileExists(atPath: lockDir),
          let raw = try? String(contentsOfFile: lockDir + "/pid", encoding: .utf8),
          let pid = Int32(raw.trimmingCharacters(in: .whitespacesAndNewlines)),
          kill(pid, 0) == 0
    else { return nil }
    return pid
}

/// A menu bar app has nowhere to print. Without this, "it is running but I
/// cannot see it" has no evidence behind it either way.
let noteFile = "/tmp/calibre-daily-menubar.log"
func note(_ message: String) {
    let f = DateFormatter()
    f.dateFormat = "HH:mm:ss"
    let line = "\(f.string(from: Date()))  \(message)\n"
    if let data = line.data(using: .utf8) {
        if let fh = FileHandle(forWritingAtPath: noteFile) {
            fh.seekToEndOfFile()
            fh.write(data)
            try? fh.close()
        } else {
            try? data.write(to: URL(fileURLWithPath: noteFile))
        }
    }
}

func openInTerminal(_ path: String) {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
    p.arguments = ["-a", "Terminal", path]
    try? p.run()
}

func mono(_ text: String, size: CGFloat = 12, dim: Bool = false) -> NSAttributedString {
    NSAttributedString(string: text, attributes: [
        .font: NSFont.monospacedSystemFont(ofSize: size, weight: .regular),
        .foregroundColor: dim ? NSColor.secondaryLabelColor : NSColor.labelColor,
    ])
}

@main
final class Controller: NSObject, NSApplicationDelegate, NSMenuDelegate {
    // Built in applicationDidFinishLaunching, NOT in init. A status item
    // created before NSApplication finishes launching reports isVisible=true
    // and never draws, which is exactly the symptom this app had: alive,
    // sleeping, symbol resolved, nothing in the menu bar.
    var item: NSStatusItem!
    var timer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        // autosaveName only names the item; measured 2026-09-13, third-party
        // status items get no entry in com.apple.controlcenter at all. The
        // "NSStatusItem Visible Item-N" keys there belong to Apple's own
        // Control Center modules, alongside AirDrop and Battery. An earlier
        // comment here claimed those keys were hiding this item. That was wrong.
item.autosaveName = "CalibreDailyEnrich"
        item.isVisible = true
        let menu = NSMenu()
        menu.delegate = self
        item.menu = menu
        refreshIcon()
        note("launched | bundleID=\(Bundle.main.bundleIdentifier ?? "NIL")"
             + " path=\(Bundle.main.bundlePath)"
             + " policy=\(NSRunningApplication.current.activationPolicy.rawValue)"
             + " infoKeys=\(Bundle.main.infoDictionary?.count ?? -1)")
        if let s = NSScreen.main {
            note("screen | frame=\(s.frame) visible=\(s.visibleFrame)"
                 + " safeTop=\(s.safeAreaInsets.top)"
                 + " auxLeft=\(s.auxiliaryTopLeftArea.map { "\($0)" } ?? "nil")"
                 + " auxRight=\(s.auxiliaryTopRightArea.map { "\($0)" } ?? "nil")")
        }
        // Only the icon is polled. The menu itself is rebuilt on open, so a
        // closed menu costs two stat() calls every five seconds and nothing else.
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            self?.refreshIcon()
        }
    }

    func refreshIcon() {
        guard let button = item.button else {
            note("no status button - the item was not created")
            return
        }
        let running = runningPid() != nil
        let name = running ? "arrow.triangle.2.circlepath" : "books.vertical"
        // The symbol is decoration. The title is what guarantees something
        // visible, because an item with only an image that fails to resolve
        // is an invisible, unclickable gap in the menu bar.
        button.image = nil
        button.title = "CALIBRE"
        let w = button.window
        note("label set | itemVisible=\(item.isVisible)"
             + " winFrame=\(w.map { "\($0.frame)" } ?? "nil")"
             + " winOnScreen=\(w?.isVisible ?? false)"
             + " winLevel=\(w?.level.rawValue ?? -999)"
             + " alpha=\(w?.alphaValue ?? -1)"
             + " screen=\(NSScreen.main?.frame.debugDescription ?? "nil")"
             + " symbolOK=\(NSImage(systemSymbolName: name, accessibilityDescription: nil) != nil)")
        button.toolTip = running ? "calibre daily enrich - running" : "calibre daily enrich"
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let pid = runningPid()

        let header = NSMenuItem(title: "", action: nil, keyEquivalent: "")
        if let pid = pid {
            header.attributedTitle = mono("running  since \(shortTime(modified(lockDir)))  pid \(pid)")
        } else {
            header.attributedTitle = mono("idle  -  last run \(shortTime(modified(summaryFile)))", dim: true)
        }
        header.isEnabled = false
        menu.addItem(header)
        menu.addItem(.separator())

        let run = NSMenuItem(title: pid == nil ? "Run now" : "Running - open the window",
                             action: #selector(runNow), keyEquivalent: "r")
        run.target = self
        menu.addItem(run)

        let watch = NSMenuItem(title: "Watch today's log", action: #selector(watchLog), keyEquivalent: "l")
        watch.target = self
        menu.addItem(watch)

        menu.addItem(.separator())
        addSummary(to: menu)
        menu.addItem(.separator())

        let reveal = NSMenuItem(title: "Reveal logs in Finder", action: #selector(revealLogs), keyEquivalent: "")
        reveal.target = self
        menu.addItem(reveal)

        let quit = NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)
    }

    /// The summary file is the script's own output, rendered verbatim rather
    /// than re-derived here - if the script changes what it reports, this
    /// follows without an edit.
    func addSummary(to menu: NSMenu) {
        guard let text = try? String(contentsOfFile: summaryFile, encoding: .utf8) else {
            let none = NSMenuItem(title: "", action: nil, keyEquivalent: "")
            none.attributedTitle = mono("no run recorded yet", dim: true)
            none.isEnabled = false
            menu.addItem(none)
            return
        }
        for line in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let s = String(line)
            let trimmed = s.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty { continue }
            let mi = NSMenuItem(title: "", action: nil, keyEquivalent: "")
            if trimmed.hasPrefix("---") {
                let title = trimmed.replacingOccurrences(of: "--- ", with: "")
                mi.attributedTitle = mono(title.uppercased(), size: 10, dim: true)
            } else {
                mi.attributedTitle = mono("  " + trimmed)
            }
            mi.isEnabled = false
            menu.addItem(mi)
        }
    }

    @objc func runNow()      { openInTerminal(runner) }
    @objc func watchLog()    { openInTerminal(watcher) }
    @objc func revealLogs()  {
        NSWorkspace.shared.selectFile(todayLog(), inFileViewerRootedAtPath: logDir)
    }
    @objc func quit()        { NSApp.terminate(nil) }
}

