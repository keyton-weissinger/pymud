import asyncio
import functools
import os
import threading
import webbrowser
from datetime import datetime
from enum import Enum

from prompt_toolkit import HTML
from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.filters import (
    Condition,
    is_true,
    to_filter,
)
from prompt_toolkit.formatted_text import (
    Template,
)
from prompt_toolkit.key_binding import KeyBindings, KeyPress, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    Float,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import (
    DisplayMultipleCursors,
    HighlightSearchProcessor,
    HighlightSelectionProcessor,
)
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.shortcuts import set_title
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Label, MenuItem, TextArea

from .dialogs import (
    LogSelectionDialog,
    MessageDialog,
    NewSessionDialog,
    QueryDialog,
    WelcomeDialog,
)
from .extras import (
    DotDict,
    EasternMenuContainer,
    MudFormatProcessor,
    SessionBuffer,
    SessionBufferControl,
    VSplitWindow,
)
from .modules import Plugin
from .objects import CodeBlock
from .session import Session
from .settings import Settings


class STATUS_DISPLAY(Enum):
    NONE = 0
    HORIZON = 1
    VERTICAL = 2
    FLOAT = 3


class PyMudApp:
    """
    Main management object for the PYMUD program, managing windows, operations, and all sessions.

    The PyMudApp object does not need to be created manually; an instance is automatically created when executing ``python -m pymud`` in the command line.

    Parameters:
        - ``cfg_data``: Alternative configuration data, read from the local `pymud.cfg` file, used to override the default Settings data in `settings.py`.

    Alternative dictionaries: For meanings, please refer to `Application Configuration and Localization <settings.html>`_
        - sessions: Dictionary used to create session menu items.
        - client: Dictionary used to configure client properties.
        - text: Dictionary for various default display text content.
        - server: Configuration dictionary for server options.
        - styles: Dictionary for defining display styles.
        - keys: Dictionary for defining shortcut keys.

    *Alternative configurations are updated using `dict.update` for each dictionary, so only the parts to be replaced need to be specified.*
    """

    def __init__(self, cfg_data=None) -> None:
        """
        Constructs a PyMudApp object instance and loads alternative configurations.
        """

        if cfg_data and isinstance(cfg_data, dict):
            for key in cfg_data.keys():
                if key == "sessions":
                    Settings.sessions = cfg_data[key]
                elif key == "client":
                    Settings.client.update(cfg_data[key])
                elif key == "text":
                    Settings.text.update(cfg_data[key])
                elif key == "server":
                    Settings.server.update(cfg_data[key])
                elif key == "styles":
                    Settings.styles.update(cfg_data[key])
                elif key == "keys":
                    Settings.keys.update(cfg_data[key])

        self._mouse_support = True
        self._plugins = DotDict()  # Add plugin dictionary
        self._globals = DotDict()  # Add global variables used by all sessions
        self._onTimerCallbacks = dict()
        self.sessions = {}
        self.current_session = None
        self.status_display = STATUS_DISPLAY(Settings.client["status_display"])

        self.keybindings = KeyBindings()
        self.keybindings.add(Keys.PageUp, is_global=True)(self.page_up)
        self.keybindings.add(Keys.PageDown, is_global=True)(self.page_down)
        self.keybindings.add(Keys.ControlZ, is_global=True)(self.hide_history)
        self.keybindings.add(Keys.ControlC, is_global=True)(
            self.copy_selection
        )  # Control-C Copy text
        self.keybindings.add(Keys.ControlR, is_global=True)(
            self.copy_selection
        )  # Control-R Copy text with ANSI markers (suitable for whole line copying)
        self.keybindings.add(Keys.Right, is_global=True)(
            self.complete_autosuggest
        )  # Right arrow completes suggestion
        self.keybindings.add(Keys.Backspace)(self.delete_selection)
        self.keybindings.add(Keys.ControlLeft, is_global=True)(
            self.change_session
        )  # Control-Left/Right arrow switches current session
        self.keybindings.add(Keys.ControlRight, is_global=True)(self.change_session)
        self.keybindings.add(Keys.ShiftLeft, is_global=True)(
            self.change_session
        )  # Shift-Left/Right arrow switches current session
        self.keybindings.add(Keys.ShiftRight, is_global=True)(
            self.change_session
        )  # Adapt for MacOS system
        self.keybindings.add(Keys.F1, is_global=True)(
            lambda event: webbrowser.open(Settings.__website__)
        )
        self.keybindings.add(Keys.F2, is_global=True)(self.toggle_mousesupport)

        used_keys = [
            Keys.PageUp,
            Keys.PageDown,
            Keys.ControlZ,
            Keys.ControlC,
            Keys.ControlR,
            Keys.Up,
            Keys.Down,
            Keys.Left,
            Keys.Right,
            Keys.ControlLeft,
            Keys.ControlRight,
            Keys.Backspace,
            Keys.Delete,
            Keys.F1,
            Keys.F2,
        ]

        for key, binding in Settings.keys.items():
            if (key not in used_keys) and binding and isinstance(binding, str):
                self.keybindings.add(key, is_global=True)(self.custom_key_press)

        self.initUI()

        # Handle the clipboard; testing shows pyperclip is unusable in termux under android, so use the default InMemoryClipboard
        clipboard = None
        try:
            clipboard = PyperclipClipboard()
            clipboard.set_text("test pyperclip")
            clipboard.set_text("")
        except:
            clipboard = None

        self.app = Application(
            layout=Layout(self.root_container, focused_element=self.commandLine),
            enable_page_navigation_bindings=True,
            style=self.style,
            mouse_support=to_filter(self._mouse_support),
            full_screen=True,
            color_depth=ColorDepth.TRUE_COLOR,
            clipboard=clipboard,
            key_bindings=self.keybindings,
            cursor=CursorShape.BLINKING_UNDERLINE,
        )

        set_title("{} {}".format(Settings.__appname__, Settings.__version__))
        self.set_status(
            Settings.text["welcome"]
        )  # Assuming Settings.text["welcome"] is already English or configured elsewhere

        self.loggers = dict()  # All logger dictionary
        self.showLog = False  # Whether to display the log page
        self.logFileShown = ""  # Log file name displayed on the log page
        self.logSessionBuffer = SessionBuffer()
        self.logSessionBuffer.name = "LOGBUFFER"

        self.load_plugins()

    async def onSystemTimerTick(self):
        while True:
            await asyncio.sleep(1)
            self.app.invalidate()
            for callback in self._onTimerCallbacks.values():
                if callable(callback):
                    callback()

    def addTimerTickCallback(self, name, func):
        "Registers a system timer callback, triggered once per second. Specify `name` as the callback function keyword and `func` as the callback function."
        if callable(func) and (name not in self._onTimerCallbacks.keys()):
            self._onTimerCallbacks[name] = func

    def removeTimerTickCallback(self, name):
        "Removes a callback function from the system timer callbacks. Specify `name` as the callback function keyword."
        if name in self._onTimerCallbacks.keys():
            self._onTimerCallbacks.pop(name)

    def initUI(self):
        """Initialize the UI interface"""
        self.style = Style.from_dict(Settings.styles)
        self.status_message = ""
        self.showHistory = False
        self.wrap_lines = True

        self.commandLine = TextArea(
            prompt=self.get_input_prompt,
            multiline=False,
            accept_handler=self.enter_pressed,
            height=D(min=1),
            auto_suggest=AutoSuggestFromHistory(),
            focus_on_click=True,
            name="input",
        )

        self.status_bar = VSplit(
            [
                Window(
                    FormattedTextControl(self.get_statusbar_text),
                    style="class:status",
                    align=WindowAlign.LEFT,
                ),
                Window(
                    FormattedTextControl(self.get_statusbar_right_text),
                    style="class:status.right",
                    width=D(preferred=40),
                    align=WindowAlign.RIGHT,
                ),
            ],
            height=1,
            style="class:status",
        )

        # Add status window display
        self.statusView = FormattedTextControl(
            text=self.get_statuswindow_text, show_cursor=False
        )

        self.mudFormatProc = MudFormatProcessor()

        self.consoleView = SessionBufferControl(
            buffer=None,
            input_processors=[
                self.mudFormatProc,
                HighlightSearchProcessor(),
                HighlightSelectionProcessor(),
                DisplayMultipleCursors(),
            ],
            focus_on_click=False,
        )

        self.console = VSplitWindow(
            content=self.consoleView,
            width=D(preferred=Settings.client["naws_width"]),
            height=D(preferred=Settings.client["naws_height"]),
            wrap_lines=Condition(lambda: is_true(self.wrap_lines)),
            # left_margins=[NumberedMargin()],
            # right_margins=[ScrollbarMargin(True)],
            style="class:text-area",
        )

        console_with_bottom_status = ConditionalContainer(
            content=HSplit(
                [
                    self.console,
                    ConditionalContainer(
                        content=Window(char="—", height=1),
                        filter=Settings.client["status_divider"],
                    ),
                    # Window(char = "—", height = 1),
                    Window(
                        content=self.statusView, height=Settings.client["status_height"]
                    ),
                ]
            ),
            filter=to_filter(self.status_display == STATUS_DISPLAY.HORIZON),
        )

        console_with_right_status = ConditionalContainer(
            content=VSplit(
                [
                    self.console,
                    ConditionalContainer(
                        content=Window(char="|", width=1),
                        filter=Settings.client["status_divider"],
                    ),
                    Window(
                        content=self.statusView, width=Settings.client["status_width"]
                    ),
                ]
            ),
            filter=to_filter(self.status_display == STATUS_DISPLAY.VERTICAL),
        )

        console_without_status = ConditionalContainer(
            content=self.console,
            filter=to_filter(self.status_display == STATUS_DISPLAY.NONE),
        )

        body = HSplit(
            [
                console_without_status,
                console_with_right_status,
                console_with_bottom_status,
            ]
        )

        fill = functools.partial(Window, style="class:frame.border")
        top_row_with_title = VSplit(
            [
                # fill(width=1, height=1, char=Border.TOP_LEFT),
                fill(char="\u2500"),
                fill(width=1, height=1, char="|"),
                # Notice: we use `Template` here, because `self.title` can be an
                # `HTML` object for instance.
                Label(
                    lambda: Template(" {} ").format(self.get_frame_title),
                    style="class:frame.label",
                    dont_extend_width=True,
                ),
                fill(width=1, height=1, char="|"),
                fill(char="\u2500"),
                # fill(width=1, height=1, char=Border.TOP_RIGHT),
            ],
            height=1,
        )

        new_body = HSplit(
            [
                top_row_with_title,
                body,
                fill(height=1, char="\u2500"),
            ]
        )

        # self.console_frame = Frame(body = body, title = self.get_frame_title)

        self.body = HSplit(
            [
                new_body,
                # self.console_frame,
                self.commandLine,
                self.status_bar,
            ]
        )

        # Assume Settings.text values are either already English or configured elsewhere to be English
        self.root_container = EasternMenuContainer(
            body=self.body,
            menu_items=[
                MenuItem(
                    Settings.text.get("world", "World"),  # Use default if missing
                    children=self.create_world_menus(),
                ),
                MenuItem(
                    Settings.text.get("session", "Session"),
                    children=[
                        MenuItem(
                            Settings.text.get("connect", "Connect"),
                            handler=self.act_connect,
                        ),
                        MenuItem(
                            Settings.text.get("disconnect", "Disconnect"),
                            handler=self.act_discon,
                        ),
                        MenuItem(
                            Settings.text.get("closesession", "Close Session"),
                            handler=self.act_close_session,
                        ),
                        MenuItem(
                            Settings.text.get("autoreconnect", "Auto Reconnect"),
                            handler=self.act_autoreconnect,
                        ),
                        MenuItem("-", disabled=True),
                        MenuItem(
                            Settings.text.get("nosplit", "Cancel Split/Selection"),
                            handler=self.act_nosplit,
                        ),
                        MenuItem(
                            Settings.text.get("echoinput", "Echo Input"),
                            handler=self.act_echoinput,
                        ),
                        MenuItem(
                            Settings.text.get("beautify", "Beautify Display"),
                            handler=self.act_beautify,
                        ),
                        MenuItem(
                            Settings.text.get("copy", "Copy"), handler=self.act_copy
                        ),
                        MenuItem(
                            Settings.text.get("copyraw", "Copy Raw"),
                            handler=self.act_copyraw,
                        ),
                        MenuItem(
                            Settings.text.get("clearsession", "Clear Session"),
                            handler=self.act_clearsession,
                        ),
                        MenuItem("-", disabled=True),
                        MenuItem(
                            Settings.text.get("reloadconfig", "Reload Config/Scripts"),
                            handler=self.act_reload,
                        ),
                    ],
                ),
                # MenuItem(
                #     Settings.text.get("layout", "Layout"),
                #     children = [
                #         MenuItem(Settings.text.get("hide", "Hide Status"), handler = functools.partial(self.act_change_layout, False)),
                #         MenuItem(Settings.text.get("horizon", "Horizontal Status"), handler = functools.partial(self.act_change_layout, True)),
                #         MenuItem(Settings.text.get("vertical", "Vertical Status"), handler = functools.partial(self.act_change_layout, True)),
                #     ]
                # ),
                MenuItem(
                    Settings.text.get("help", "Help"),
                    children=[
                        MenuItem(
                            Settings.text.get("about", "About"), handler=self.act_about
                        )
                    ],
                ),
                MenuItem(
                    "",  # Add an empty name MenuItem; clicking it moves focus to the command line input, preventing clicks on the right blank bar from responding
                    handler=lambda: self.app.layout.focus(self.commandLine),
                ),
            ],
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=16, scroll_offset=1),
                )
            ],
        )

    def create_world_menus(self):
        "Creates the World submenu, including session-related submenus based on the configuration in the local `pymud.cfg`."
        menus = []
        # Assume Settings.text values are either already English or configured elsewhere to be English
        menus.append(
            MenuItem(
                Settings.text.get("new_session", "New Session"), handler=self.act_new
            )
        )
        menus.append(MenuItem("-", disabled=True))

        ss = Settings.sessions

        for key, site in ss.items():
            menu = MenuItem(key)
            for name in site["chars"].keys():
                sub = MenuItem(
                    name, handler=functools.partial(self._quickHandleSession, key, name)
                )
                menu.children.append(sub)
            menus.append(menu)

        menus.append(MenuItem("-", disabled=True))
        menus.append(
            MenuItem(
                Settings.text.get("show_log", "Show Log"),
                handler=self.show_logSelectDialog,
            )
        )
        menus.append(MenuItem("-", disabled=True))
        menus.append(MenuItem(Settings.text.get("exit", "Exit"), handler=self.act_exit))

        return menus

    def invalidate(self):
        "Refresh the display interface"
        self.app.invalidate()

    def scroll(self, lines=1):
        "Scroll content by the specified number of lines. Less than 0 scrolls up, greater than 0 scrolls down."
        b = None  # Initialize b
        if self.current_session:
            s = self.current_session
            b = s.buffer
        elif self.showLog:
            b = self.logSessionBuffer

        if isinstance(b, Buffer):
            if lines < 0:
                b.cursor_up(-1 * lines)
            elif lines > 0:
                b.cursor_down(lines)

    def page_up(self, event: KeyPressEvent) -> None:
        "Shortcut Key PageUp: Used to scroll up one page. The number of lines scrolled is half the display window height minus one."
        # lines = (self.app.output.get_size().rows - 5) // 2 - 1
        lines = self.get_height() // 2 - 1
        self.scroll(-1 * lines)

    def page_down(self, event: KeyPressEvent) -> None:
        "Shortcut Key PageDown: Used to scroll down one page. The number of lines scrolled is half the display window height minus one."
        # lines = (self.app.output.get_size().rows - 5) // 2 - 1
        lines = self.get_height() // 2 - 1
        self.scroll(lines)

    def custom_key_press(self, event: KeyPressEvent):
        "Implementation for custom shortcut keys. Executes specified commands in the current session based on the `keys` dictionary configuration."
        if (len(event.key_sequence) == 1) and (
            event.key_sequence[-1].key in Settings.keys.keys()
        ):
            cmd = Settings.keys[event.key_sequence[-1].key]
            if self.current_session:
                self.current_session.exec_command(cmd)

    def hide_history(self, event: KeyPressEvent) -> None:
        """Shortcut Key Ctrl+Z: Close history line display / Cancel split/selection."""
        self.act_nosplit()

    def copy_selection(self, event: KeyPressEvent) -> None:
        """Shortcut Key Ctrl+C/Ctrl+R: Copy selected content. Selects text copy mode or RAW copy mode based on the key pressed."""
        if event.key_sequence[-1].key == Keys.ControlC:
            self.copy()
        elif event.key_sequence[-1].key == Keys.ControlR:
            self.copy(raw=True)

    def delete_selection(self, event: KeyPressEvent):
        event.key_sequence
        b = event.current_buffer
        if b.selection_state:
            event.key_processor.feed(KeyPress(Keys.Delete), first=True)
        else:
            b.delete_before_cursor(1)

    def complete_autosuggest(self, event: KeyPressEvent):
        """Shortcut Key Right Arrow →: Autocomplete suggestion."""
        b = event.current_buffer
        if b.cursor_position == len(b.text):
            s = b.auto_suggest.get_suggestion(b, b.document)
            if s:
                b.insert_text(s.text, fire_event=False)
        else:
            b.cursor_right()

    def change_session(self, event: KeyPressEvent):
        """Shortcut Key Ctrl/Shift + Left/Right Arrow: Switch sessions."""
        current = None
        keys = list(self.sessions.keys())
        count = len(keys)

        if self.current_session:
            current = self.current_session.name
            idx = keys.index(current)

            if (event.key_sequence[-1].key == Keys.ControlRight) or (
                event.key_sequence[-1].key == Keys.ShiftRight
            ):
                if idx < count - 1:
                    new_key = keys[idx + 1]
                    self.activate_session(new_key)
                elif (idx == count - 1) and self.showLog:
                    self.showLogInTab()  # Switch to log tab if it's the "next" one

            elif (event.key_sequence[-1].key == Keys.ControlLeft) or (
                event.key_sequence[-1].key == Keys.ShiftLeft
            ):
                if (
                    self.showLog and idx == 0
                ):  # If log is shown and we are at first session, go to log
                    self.showLogInTab()
                elif idx > 0:
                    new_key = keys[idx - 1]
                    self.activate_session(new_key)

        elif self.showLog:  # If no current session, we must be on the log tab
            if (event.key_sequence[-1].key == Keys.ControlLeft) or (
                event.key_sequence[-1].key == Keys.ShiftLeft
            ):
                if count > 0:
                    new_key = keys[-1]  # Go to the last session
                    self.activate_session(new_key)
            # ControlRight while on log does nothing if there are no sessions

    def toggle_mousesupport(self, event: KeyPressEvent):
        """Shortcut Key F2: Toggle mouse support status. Useful for local copy command execution during remote connections."""
        self._mouse_support = not self._mouse_support
        if self._mouse_support:
            self.app.renderer.output.enable_mouse_support()
        else:
            self.app.renderer.output.disable_mouse_support()

    def copy(self, raw=False):
        """
        Copy selected content in the session.

        :param raw: Specify whether to use text mode or ANSI format mode.

        ``Note: The copied content only exists in the runtime environment's clipboard. If using SSH remotely, this copy command cannot access the local clipboard.``
        """

        b = self.consoleView.buffer
        if b and b.selection_state:  # Check if buffer exists and has selection
            cur1, cur2 = (
                b.selection_state.original_cursor_position,
                b.document.cursor_position,
            )
            start, end = min(cur1, cur2), max(cur1, cur2)
            srow, scol = b.document.translate_index_to_position(start)
            erow, ecol = b.document.translate_index_to_position(end)
            # srow, scol = b.document.translate_index_to_position(b.selection_state.original_cursor_position)
            # erow, ecol = b.document.translate_index_to_position(b.document.cursor_position)

            if not raw:
                # Control-C Copy plain text
                if srow == erow:
                    # Single line case
                    # line = b.document.current_line
                    line = self.mudFormatProc.line_correction(b.document.current_line)
                    start_pos = max(0, scol)  # Use start_pos instead of start
                    end_pos = min(ecol, len(line))  # Use end_pos instead of end
                    # line_plain = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line, flags = re.IGNORECASE).replace("\r", "").replace("\x00", "")
                    line_plain = (
                        Session.PLAIN_TEXT_REGX.sub("", line)
                        .replace("\r", "")
                        .replace("\x00", "")
                    )
                    # line_plain = re.sub("\x1b\\[[^mz]+[mz]", "", line).replace("\r", "").replace("\x00", "")
                    selection = line_plain[start_pos:end_pos]  # Use corrected start/end
                    self.app.clipboard.set_text(selection)
                    self.set_status("Copied: {}".format(selection))
                    if self.current_session:
                        self.current_session.setVariable("%copy", selection)
                else:
                    # Multi-line considers only lines
                    lines = []
                    for row in range(srow, erow + 1):
                        line = b.document.lines[row]
                        # line_plain = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line, flags = re.IGNORECASE).replace("\r", "").replace("\x00", "")
                        line_plain = (
                            Session.PLAIN_TEXT_REGX.sub("", line)
                            .replace("\r", "")
                            .replace("\x00", "")
                        )
                        lines.append(line_plain)

                    self.app.clipboard.set_text("\n".join(lines))
                    self.set_status("Copied: {} lines".format(1 + erow - srow))

                    if self.current_session:
                        self.current_session.setVariable("%copy", "\n".join(lines))

            else:
                # Control-R Copy original content with ANSI markers (character relationships might be incorrect, so RAW copy automatically copies whole lines)
                if srow == erow:
                    line = b.document.current_line
                    self.app.clipboard.set_text(line)
                    self.set_status(
                        "Copied: {}".format(line)
                    )  # Might show raw ANSI codes here

                    if self.current_session:
                        self.current_session.setVariable("%copy", line)

                else:
                    lines = b.document.lines[srow : erow + 1]
                    copy_raw_text = "".join(
                        lines
                    )  # Join with newline? Maybe not for raw. Original didn't.
                    self.app.clipboard.set_text(copy_raw_text)
                    self.set_status(
                        "Copied: {} lines".format(1 + erow - srow)
                    )  # Might show raw ANSI codes here

                    if self.current_session:
                        self.current_session.setVariable("%copy", copy_raw_text)

                # data = self.consoleView.buffer.copy_selection()
                # self.app.clipboard.set_data(data)
                # self.set_status("Copied: {}".format(data.text)) # Might show raw ANSI codes here

                # self.current_session.setVariable("%copy", data.text)
        else:
            self.set_status("Nothing selected...")

    def create_session(
        self,
        name,
        host,
        port,
        encoding=None,
        after_connect=None,
        scripts=None,
        userid=None,
    ):
        """
        Creates a session. Both the menu and the `#session` command call this function to create a session.

        :param name: Session name
        :param host: Server domain name or IP address
        :param port: Port number
        :param encoding: Server encoding
        :param after_connect: Content to send to the server after connecting, used for automatic login functionality.
        :param scripts: List of scripts to load.
        :param userid: Auto-login ID (obtained from definitions in the cfg file, bound to the menu), this value will be used to create a variable named 'id' in this session.
        """
        result = False
        encoding = encoding or Settings.server["default_encoding"]

        if name not in self.sessions.keys():
            session = Session(
                self, name, host, port, encoding, after_connect, scripts=scripts
            )
            session.setVariable("id", userid)
            self.sessions[name] = session
            self.activate_session(name)

            for plugin in self._plugins.values():
                if isinstance(plugin, Plugin):
                    plugin.onSessionCreate(session)

            result = True
        else:
            self.set_status(
                f"Error! A session named {name} already exists, please try a different name."
            )

        return result

    def show_logSelectDialog(self):
        async def coroutine():
            # Use English headers
            head_line = "   {}{}{}".format(
                "Log Filename".ljust(15),
                "File Size".rjust(16),
                "Last Modified Time".center(17),
            )

            log_list = list()
            files = [
                f for f in os.listdir(".") if os.path.isfile(f) and f.endswith(".log")
            ]
            for file in files:
                file_path = os.path.abspath(file)  # Use different variable name
                filename = os.path.basename(file_path).ljust(20)
                filesize = f"{os.path.getsize(file_path):,} Bytes".rjust(20)
                # ctime   = datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S').rjust(23)
                mtime = (
                    datetime.fromtimestamp(os.path.getmtime(file_path))
                    .strftime("%Y-%m-%d %H:%M:%S")
                    .rjust(23)
                )

                file_display_line = "{}{}{}".format(filename, filesize, mtime)
                log_list.append((file_path, file_display_line))  # Store full path

            logDir = os.path.abspath(os.path.join(os.curdir, "log"))
            if os.path.exists(logDir):
                files = [f for f in os.listdir(logDir) if f.endswith(".log")]
                for file in files:
                    file_path = os.path.join(
                        logDir, file
                    )  # Use different variable name
                    filename = ("log/" + os.path.basename(file_path)).ljust(20)
                    filesize = f"{os.path.getsize(file_path):,} Bytes".rjust(20)
                    # ctime   = datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S').rjust(23)
                    mtime = (
                        datetime.fromtimestamp(os.path.getmtime(file_path))
                        .strftime("%Y-%m-%d %H:%M:%S")
                        .rjust(23)
                    )

                    file_display_line = "{}{}{}".format(filename, filesize, mtime)
                    log_list.append((file_path, file_display_line))  # Store full path

            dialog = LogSelectionDialog(text=head_line, values=log_list)

            result = await self.show_dialog_as_float(dialog)

            if result:
                self.logFileShown = result  # result should be the full path now
                self.showLogInTab()

        asyncio.ensure_future(coroutine())

    def showLogInTab(self):
        "Display LOG records in the log tab."
        self.showLog = True
        self.current_session = None  # Deactivate current session when viewing log

        if self.logFileShown:
            filename = os.path.abspath(self.logFileShown)
            if os.path.exists(filename):
                lock = threading.RLock()
                lock.acquire()
                try:
                    with open(filename, "r", encoding="utf-8", errors="ignore") as file:
                        self.logSessionBuffer._set_text(file.read())
                finally:
                    lock.release()  # Ensure lock is released even if error occurs

                self.logSessionBuffer.cursor_position = len(
                    self.logSessionBuffer.text
                )  # Move cursor to end
                self.consoleView.buffer = self.logSessionBuffer
                self.app.invalidate()
            else:
                self.logSessionBuffer._set_text(f"Log file not found: {filename}")
                self.consoleView.buffer = self.logSessionBuffer
                self.app.invalidate()
        else:
            self.logSessionBuffer._set_text("No log file selected.")
            self.consoleView.buffer = self.logSessionBuffer
            self.app.invalidate()

    def activate_session(self, key):
        "Activates the session with the specified name and sets it as the current session."
        session = self.sessions.get(key, None)

        if isinstance(session, Session):
            self.current_session = session
            self.consoleView.buffer = session.buffer
            self.showLog = False  # Ensure log view is deactivated
            # self.set_status("Session changed to {}".format(session.name)) # Already in English
            self.app.invalidate()

    def close_session(self):
        "Closes the current session. If the current session is connected, a dialog box will pop up for confirmation."

        async def coroutine():
            if self.current_session:
                if self.current_session.connected:
                    # Use English text for dialog
                    dlgQuery = QueryDialog(
                        HTML('<b fg="red">Warning</b>'),
                        HTML(
                            '<style fg="red">Current session {0} is still connected. Confirm closing?</style>'.format(
                                self.current_session.name
                            )
                        ),
                    )
                    result = await self.show_dialog_as_float(dlgQuery)
                    if result:
                        self.current_session.disconnect()

                        # Add delay to ensure session closure
                        wait_time = 0
                        while self.current_session.connected:
                            await asyncio.sleep(0.1)
                            wait_time += 1
                            if wait_time > 100:  # Timeout after 10 seconds
                                self.current_session.onDisconnected(
                                    None
                                )  # Force disconnect state
                                break

                    else:
                        return  # User cancelled closing connected session

                for plugin in self._plugins.values():
                    if isinstance(plugin, Plugin):
                        plugin.onSessionDestroy(self.current_session)

                name = self.current_session.name
                self.current_session.closeLoggers()
                self.current_session.clean()
                self.sessions.pop(name)  # Remove after cleaning
                self.current_session = None  # Set current session to None
                self.consoleView.buffer = SessionBuffer()  # Use a blank buffer

                # self.set_status(f"Session {name} has been closed") # Already in English
                if len(self.sessions.keys()) > 0:
                    new_sess_key = list(self.sessions.keys())[
                        0
                    ]  # Activate the first remaining session
                    self.activate_session(new_sess_key)
                    # self.set_status(f"Current session switched to {self.current_session.name}") # Already in English
                else:
                    self.app.invalidate()  # Invalidate to update title bar etc.

        asyncio.ensure_future(coroutine())

    # Menu Action Operations - Start

    def act_new(self):
        "Menu: Create New Session"

        async def coroutine():
            dlgNew = NewSessionDialog()
            result = await self.show_dialog_as_float(dlgNew)
            if result:
                self.create_session(*result)
            # Return result? Original didn't explicitly return

        asyncio.ensure_future(coroutine())

    def act_connect(self):
        "Menu: Connect/Reconnect"
        if self.current_session:
            self.current_session.handle_connect()

    def act_discon(self):
        "Menu: Disconnect"
        if self.current_session:
            self.current_session.disconnect()

    def act_nosplit(self):
        "Menu: Cancel Split/Selection"
        b = None  # Initialize b
        if self.current_session:
            s = self.current_session
            b = s.buffer
        elif self.showLog:
            b = self.logSessionBuffer

        if isinstance(b, Buffer):  # Check if b is a valid buffer
            b.exit_selection()
            b.cursor_position = len(b.text)

    def act_close_session(self):
        "Menu: Close Current Session"
        if self.current_session:
            self.close_session()

        elif self.showLog:
            self.showLog = False
            self.logFileShown = ""  # Clear shown log file name
            self.logSessionBuffer._set_text("")  # Clear log buffer content
            self.consoleView.buffer = SessionBuffer()  # Set to a blank buffer
            if len(self.sessions.keys()) > 0:
                new_sess_key = list(self.sessions.keys())[
                    0
                ]  # Activate first session if any exist
                self.activate_session(new_sess_key)
            else:
                self.current_session = None  # Ensure no session is active
                self.app.invalidate()  # Update display

    def act_beautify(self):
        "Menu: Toggle Beautify Display"
        val = not Settings.client["beautify"]
        Settings.client["beautify"] = val
        if self.current_session:
            # Use English text
            self.current_session.info(
                f"Display beautification is now {'enabled' if val else 'disabled'}!"
            )

    def act_echoinput(self):
        "Menu: Toggle Echo Input Command"
        val = not Settings.client["echo_input"]
        Settings.client["echo_input"] = val
        if self.current_session:
            # Use English text
            self.current_session.info(
                f"Echo input command is set to: {'ON' if val else 'OFF'}"
            )

    def act_autoreconnect(self):
        "Menu: Toggle Auto Reconnect"
        val = not Settings.client["auto_reconnect"]
        Settings.client["auto_reconnect"] = val
        if self.current_session:
            # Use English text
            self.current_session.info(
                f"Auto reconnect is set to: {'ON' if val else 'OFF'}"
            )

    def act_copy(self):
        "Menu: Copy Plain Text"
        self.copy()

    def act_copyraw(self):
        "Menu: Copy (ANSI)"
        self.copy(raw=True)

    def act_clearsession(self):
        "Menu: Clear Session Content"
        if self.consoleView.buffer:  # Check if buffer exists
            self.consoleView.buffer.reset()  # Use reset for clarity

    def act_reload(self):
        "Menu: Reload Scripts/Config"
        if self.current_session:
            self.current_session.handle_reload()

    # Feature not yet implemented
    def act_change_layout(self, layout):
        # if isinstance(layout, STATUS_DISPLAY):
        self.status_display = (
            layout  # Needs conversion if layout isn't STATUS_DISPLAY enum
        )
        # self.console_frame.body.reset()
        # if layout == STATUS_DISPLAY.HORIZON:
        #     self.console_frame.body = self.console_with_horizon_status
        # elif layout == STATUS_DISPLAY.VERTICAL:
        #     self.console_frame.body = self.console_with_vertical_status
        # elif layout == STATUS_DISPLAY.NONE:
        #     self.console_frame.body = self.console_without_status

        # self.show_message("Layout Adjustment", f"Layout set to {layout}") # English message
        self.app.invalidate()

    def act_exit(self):
        """Menu: Exit"""

        async def coroutine():
            con_sessions = list()
            for session in self.sessions.values():
                if session.connected:
                    con_sessions.append(session.name)

            if len(con_sessions) > 0:
                # Use English text for dialog
                dlgQuery = QueryDialog(
                    HTML('<b fg="red">Program Exit Warning</b>'),
                    HTML(
                        '<style fg="red">There are still {0} sessions ({1}) connected. Confirm closing?</style>'.format(
                            len(con_sessions), ", ".join(con_sessions)
                        )
                    ),
                )
                result = await self.show_dialog_as_float(dlgQuery)
                if result:
                    # Disconnect sessions before exiting
                    for ss_name in con_sessions:
                        if ss_name in self.sessions:  # Check if session still exists
                            ss = self.sessions[ss_name]
                            ss.disconnect()

                            # Add delay to ensure session closure (similar to close_session)
                            wait_time = 0
                            while ss.connected:
                                await asyncio.sleep(0.1)
                                wait_time += 1
                                if wait_time > 100:  # Timeout after 10 seconds
                                    ss.onDisconnected(None)  # Force disconnect state
                                    break

                            # Call plugin destroy hook after disconnect attempt
                            for plugin in self._plugins.values():
                                if isinstance(plugin, Plugin):
                                    plugin.onSessionDestroy(ss)
                else:
                    return  # User cancelled exit

            # Proceed with exit if no connected sessions or user confirmed
            self.app.exit()

        asyncio.ensure_future(coroutine())

    def act_about(self):
        "Menu: About"
        dialog_about = WelcomeDialog(True)
        self.show_dialog(dialog_about)

    # Menu Action Operations - End

    def get_input_prompt(self):
        "Command input line prompt"
        # Assume Settings.text["input_prompt"] is English or configured elsewhere
        return HTML(Settings.text.get("input_prompt", "> "))  # Default prompt

    def btn_title_clicked(self, name, mouse_event: MouseEvent):
        "Top session tab click switch mouse event"
        if mouse_event.event_type == MouseEventType.MOUSE_UP:
            if name == "[LOG]":
                self.showLogInTab()
            elif name in self.sessions:  # Check if clicked name is a valid session
                self.activate_session(name)

    def get_frame_title(self):
        "Top session title tabs"
        if not self.sessions and not self.showLog:  # Simplified condition
            return Settings.__appname__ + " " + Settings.__version__

        title_formatted_list = []

        # Add session tabs
        for key, session in self.sessions.items():
            style_class = ""
            if session == self.current_session:  # Check if it's the active session
                style_class = Settings.styles.get(
                    "selected.connected" if session.connected else "selected",
                    "class:frame.label",
                )
            else:
                style_class = Settings.styles.get(
                    "normal.connected" if session.connected else "normal",
                    "class:frame.label",
                )

            title_formatted_list.append(
                (style_class, key, functools.partial(self.btn_title_clicked, key))
            )
            title_formatted_list.append(("", " | "))

        # Add log tab if applicable
        if self.showLog:
            log_title_display = (
                f"[LOG] {os.path.basename(self.logFileShown)}"
                if self.logFileShown
                else "[LOG]"
            )
            log_style_class = Settings.styles.get(
                "selected" if self.current_session is None else "normal",
                "class:frame.label",
            )  # Selected if no session is active
            title_formatted_list.append(
                (
                    log_style_class,
                    log_title_display,
                    functools.partial(self.btn_title_clicked, "[LOG]"),
                )
            )
            title_formatted_list.append(("", " | "))
        elif not self.sessions:  # Only show [LOG] if no sessions exist and log isn't active (edge case from first check)
            log_title_display = "[LOG]"  # No file shown as log isn't active
            log_style_class = Settings.styles.get(
                "normal", "class:frame.label"
            )  # Normal style
            title_formatted_list.append(
                (
                    log_style_class,
                    log_title_display,
                    functools.partial(self.btn_title_clicked, "[LOG]"),
                )
            )
            title_formatted_list.append(("", " | "))

        # Remove trailing separator if list is not empty
        if title_formatted_list:
            return title_formatted_list[:-1]
        else:  # Should not happen based on initial check, but safeguard
            return Settings.__appname__ + " " + Settings.__version__

    def get_statusbar_text(self):
        "Status bar content"
        return [
            ("class:status", " "),
            ("class:status", self.status_message),
        ]

    def get_statusbar_right_text(self):
        "Status bar right-side content"
        # Use English indicators
        con_str, mouse_support, tri_status, beautify = "", "", "", ""
        if not Settings.client["beautify"]:
            beautify = "Beautify Off "  # English
        if not self._mouse_support:
            mouse_support = "Mouse Disabled "  # English

        if self.current_session:
            if self.current_session._ignore:  # Assuming _ignore relates to triggers
                tri_status = "Triggers Disabled "  # English (Assuming meaning)

            if not self.current_session.connected:
                con_str = "Not Connected"  # English
            else:
                dura = self.current_session.duration
                DAY, HOUR, MINUTE = 86400, 3600, 60
                days = dura // DAY
                dura %= DAY
                hours = dura // HOUR
                dura %= HOUR
                mins = dura // MINUTE
                secs = dura % MINUTE  # Corrected to secs

                # Use English format strings
                if days > 0:
                    con_str = "Connected: {:.0f}d {:.0f}h {:.0f}m {:.0f}s".format(
                        days, hours, mins, secs
                    )
                elif hours > 0:
                    con_str = "Connected: {:.0f}h {:.0f}m {:.0f}s".format(
                        hours, mins, secs
                    )
                elif mins > 0:
                    con_str = "Connected: {:.0f}m {:.0f}s".format(mins, secs)
                else:
                    con_str = "Connected: {:.0f}s".format(secs)
        elif self.showLog:
            con_str = "Viewing Log"  # Indicate log view status

        return "{}{}{}{} {} {} ".format(
            beautify,
            mouse_support,
            tri_status,
            con_str,
            Settings.__appname__,
            Settings.__version__,
        )

    def get_statuswindow_text(self):
        "Status window: content from status_maker"
        text = ""
        try:
            if self.current_session:
                text = (
                    self.current_session.get_status()
                )  # Assuming get_status returns formatted text
        except Exception as e:
            text = f"Error getting status: {e}"  # English error

        return text

    def set_status(self, msg):
        """
        Display a message in the status bar. Can be called from code.

        :param msg: The message to display
        """
        self.status_message = msg
        self.app.invalidate()

    def _quickHandleSession(self, group, name):
        """
        Creates a session based on the specified group name and session character name from Settings content.
        """
        handled = False
        sess_key = (
            f"{group}.{name}"  # Consider using a combined key or just name if unique
        )

        # Use 'name' for session lookup as it seems to be the intended unique identifier
        if name in self.sessions.keys():
            self.activate_session(name)
            handled = True

        elif group in Settings.sessions:  # Check if group exists
            site = Settings.sessions[group]
            if name in site.get("chars", {}):  # Check if character exists in group
                host = site.get("host")
                port = site.get("port")
                encoding = site.get(
                    "encoding"
                )  # Will default in create_session if None
                autologin = site.get("autologin", "{} {}")  # Default format
                default_script = site.get("default_script", [])  # Default to empty list

                def_scripts = list()
                if isinstance(default_script, str):
                    def_scripts.extend(
                        s.strip() for s in default_script.split(",") if s.strip()
                    )
                elif isinstance(default_script, (list, tuple)):
                    def_scripts.extend(default_script)

                charinfo = site["chars"][
                    name
                ]  # Assuming list/tuple [userid, password, script?]

                after_connect = ""
                userid = ""
                if len(charinfo) >= 2:
                    userid = charinfo[0]
                    password = charinfo[1]
                    try:
                        after_connect = autologin.format(userid, password)
                    except (
                        IndexError
                    ):  # Handle if autologin format string expects more args
                        after_connect = ""  # Or log error

                sess_scripts = list(def_scripts)  # Start with default scripts

                if len(charinfo) >= 3:
                    session_script = charinfo[2]
                    if session_script:
                        if isinstance(session_script, str):
                            sess_scripts.extend(
                                s.strip()
                                for s in session_script.split(",")
                                if s.strip()
                            )
                        elif isinstance(session_script, (list, tuple)):
                            sess_scripts.extend(session_script)

                # Use 'name' as the session name
                self.create_session(
                    name, host, port, encoding, after_connect, sess_scripts, userid
                )
                handled = True

        return handled

    def handle_session(self, *args):
        """
        Execution function for the embedded command #session, creates a remote connection session.
        This function should not be called directly in code.

        Usage:
            - #session {name} {host} {port} [encoding]
            - When Encoding is not specified, defaults to the value in Settings.server["default_encoding"] (usually utf-8).
            - Can directly use #{name} [command args...] to switch sessions or send commands to a session.

            - #session {group}.{name}
            - Equivalent to clicking the {name} menu under the {group} menu to create a session. If the session already exists, switches to it.

        Parameters:
            :name: Session name
            :host: Server domain name or IP address
            :port: Port number
            :encoding: Encoding format, defaults to utf8 if not specified.

            :group: Group name, i.e., a key under the `sessions` field in the configuration file.
            :name: Session shortcut name, a key under the `chars` field of the aforementioned `group` key.

        Examples:
            ``#session {name} {host} {port} [encoding]``
                Creates a remote connection session, connecting to the specified port of the remote host using the specified encoding format (or default) and saving it as {name}.
            ``#session newstart mud.pkuxkx.net 8080 GBK``
                Connects to port 8080 of mud.pkuxkx.net using GBK encoding and names the session 'newstart'.
            ``#session othermud mud.example.com 8081``
                Connects to port 8081 of mud.example.com using the default encoding (e.g., UTF8) and names the session 'othermud'.
            ``#newstart``
                Switches the session named 'newstart' to be the current session.
            ``#newstart tell player hello``
                Makes the session named 'newstart' execute the command 'tell player hello' without switching to that session.

            ``#session pkuxkx.newstart``
                Creates a session using the specified shortcut configuration (group 'pkuxkx', character 'newstart'), equivalent to clicking the World->pkuxkx->newstart menu. If the session exists, switches to it.

        Related commands:
            - #close
            - #exit

        """

        nothandle = True
        errmsg = "Incorrect #session command usage."  # English error message
        if len(args) == 1:
            host_session = args[0]
            if "." in host_session:
                try:
                    group, name = host_session.split(".", 1)  # Split only once
                    nothandle = not self._quickHandleSession(group, name)
                    if nothandle:  # If quick handle failed, provide specific error
                        errmsg = f"Could not create or activate session from shortcut '{host_session}'. Check config."
                except ValueError:
                    errmsg = f"Invalid shortcut format '{host_session}'. Use group.name format, e.g., #session pkuxkx.newstart"

            else:
                # Allow switching/sending commands via #sessionname [command]
                session_name_cmd = host_session
                if session_name_cmd in self.sessions:
                    self.activate_session(session_name_cmd)
                    nothandle = False
                else:
                    errmsg = f"Session '{session_name_cmd}' not found. To create via shortcut, use group.name format."

        elif len(args) >= 3:
            try:
                session_name = args[0]
                session_host = args[1]
                session_port = int(args[2])
                session_encoding = None  # Default
                if len(args) >= 4:
                    session_encoding = args[3]
                # Removed default setting here, create_session handles it

                # Basic validation
                if not session_name or not session_host or session_port <= 0:
                    raise ValueError("Invalid session name, host, or port.")

                self.create_session(
                    session_name, session_host, session_port, session_encoding
                )
                nothandle = False  # Assuming create_session handles errors internally by setting status
            except ValueError as e:
                errmsg = f"Invalid arguments for #session: {e}. Use #session name host port [encoding]."
            except Exception as e:  # Catch other potential errors
                errmsg = f"Error creating session: {e}"

        if nothandle:
            self.set_status(errmsg)  # Use the specific error message generated

    def enter_pressed(self, buffer: Buffer):
        "Command line Enter key processing"
        cmd_line = buffer.text.strip()  # Strip leading/trailing whitespace

        # Handle sending commands to specific inactive sessions: #sessionname command args...
        if cmd_line.startswith(Settings.client["appcmdflag"]) and " " in cmd_line:
            parts = cmd_line[1:].split(" ", 1)
            target_session_name = parts[0]
            command_to_send = parts[1] if len(parts) > 1 else ""

            if (
                target_session_name in self.sessions
                and self.sessions[target_session_name] != self.current_session
            ):
                target_session = self.sessions[target_session_name]
                if command_to_send:  # Only send if there's an actual command
                    try:
                        target_session.log.log(
                            f"Remote command input for {target_session_name}: {command_to_send}\n"
                        )
                        cb = CodeBlock(command_to_send)
                        cb.execute(target_session)  # Execute in target session context
                    except Exception as e:
                        target_session.warning(f"Error executing remote command: {e}")
                        target_session.exec_command(command_to_send)  # Fallback
                    self.set_status(f"Sent to {target_session_name}: {command_to_send}")
                else:
                    # Just switch session if no command given after #sessionname
                    self.activate_session(target_session_name)
                # Command handled, don't process further, clear input buffer
                buffer.reset()
                return False  # Don't keep text

        # Handle #session command specifically for creation/activation
        if cmd_line.startswith(f"{Settings.client['appcmdflag']}session"):
            cmd_tuple = cmd_line.split()  # Split by space
            self.handle_session(*cmd_tuple[1:])  # Pass arguments after '#session'
            buffer.reset()  # Clear input after handling
            return False  # Don't keep text

        # Handle other # commands for current session or app
        elif cmd_line.startswith(Settings.client["appcmdflag"]):
            command_part = cmd_line[1:].split(" ", 1)[0]  # Get the command name
            if command_part == "exit":
                self.act_exit()
                buffer.reset()
                return False
            elif command_part == "close":
                if self.current_session:
                    self.act_close_session()  # Will close current session
                elif self.showLog:
                    self.act_close_session()  # Will close log view
                else:
                    self.set_status("No active session or log view to close.")
                buffer.reset()
                return False
            # Add other app-level commands here if needed
            elif self.current_session:
                # Treat other #commands as potentially session-specific
                try:
                    self.current_session.log.log(f"Command line input: {cmd_line}\n")
                    cb = CodeBlock(cmd_line)  # Pass the full #command
                    cb.execute(self.current_session)
                except Exception as e:
                    self.current_session.warning(
                        f"Error processing command '{cmd_line}': {e}"
                    )
                    # Maybe don't execute as plain command if it started with #
            else:
                # If no current session and not exit/close
                self.set_status(f"Unknown command '{cmd_line}' or no active session.")
            buffer.reset()
            return False  # Don't keep text

        # Send non-# command lines to the current session
        elif self.current_session:
            if len(cmd_line) == 0:
                self.current_session.writeline(
                    ""
                )  # Send empty line if user just presses enter
            else:
                self.current_session.last_command = cmd_line  # Store last command sent
                try:
                    self.current_session.log.log(f"Command line input: {cmd_line}\n")
                    cb = CodeBlock(cmd_line)  # Process as potential code block first
                    cb.execute(self.current_session)
                except Exception:
                    # If not a valid CodeBlock or error during exec, treat as plain command
                    # self.current_session.warning(f"Executing as plain text: {e}") # Optional warning
                    self.current_session.exec_command(cmd_line)  # Send as plain command

        # No current session and not an app command
        elif len(cmd_line) > 0:
            self.set_status("No active session to send command to.")  # English message

        # Configuration: Retain last input in command line
        if Settings.client["remain_last_input"]:
            buffer.cursor_position = 0
            buffer.start_selection()
            buffer.cursor_right(len(buffer.text))  # Use buffer.text length
            return True  # Keep text

        else:
            buffer.reset()  # Clear buffer if not retaining
            return False  # Don't keep text (default behavior)

    @property
    def globals(self):
        """
        Global variables, dot notation accessor.
        Used to replace calls to get_globals and set_globals functions.
        """
        return self._globals

    def get_globals(self, name, default=None):
        """
        Get a PYMUD global variable.

        :param name: Global variable name.
        :param default: Return value if the global variable does not exist.
        """
        return self._globals.get(name, default)  # Use dict.get for safety

    def set_globals(self, name, value):
        """
        Set a PYMUD global variable.

        :param name: Global variable name.
        :param value: Global variable value. The value can be of any type.
        """
        self._globals[name] = value

    def del_globals(self, name):
        """
        Remove a PYMUD global variable.
        Removing a global variable deletes it from the dictionary, rather than setting it to None.

        :param name: Global variable name.
        """
        if name in self._globals:  # Use 'in' for check
            self._globals.pop(name)

    @property
    def plugins(self):
        "List of all loaded plugins, dot notation accessor."
        return self._plugins

    def show_message(self, title, text, modal=True):
        "Display a message dialog box."

        async def coroutine():
            dialog = MessageDialog(title, text, modal)
            await self.show_dialog_as_float(dialog)

        asyncio.ensure_future(coroutine())

    def show_dialog(self, dialog):
        "Display a given dialog box."

        async def coroutine():
            await self.show_dialog_as_float(dialog)

        asyncio.ensure_future(coroutine())

    async def show_dialog_as_float(self, dialog):
        "Display a pop-up window."
        float_ = Float(content=dialog)
        self.root_container.floats.insert(0, float_)

        app_layout = self.app.layout  # Cache layout
        original_focus = app_layout.current_window  # Store original focus

        app_layout.focus(dialog)
        result = await dialog.future

        # Restore focus carefully
        try:
            if float_ in self.root_container.floats:  # Check if still exists
                self.root_container.floats.remove(float_)
            # Try to restore original focus, otherwise focus command line
            if original_focus and original_focus in app_layout.visible_windows:
                app_layout.focus(original_focus)
            else:
                app_layout.focus(self.commandLine)
        except Exception:  # Catch potential errors during focus restoration
            app_layout.focus(self.commandLine)  # Fallback focus

        return result

    async def run_async(self):
        "Run this program asynchronously."
        # Run plugin application startup here, ensuring plugin initialization runs after the event_loop is created.
        for plugin in self._plugins.values():
            if isinstance(plugin, Plugin):
                try:
                    plugin.onAppInit(self)
                except Exception as e:
                    print(
                        f"Error during onAppInit for plugin {plugin.name}: {e}"
                    )  # Log error

        # Create system timer task
        timer_task = asyncio.create_task(self.onSystemTimerTick())

        try:
            # Run the application
            await self.app.run_async(
                set_exception_handler=False
            )  # Consider handling exceptions
        finally:
            # Cleanup tasks when application exits
            timer_task.cancel()  # Cancel the timer task
            try:
                await timer_task  # Wait for cancellation (optional)
            except asyncio.CancelledError:
                pass  # Expected exception on cancel

            # When the application exits, run plugin application destruction.
            for plugin in self._plugins.values():
                if isinstance(plugin, Plugin):
                    try:
                        plugin.onAppDestroy(self)
                    except Exception as e:
                        print(
                            f"Error during onAppDestroy for plugin {plugin.name}: {e}"
                        )  # Log error

    def run(self):
        "Run this program."
        # self.app.run(set_exception_handler = False)
        try:
            asyncio.run(self.run_async())
        except (EOFError, KeyboardInterrupt):
            # Handle common exit scenarios gracefully
            pass
        finally:
            # Ensure final cleanup if needed
            print("PyMud exiting.")

    def get_width(self):
        "Get the actual width of ConsoleView, equal to the output width (adjusted for side status bar)."
        size = self.app.output.get_size().columns
        if self.status_display == STATUS_DISPLAY.VERTICAL:  # Compare with Enum member
            # Subtract status width and divider width (assuming 1)
            size = (
                size
                - Settings.client.get("status_width", 20)
                - (1 if Settings.client.get("status_divider", False) else 0)
            )
        return max(1, size)  # Ensure width is at least 1

    def get_height(self):
        "Get the actual height of ConsoleView, equal to output height minus fixed elements (borders, menu, command, status)."
        # Fixed elements height: top_border(1) + bottom_border(1) + commandLine(1) + status_bar(1) = 4
        fixed_height = 4
        size = self.app.output.get_size().rows - fixed_height

        if self.status_display == STATUS_DISPLAY.HORIZON:  # Compare with Enum member
            # Subtract status height and divider height (assuming 1)
            size = (
                size
                - Settings.client.get("status_height", 5)
                - (1 if Settings.client.get("status_divider", False) else 0)
            )
        return max(1, size)  # Ensure height is at least 1

    #####################################
    # plugins Handling
    #####################################
    def load_plugins(self):
        "Load plugins. Will load plugins from the `plugins` directory under the `pymud` package, and also from the `plugins` directory in the current working directory."

        plugin_dirs = []
        # System plugins directory
        try:
            current_dir = os.path.dirname(__file__)
            system_plugins_dir = os.path.join(current_dir, "plugins")
            if os.path.isdir(system_plugins_dir):  # Check if it's a directory
                plugin_dirs.append(system_plugins_dir)
        except NameError:  # __file__ might not be defined (e.g., interactive)
            pass

        # Current working directory plugins
        local_plugins_dir = os.path.abspath(os.path.join(os.getcwd(), "plugins"))
        if os.path.isdir(local_plugins_dir):
            plugin_dirs.append(local_plugins_dir)

        loaded_plugin_names = set()

        for plugins_dir in plugin_dirs:
            # print(f"Scanning for plugins in: {plugins_dir}") # Debugging output
            try:
                for file in os.listdir(plugins_dir):
                    if file.endswith(".py") and not file.startswith(
                        "_"
                    ):  # Standard convention
                        file_path = os.path.join(plugins_dir, file)
                        file_name = file[:-3]  # Module name

                        if file_name in loaded_plugin_names:
                            # print(f"Skipping already loaded plugin: {file_name}") # Debug
                            continue  # Don't load plugin with same name twice

                        try:
                            plugin = Plugin(
                                file_name, file_path
                            )  # Instantiation loads the module
                            self._plugins[plugin.name] = plugin
                            loaded_plugin_names.add(plugin.name)
                            # onAppInit is called later in run_async after event loop is ready
                            print(
                                f"Successfully loaded plugin: {plugin.name} from {file_path}"
                            )  # Info
                        except Exception as e:
                            # Use print for early loading errors as set_status might not work yet
                            print(
                                f"ERROR loading plugin: File: {file_path} is not a valid plugin file. Error: {e}"
                            )
            except FileNotFoundError:
                # print(f"Plugin directory not found: {plugins_dir}") # Debugging
                pass  # Silently ignore if a directory doesn't exist
            except Exception as e:
                print(f"ERROR accessing plugin directory {plugins_dir}: {e}")

    def reload_plugin(self, plugin_name: str):  # Accept name as string
        "Reload the specified plugin by name."
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            if isinstance(plugin, Plugin):
                print(f"Reloading plugin: {plugin_name}")  # Info
                # Call destroy hooks on sessions *before* reloading module
                for session in self.sessions.values():
                    try:
                        plugin.onSessionDestroy(session)
                    except Exception as e:
                        print(
                            f"Error during onSessionDestroy for {plugin_name} on session {session.name}: {e}"
                        )

                try:
                    # Reload the plugin module itself
                    plugin.reload()

                    # Call init hooks *after* reloading
                    plugin.onAppInit(
                        self
                    )  # Re-initialize plugin state related to the app

                    # Call create hooks for existing sessions *after* reloading
                    for session in self.sessions.values():
                        try:
                            plugin.onSessionCreate(session)
                        except Exception as e:
                            print(
                                f"Error during onSessionCreate for reloaded {plugin_name} on session {session.name}: {e}"
                            )

                    self.set_status(f"Plugin '{plugin_name}' reloaded successfully.")

                except Exception as e:
                    self.set_status(f"Error reloading plugin '{plugin_name}': {e}")
                    print(
                        f"Error reloading plugin '{plugin_name}': {e}"
                    )  # Also print for visibility
                    # Optionally remove the failed plugin?
                    # self._plugins.pop(plugin_name, None)
            else:
                self.set_status(
                    f"Cannot reload '{plugin_name}': Not a valid Plugin object."
                )
        else:
            self.set_status(f"Plugin '{plugin_name}' not found for reloading.")


def startApp(cfg_data=None):
    """Initializes and runs the PyMudApp."""
    app = PyMudApp(cfg_data)
    app.run()


# Example of how to run if this script is executed directly
if __name__ == "__main__":
    # Potential place to load cfg_data from a file if needed
    # cfg = {}
    # startApp(cfg)
    startApp()
