"""Session core module - defines the main Session class and its initialization"""

import asyncio
import datetime
import logging
import re
import sysconfig
import time
from collections import OrderedDict

from ..extras import DotDict, SessionBuffer
from ..logger import Logger
from ..protocol import MudClientProtocol
from ..settings import Settings
from .command_handlers import SessionCommandHandlers
from .commands import SessionCommands
from .display import SessionDisplay
from .io import SessionIO
from .modules import SessionModules
from .objects import SessionObjects
from .variables import SessionVariables


class Session(
    SessionIO,
    SessionVariables,
    SessionObjects,
    SessionModules,
    SessionCommands,
    SessionDisplay,
    SessionCommandHandlers,
):
    """
    Main session management object that implements all processing for each character.

    **Session objects are created and managed by the PyMudApp object. No manual creation is required.**

    :param app: The corresponding PyMudApp object
    :param name: The name of this session
    :param host: The address of the remote server this session connects to
    :param port: The port of the remote server this session connects to
    :param encoding: The encoding of the remote server
    :param after_connect: Operations to execute after connecting to the remote server
    :param loop: The asyncio event loop
    :param kwargs: Keyword parameter list, currently supports **scripts**: list of scripts to load
    """

    PLAIN_TEXT_REGX = re.compile(
        "\x1b\\[[0-9;]*[a-zA-Z]", flags=re.IGNORECASE | re.ASCII
    )

    _sys_commands = (
        "help",
        "exit",
        "close",
        "connect",
        "disconnect",
        "info",
        "warning",
        "error",
        "clear",
        "test",
        "wait",
        "timer",
        "variable",
        "alias",
        "trigger",
        "global",
        "command",
        "task",
        "modules",
        "load",
        "reload",
        "unload",
        "reset",
        "ignore",
        "save",
        "gmcp",
        "num",
        "repeat",
        "replace",
        "gag",
        "message",
        "plugins",
        "py",
        "all",
        "log",
    )

    _commands_alias = {
        "ali": "alias",
        "cmd": "command",
        "ti": "timer",
        "tri": "trigger",
        "var": "variable",
        "rep": "repeat",
        "con": "connect",
        "dis": "disconnect",
        "wa": "wait",
        "mess": "message",
        "action": "trigger",
        "cls": "clear",
        "mods": "modules",
        "ig": "ignore",
        "t+": "ignore",
        "t-": "ignore",
        "show": "test",
    }

    def __init__(
        self,
        app,
        name,
        host,
        port,
        encoding=None,
        after_connect=None,
        loop=None,
        **kwargs,
    ):
        self.pyversion = sysconfig.get_python_version()
        self.loop = loop or asyncio.get_running_loop()
        self.syslog = logging.getLogger("pymud.Session")

        from ..pymud import PyMudApp

        if isinstance(app, PyMudApp):
            self.application = app

        self.name = name
        self._transport = None
        self._protocol = None
        self.state = "INITIALIZED"
        self._eof = False
        self._uid = 0
        self._ignore = False
        self._events = dict()
        self._events["connected"] = None
        self._events["disconnected"] = None

        self._auto_script = kwargs.get("scripts", None)

        self._cmds_handler = dict()
        for cmd in self._sys_commands:
            handler = getattr(self, f"handle_{cmd}", None)
            self._cmds_handler[cmd] = handler

        self.seperator = Settings.client["seperator"] or ";"
        self.newline = Settings.server["newline"] or "\n"
        self.encoding = Settings.server["default_encoding"]
        self.newline_cli = Settings.client["newline"] or "\n"

        self.last_command = ""

        self.buffer = SessionBuffer()
        self.buffer_pos_end = 0
        self.buffer_pos_view = 0
        self.buffer_pos_view_line = -1
        self.showHistory = False
        self._line_count = 0
        self._status_maker = None
        self.display_line = ""

        self._activetime = time.time()

        self.initialize()

        self._loggers = dict()
        self.log = self.getLogger(name)

        self.host = host
        self.port = port
        self.encoding = encoding or self.encoding
        self.after_connect = after_connect

        self._modules = OrderedDict()

        # Adjust variable loading and script loading to session creation time
        if Settings.client["var_autoload"]:
            self._load_saved_variables()

        if self._auto_script:
            self.info(
                f"About to automatically load the following modules: {self._auto_script}"
            )
            self.load_module(self._auto_script)

        if Settings.client["auto_connect"]:
            self.open()

    def _load_saved_variables(self):
        """Load saved variables from disk if available"""
        import os
        import pickle

        file = f"{self.name}.mud"
        if os.path.exists(file):
            with open(file, "rb") as fp:
                try:
                    vars = pickle.load(fp)
                    self._variables.update(vars)
                    self.info(f"Successfully loaded saved variables from {file}")
                except Exception as e:
                    self.warning(
                        f"Failed to load variables from {file}, error message: {e}"
                    )

    def __del__(self):
        self.clean()
        self.closeLoggers()

    def initialize(self):
        """Initialize Session related objects. **No script call required.**"""
        self._line_buffer = bytearray()

        self._triggers = DotDict()
        self._aliases = DotDict()
        self._commands = DotDict()
        self._timers = DotDict()
        self._gmcp = DotDict()

        self._variables = DotDict()

        self._tasks = set()

        self._command_history = []

    def open(self):
        """Create a connection to the remote server, synchronously. Implemented by calling the asynchronous connect method."""
        asyncio.ensure_future(self.connect(), loop=self.loop)

    async def connect(self):
        """Create a connection to the remote server, asynchronously. Non-blocking."""

        def _protocol_factory():
            return MudClientProtocol(self, onDisconnected=self.onDisconnected)

        try:
            transport, protocol = await self.loop.create_connection(
                _protocol_factory, self.host, self.port
            )

            self._transport = transport
            self._protocol = protocol
            self._state = "RUNNING"

            self.onConnected()

        except Exception as exc:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.error(
                f"An error occurred during connection creation, error occurred at {now}, error information: {exc}, "
            )
            self._state = "EXCEPTION"

    async def reconnect(self, timeout=15):
        """Reconnect to the remote server, asynchronously. Non-blocking."""
        if not self.connected:
            self.info(
                f"Attempting to reconnect to server {self.host}:{self.port}, timeout {timeout} seconds."
            )
            try:
                await asyncio.wait_for(self.connect(), timeout)
            except asyncio.TimeoutError:
                self.error("Connection to server timed out, connection remains closed.")

    def onConnected(self):
        """
        Callback function after connection is established. **No script call required.**
        """
        self.info(f"Connected to server {self.host}:{self.port} successfully.")
        if self.after_connect:
            self.exec_command(self.after_connect)

        if self._events["connected"]:
            self._events["connected"]()

    def disconnect(self):
        """Disconnect from the remote server."""
        if self._transport:
            self._transport.close()

    def onDisconnected(self, protocol):
        """
        Callback function after connection is disconnected. **No script call required.**

        :param protocol: Disconnected protocol
        """
        if self._protocol is protocol:
            self.state = "DISCONNECTED"
            if self._events["disconnected"]:
                self._events["disconnected"]()

    @property
    def connected(self) -> bool:
        """
        Read-only property: Current connection status of this session, connected is `True`, otherwise `False`
        """
        if not self._transport:
            return False

        return not self._transport.is_closing()

    @property
    def duration(self) -> float:
        """
        Read-only property: Current connection duration of this session, unit is seconds
        """
        if self._protocol and hasattr(self._protocol, "duration"):
            return self._protocol.duration
        else:
            return 0.0

    @property
    def idletime(self) -> float:
        """
        Read-only property: Current idle time without input of this session, unit is seconds
        """
        return time.time() - self._activetime

    @property
    def status_maker(self):
        """
        Property: Status bar generation function, set by user script, used to generate additional tags on the status bar.

        If user script executes `session.status_maker = my_status_func`, PyMUD will call this function to generate additional tags, providing them to the interface for display.
        """
        return self._status_maker

    @status_maker.setter
    def status_maker(self, value):
        """Set status_maker value"""
        if callable(value):
            self._status_maker = value

    @property
    def event_connected(self):
        """
        Property: Connection establishment event callback function, set by user script.

        If user script executes `session.event_connected = my_connected_func`, PyMUD will call this function when this session connection is established.
        """
        return self._events["connected"]

    @event_connected.setter
    def event_connected(self, event):
        """Set event_connected value"""
        if callable(event):
            self._events["connected"] = event

    @property
    def event_disconnected(self):
        """
        Property: Connection disconnection event callback function, set by user script.

        If user script executes `session.event_disconnected = my_disconnected_func`, PyMUD will call this function when this session connection is disconnected.
        """
        return self._events["disconnected"]

    @event_disconnected.setter
    def event_disconnected(self, event):
        """Set event_disconnected value"""
        if callable(event):
            self._events["disconnected"] = event

    def getLogger(
        self, name, mode="a", encoding="utf-8", encoding_errors="ignore", raw=False
    ) -> Logger:
        """
        Get the logger associated with this session. Each session logger name is unique and automatically created with the session, and closed with the session.

        If the name is different from the session name, the session will attempt to close the logger associated with that name when the session is closed, unless the logger is referenced by other sessions.

        :param name: Name.
        :param mode: Open file mode, default is 'a'(append)
        :param encoding: Encoding method, default is 'utf-8'
        :param encoding_errors: Encoding error handling method
        :param raw: Whether to save original ANSI control characters, default is False (not saved)

        :return: Logger object
        """
        if name in self._loggers.keys():
            log = self._loggers[name]
        else:
            log = Logger(name, mode, encoding, encoding_errors, raw)
            self._loggers[name] = log

        return log

    def closeLoggers(self):
        """Close all loggers"""
        for log in self._loggers.values():
            log.close()
        self._loggers.clear()

    @property
    def modules(self) -> OrderedDict:
        """
        Read-only property: List of modules for this session. OrderedDict type
        """
        return self._modules

    @property
    def plugins(self) -> DotDict:
        """
        Read-only property: All plugins loaded for this session. DotDict type
        """
        return self.application.plugins

    def get_status(self):
        """
        Get status information.

        :return: Tuple composed of status_text, sub_status_text, status_color
        """
        if self._status_maker and callable(self._status_maker):
            return self._status_maker()
        else:
            status_text = f"{self.name} - {self.host}:{self.port}"
            sub_status_text = "Connection closed" if not self.connected else ""
            status_color = "rgb(230,0,0)" if not self.connected else None
            return status_text, sub_status_text, status_color

    def clean(self):
        """Clean up resources used by the session. **No script call required.**"""
        import gc

        for key, val in list(self.__dict__.items()):
            if key.startswith("_") or key not in dir(self):
                if key == "_transport":
                    if val:
                        try:
                            val.close()
                        except Exception:
                            pass
                        val = None
                        self.__dict__[key] = val

                elif key == "_tasks":
                    if val:
                        tasks = list(val)
                        for task in tasks:
                            try:
                                if not task.done() and not task.cancelled():
                                    task.cancel()
                            except Exception:
                                pass
                        val.clear()
                        self.__dict__[key] = val

                elif key == "_timers":
                    if val:
                        timers = list(val.values())
                        for timer in timers:
                            try:
                                if hasattr(timer, "enabled"):
                                    timer.enabled = False
                            except Exception:
                                pass
                        val.clear()
                        self.__dict__[key] = val

                elif key in ("_triggers", "_aliases", "_commands", "_gmcp"):
                    if val:
                        val.clear()
                        self.__dict__[key] = val

        gc.collect()

    def reset(self):
        """
        Reset session, restore to the initial state after the session is created: Reset all triggers, aliases, timers, and empty all tasks, responses, and commands in the session.
        Modules loaded automatically when the session is created will not be unloaded.
        Session variables and buffer will be cleared.

        Reset is the highest level reset operation for the session object, which can be used for a one-time thorough reset when the script is mistakenly triggered or an exception occurs.
        """
        self.warning("Session reset, all objects cleared (excluding modules)")
        self.initialize()

    def create_task(self, coro, *args, name: str = None) -> asyncio.Task:
        """
        Create an asynchronous task using the session's associated event loop, and add a callback function to automatically clean up after task completion.

        :param coro: Coroutine
        :param name: Task name, used for distinction and search
        :return: Created task
        """

        def on_done(fut):
            try:
                self._tasks.remove(fut)
                exc = fut.exception()
                if exc:
                    self.error(f"Task {fut} encountered an exception: {exc}")
            except asyncio.exceptions.CancelledError:
                pass
            except Exception:
                pass

        task = asyncio.ensure_future(coro, loop=self.loop)
        if name:
            task.set_name(name)
        self._tasks.add(task)
        task.add_done_callback(on_done)

        return task

    def remove_task(self, task: asyncio.Task, msg=None):
        """
        Use the session's associated event loop to delete/cancel an asynchronous task, generally not required to call, created task will be automatically removed from list after completion.

        :param task: Task
        :param msg: Message to display, default is not displayed
        """
        if not task.done() and not task.cancelled():
            task.cancel()
            if isinstance(msg, str) and len(msg.strip()) > 0:
                self.info(msg)

        if task in self._tasks:
            self._tasks.remove(task)

    def clean_finished_tasks(self):
        # Clean up completed tasks.
        # Since PyMUD 0.19.2post2, cleanup completed tasks is automatically called when the task is completed, so this function is no longer used, the purpose of retaining it is for forward compatibility.
        pass

    def getUniqueNumber(self):
        """
        Get a unique identifier value that increases incrementally, used for id generation
        """
        self._uid += 1
        return self._uid

    def getUniqueID(self, prefix):
        """
        Get a unique identifier id string that increases incrementally, used for object id creation
        - prefix is object abbreviation (e.g., Alias is ali, SimpleAlias is also ali, MatchObject is mo, etc.)
        - Object abbreviation is determined by __abbr__ attribute in object class definition
        """
        self._uid += 1
        return f"{prefix}{self._uid}"

    def write_eof(self) -> None:
        """
        Send eof to the server. This function is used to send specific control characters, and should be avoided in scripts directly.
        """
        if self._transport:
            self._transport.write_eof()
