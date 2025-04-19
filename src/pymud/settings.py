"""
PyMUD Settings File
Used to store various configurations, constants, etc. related to the App
"""


class Settings:
    "Global object for saving PyMUD configuration"

    # The following content defines APP constants, please do not modify
    __appname__ = "PYMUD"
    "APP name, default PYMUD"
    __appdesc__ = "a MUD client written in Python"
    "APP brief description"
    __version__ = "0.20.4"
    "APP current version"
    __release__ = "2025-03-30"
    "APP current version release date"
    __author__ = "Benniu(newstart)@PKUXKX"
    "APP author"
    __email__ = "crapex@crapex.cc"
    "APP author email"
    __website__ = "https://pymud.readthedocs.io/"
    "Help documentation website"

    server = {
        "default_encoding": "utf-8",  # Server default encoding
        "encoding_errors": "ignore",  # Default error handling when encoding conversion fails
        "newline": "\n",  # Server newline character feature
        "SGA": True,  # Supress Go Ahead
        "ECHO": False,  # Echo
        "GMCP": True,  # Generic Mud Communication Protocol
        "MSDP": True,  # Mud Server Data Protocol
        "MSSP": True,  # Mud Server Status Protocol
        "MCCP2": False,  # Mud Compress Communication Protocol V2
        "MCCP3": False,  # Mud Compress Communication Protocol V3
        "MSP": False,  # Mud Sound Protocol
        "MXP": False,  # Mud eXtension Protocol
    }
    "Server default configuration information"

    mnes = {
        "CHARSET": server["default_encoding"],
        "CLIENT_NAME": __appname__,
        "CLIENT_VERSION": __version__,
        "AUTHOR": __author__,
    }
    "Default MNES (Mud New-Environment Standard) configuration information required by MUD protocol"

    client = {
        "buffer_lines": 5000,  # Number of buffer lines to retain
        "naws_width": 150,  # Client NAWS width
        "naws_height": 40,  # Client NAWS height
        "newline": "\n",  # Client newline character
        "tabstop": 4,  # Convert tab to spaces
        "seperator": ";",  # Multiple command separator (default ;)
        "appcmdflag": "#",  # App command flag (default #)
        "interval": 10,  # Interval time (ms) between command inputs in auto execution
        "auto_connect": True,  # Whether to automatically connect after creating a session
        "auto_reconnect": False,  # Whether to automatically reconnect after abnormal disconnection
        "reconnect_wait": 15,  # Wait time (seconds) for auto reconnection
        "var_autosave": True,  # Automatically save session variables when disconnected
        "var_autoload": True,  # Automatically load session variables during initialization
        "remain_last_input": False,
        "echo_input": False,
        "beautify": True,  # Specifically to solve the problem of PKUXKX ASCII art misalignment in the console
        "status_divider": True,  # Whether to display the status bar divider
        "status_display": 1,  # Status window display setting, 0-not display, 1-display at bottom, 2-display on right
        "status_width": 30,  # Width of right status bar
        "status_height": 6,  # Height of bottom status bar
    }
    "Client default configuration information"

    text = {
        "welcome": "Welcome to PYMUD client - PKUXKX, the best Chinese MUD game",
        "world": "World",
        "new_session": "Create new session...",
        "show_log": "Show log information",
        "exit": "Exit",
        "session": "Session",
        "connect": "Connect/Reconnect",
        "disconnect": "Disconnect",
        "beautify": "Enable/Disable beautify display",
        "echoinput": "Show/Hide input commands",
        "nosplit": "Cancel split screen",
        "copy": "Copy (plain text)",
        "copyraw": "Copy (ANSI)",
        "clearsession": "Clear session content",
        "closesession": "Close current page",
        "autoreconnect": "Enable/Disable auto reconnect",
        "loadconfig": "Load script configuration",
        "reloadconfig": "Reload script configuration",
        "layout": "Layout",
        "hide": "Hide status window",
        "horizon": "Bottom status window",
        "vertical": "Right status window",
        "help": "Help",
        "about": "About",
        "session_changed": "Successfully switched to session: {0}",
        "input_prompt": "<prompt><b>Command:</b></prompt>",  # HTML format, input command line prompt
    }

    keys = {
        "f3": "#ig",
        "f4": "#clear",
        "f5": "",
        "f6": "",
        "f7": "",
        "f8": "",
        "f9": "",
        "f10": "",
        "f11": "#close",
        "f12": "#exit",
        "c-1": "",
        "c-2": "",
        "c-3": "",
        "c-4": "",
        "c-5": "",
        "c-6": "",
        "c-7": "",
        "c-8": "",
        "c-9": "",
        "c-0": "",
    }

    sessions = {
        "pkuxkx": {
            "host": "mud.pkuxkx.net",
            "port": "8081",
            "encoding": "utf8",
            "autologin": "{0};{1}",
            "default_script": "common_modules",
            "chars": {
                "display_title": ["yourid", "yourpassword", "special_modules"],
            },
        },
        "another-mud-evennia": {
            "host": "another.mud",
            "port": "4000",
            "encoding": "utf8",
            "autologin": "connect {0} {1}",
            "default_script": None,
            "chars": {
                "evennia": ["name", "pass"],
            },
        },
    }

    styles = {
        "status": "reverse",
        "shadow": "bg:#440044",
        "prompt": "",
        "selected": "bg:#555555 fg:#eeeeee bold",
        "selected.connected": "bg:#555555 fg:#33ff33 bold",
        "normal": "fg:#aaaaaa",
        "normal.connected": "fg:#33aa33",
        "skyblue": "fg:skyblue",
        "yellow": "fg:yellow",
        "red": "fg:red",
        "green": "fg:green",
        "blue": "fg:blue",
        "link": "fg:green underline",
        "title": "bold",
        "value": "fg:green",
    }

    INFO_STYLE = "\x1b[48;5;22m\x1b[38;5;252m"  # "\x1b[38;2;0;128;255m"
    WARN_STYLE = "\x1b[48;5;220m\x1b[38;5;238m"
    ERR_STYLE = "\x1b[48;5;160m\x1b[38;5;252m"
    CLR_STYLE = "\x1b[0m"
