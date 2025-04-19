# PyMUD - Native Python MUD Client

Introduction

Beida Hero Wiki: https://www.pkuxkx.net/wiki/tools/pymud

Source Code: https://github.com/crapex/pymud

Documentation: https://pymud.readthedocs.org

PyPi Project: https://pypi.org/project/pymud

Discussion Group (QQ Group): 554672580

Beida Hero MUD (www.pkuxkx.net), the best Chinese-language MUD game!

PyMUD is a MUD client I specifically developed myself for better enjoyment of Beida Hero. PyMUD features:
	•	Fully written in native Python; requires no third-party libraries other than prompt-toolkit and its dependencies (wcwidth, pygment, pyperclip)
	•	Console-based full-screen UI design with mouse support (supports touchscreen on Android)
	•	Split-screen display supported — when data scrolls rapidly, the upper half remains static so you won’t miss any info
	•	Fixes 99% of the Chinese misalignment/display issues in Beida Hero (I haven’t explored every location, so I won’t claim 100%)
	•	Real multi-session support — switch sessions via commands or mouse
	•	Native support for multiple server-side encodings including GBK, BIG5, UTF-8
	•	Supports NWAS and MTTS negotiation, plus GMCP, MSDP, MSSP protocols
	•	Write once, run anywhere — as long as Python runs, PyMUD runs
	•	All scripting uses native Python syntax. If you know Python, you can write scripts — no need to learn Lua or struggle with app-specific tools
	•	Python’s powerful text processing is perfect for MUDs
	•	Python’s rich third-party ecosystem means you can use those libraries in PyMUD too
	•	I’m still actively playing, so this client will continue to get updates :)

Who is PyMUD for?
	•	Python-savvy coders — nothing beats PyMUD’s support for Python
	•	Beginners eager to learn Python — great opportunity to learn while writing scripts for Beida Hero
	•	Folks who think “no current client has this feature I want” — tell me your idea, and I’ll add it
	•	Tinkerers who want to build a custom client — PyMUD is fully open-source, and aside from the UI framework, every line is hand-written and easy to reference

⸻

0.20.4 (2025-03-30)
	•	Feature Update: Added PLUGIN_PYMUD_DESTROY method for plugin cleanup when a plugin is unloaded.
	•	Feature Update: Changed when the PLUGIN_PYMUD_START method is called—from plugin load time to after the event loop starts. This allows using asyncio.create_task or asyncio.ensure_future for async operations during load.

⸻

0.20.3 (2025-03-05)
	•	Feature Update: Added Shift + Left/Right Arrow as additional hotkeys for session switching on macOS.
	•	Feature Update: Occasionally when closing sessions or quitting the app, a server disconnect could go undetected due to network issues. Now it waits up to 10 seconds before force quitting.

⸻

0.20.2 (2024-11-26)
	•	Feature Update: Explicitly added 256 Color to MTTS negotiation reply (previously only ANSI and TrueColor). Suspected this might be related to rare color issues in 武庙 (Wumiao), though tests show it’s unrelated.
	•	Feature Fix: Improved plain-text regex processing — now theoretically supports all ANSI control codes to better handle text triggers.
	•	Feature Update: Improved display for #var and #global commands for better alignment and readability, even with long or complex variable values.
	•	Bug Fix: Fixed multi-line color code rendering issues — 星宿毒草 (Star Sect Poison Herb) colors now display correctly.
	•	UI Update: Adjusted styles for info/warning/error messages.
	•	New Feature: Added menu option to toggle “beautify” mode, helping copy content more precisely when triggers are involved.
	•	New Feature: Status bar divider can now be disabled via config (status_divider = false in pymud.cfg).
	•	Feature Update: buffer_lines can now be set to 0 to disable cache clearing.
	•	New Feature: Status bar display function now includes error protection — if status_maker fails, the error message will be shown in the status bar.

⸻

0.20.1 (2024-11-16)
	•	Feature Update: Optimized trigger matching to reduce loops and improve response time.
	•	Feature Update: Adjusted #test and #show trigger testing:
	•	#show: performs matching tests without triggering.
	•	#test: actually triggers matched results.
	•	New Feature: The pymud object now has a recurring 1-second timer that refreshes the UI. Developers can register callbacks using session.application.addTimerTickCallback.

⸻

0.20.0 (2024-08-25)
	•	Structural Update: Moved main entry point from __main__.py to main.py, allowing launch via pymud or python -m pymud.
	•	Command Line Update: Uses argparser for command-line configuration. Run pymud -h for options.
	•	New Feature: -s / --startup_dir allows launching from any directory by specifying script path.
	•	Example:
            PS C:\> pymud -s d:\prog\pkuxkx
            is equivalent to
            PS D:\prog\pkuxkx> pymud
	•	Bug Fix: Fixed directory creation error when running python -m pymud init on macOS. Now all systems use ~/pkuxkx as the default folder (affects Windows too).
	•	Feature Update: Re-enabled from pymud import PyMudApp via __init__.py.
	•	New Feature: Added logging support via the #log command and the Logger and Session.handle_log methods.
	•	New Feature: #disconnect / #dis command to manually disconnect the current session.
	•	Feature Update: #exit can now be used even without an active session.
	•	New Feature: #session now supports quick session creation using menu aliases, like #session pkuxkx.newstart.
	•	Feature Update: Clicking a menu to create a session now switches to that session if it already exists.
	•	Major Update: Completely rewrote module load/unload/reload logic to fix various issues.
	•	Config Overhaul:
	•	Classes that implement IConfig or are named Configuration are treated as config types and automatically instantiated.
	•	Unload logic can now go in either __unload__ or unload.
	•	Modules auto-call their unload logic before loading/reloading.
	•	Command Enhancements:
	•	Command base class now includes __unload__ and unload.
	•	Custom command classes should override one of those and clean up triggers, aliases, etc.
	•	Object Management:
	•	All base objects (Alias, Trigger, Timer, Command, GMCPTrigger) are auto-registered with the session.
	•	Bug Fix: Fixed some broken regex patterns.
	•	New Feature: Session.waitfor method simplifies waiting for a trigger:

            await self.session.waitfor('dazuo', self.create_task(self.tri1.triggered()))
	•	Feature Update: In addTriggers and similar methods, if object ID ≠ key, a warning will show.
	•	New Feature: Session.addObject, addObjects, delObject, delObjects — manage aliases, triggers, timers, etc.
	•	New Feature: Session.idletime tracks how long a session has been idle.
	•	New Feature: Async command methods like exec_async now return the result of the final command executed.
	•	New Feature: Added concept of temporary variables — variables starting with _ are not saved to .mud files.
	•	Improved Intellisense: self.session now type-hinted for better auto-completion in custom commands.
	•	Bug Fix: Fixed alignment issues with Chinese characters in #var commands.
	•	Feature Update: If an object has no group in #tri, the group property is omitted from output to reduce clutter.


Perfect — continuing on with the translated changelogs from version 0.19.4 and earlier:

⸻

0.19.4 (2024-04-20)
	•	Feature Update: The info message function now accepts any type of argument again (not limited to str).
	•	Feature Update: In #var and #global, you can now use expanded arguments, e.g., #var max_qi @qi.
	•	Feature Update: #var and #global will attempt to auto-convert string values using eval. If it fails, it defaults to string. For example: #var myvar 1 will make myvar an int.
	•	Feature Update: Variable substitution now auto-converts types, so if the substituted value isn’t a string, it won’t raise an error.
	•	Bug Fix: Fixed issue where copying text backward (from bottom to top) sometimes didn’t work.

⸻

0.19.3post2 (2024-04-05)
	•	Bug Fix: Fixed command order errors when sending multiple commands at once.
	•	New Feature: Added exec_async — an async version of exec. Allows running code asynchronously in other sessions.
	•	Help Improvements: Completed internal documentation for the entire package.
	•	Note: Because of limitations in how readthedocs.io reads GitHub source code, documentation updates will only be visible after new official releases.
	•	Bug Fix: Fixed a minor bug triggered when exiting the program.

⸻

0.19.2post2 (2024-03-24)
	•	Fixes: Corrected typos, incorrect help entries, and formatting issues.
	•	System Enhancement: Rewrote all docstrings using reStructuredText (reST) format.
	•	Feature Update: session.exec_command, exec_command_async, and exec now support variable substitution, e.g., session.exec("dazuo @dzpt").
	•	Feature Update: Added reconnect_wait to settings.py under the client dict. Controls auto-reconnect wait time (default: 15s), can be overridden locally.
	•	Feature Update: Workaround for issue where clicking the right side of the Help menu caused unexpected behavior.
	•	Bug Fix: Fixed plugin unloading errors when sessions close.
	•	Feature Update: Now waits during session close or program exit to ensure disconnect messages are received before exiting.
	•	Bug Fix: Plugin unload now correctly triggers on program exit.
	•	Implementation Update: Removed type checks during list comprehension that clears tasks to reduce processing overhead.
	•	Other: Removed reference-only files that were bundled in the package.
	•	Help Improvements: Finalized logic and layout of help documentation.
	•	Implementation Update: Switched to official sample code’s method for task cleanup (clears each task after it ends).

⸻

0.19.1 (2024-03-06)
	•	New Feature: Added mouse enable/disable toggle — useful when copying via SSH. Use F2 to toggle. A status message shows “Mouse Disabled” on the status bar.
	•	New Feature: F1 shortcut now opens the help site https://pymud.readthedocs.io/ in the browser.
	•	New Feature: Default hotkeys:
	•	F3 = #ig
	•	F4 = #cls
	•	F11 = #close
	•	F12 = #exit
These can be customized via config. F1 and F2 are hardcoded system functions.
	•	Feature Update: Moved all # commands except #session into the Session class — these commands now support session.exec_command.
	•	Feature Update: When running python -m pymud init, the generated pymud.cfg now includes a keys dictionary for custom hotkeys.

⸻

0.19.0 (2024-03-01)
	•	Implementation Update: When session.info/warning/error outputs multiline text, each line now has consistent coloring.
	•	New Feature: First-time users can run python -m pymud init to initialize the environment. This creates folders and default config/sample script files.
	•	Implementation Update: Buffer line-clear logic moved to SessionBuffer, reducing code coupling and memory usage.
	•	New Feature: #T+, #T- commands can enable/disable groups. Equivalent to session.enableGroup.
	•	New Feature: #task lists all system-managed tasks. Useful for development/testing.
	•	Implementation Update: Improved cleanup and exit for system tasks, reducing resource usage.
	•	Implementation Update: In COPY-RAW mode, partial selections auto-expand to full line (even for multi-line).
	•	New Feature: Settings.keys dictionary lets you define keybindings. Uses the prompt_toolkit keys module. Configurable via pymud.cfg.
