import argparse
import json
import logging
import os
import platform
import shutil
import sys
from pathlib import Path

from .pymud import PyMudApp
from .settings import Settings

CFG_TEMPLATE = {
    "client": {
        "buffer_lines": 5000,  # Number of buffer lines to retain
        "interval": 10,  # Delay between auto-executed commands (ms)
        "auto_connect": True,  # Automatically connect after session is created
        "auto_reconnect": False,  # Automatically reconnect after unexpected disconnect
        "var_autosave": True,  # Automatically save session variables on disconnect
        "var_autoload": True,  # Automatically load session variables on startup
        "echo_input": False,
        "beautify": True,  # Helps fix ASCII alignment issues in PKUXKX
        "status_display": 1,  # Status bar display: 0 = hidden, 1 = bottom, 2 = right
        "status_height": 4,  # Height of the bottom status bar
        "status_width": 30,  # Width of the right status bar
    },
    "sessions": {
        "pkuxkx": {
            "host": "mud.pkuxkx.net",
            "port": "8081",
            "encoding": "utf8",
            "autologin": "{0};{1}",
            "default_script": "examples",
            "chars": {
                "display_title": ["yourid", "yourpassword", ""],
            },
        }
    },
    "keys": {
        "f3": "#ig",
        "f4": "#clear",
        "f11": "#close",
        "f12": "#exit",
    },
}


def init_pymud_env(args):
    print(
        f"Welcome to PyMUD, version {Settings.__version__}. It's recommended to create a new directory (anywhere) to store your PyMUD scripts and configuration."
    )
    print("Initializing environment for first-time setup...")

    dir = args.dir
    if dir:
        print(f"You specified {args.dir} as the script directory.")
        dir = Path(dir)
    else:
        dir = Path.home().joinpath("pkuxkx")
        system = platform.system().lower()
        dir_enter = input(
            f"Detected OS: {system}. Specify a directory for game scripts (will be created if it doesn't exist). Press Enter to use default [{dir}]: "
        )
        if dir_enter:
            dir = Path(dir_enter)

    if dir.exists() and dir.is_dir():
        print(f"Directory {dir} already exists. Switching to it...")
    else:
        print(f"Directory {dir} does not exist. Creating and switching to it...")
        dir.mkdir()

    os.chdir(dir)

    if os.path.exists("pymud.cfg"):
        print("Found existing pymud.cfg file. Using it to launch PyMUD...")
    else:
        print("No pymud.cfg found. Creating default configuration...")
        with open("pymud.cfg", mode="x") as fp:
            fp.writelines(json.dumps(CFG_TEMPLATE, indent=4))

    if not os.path.exists("examples.py"):
        from pymud import pkuxkx

        module_dir = pkuxkx.__file__
        shutil.copyfile(module_dir, "examples.py")
        print(
            "Sample script copied to script directory and added to default configuration."
        )

    print(f"You can modify the pymud.cfg file in {dir} to customize settings.")
    if system == "windows":
        print(f"To run PyMUD later, use: python -m pymud (from inside {dir})")
    else:
        print(f"To run PyMUD later, use: python3 -m pymud (from inside {dir})")

    input("Initialization complete. Press Enter to start PyMUD.")
    startApp(args)


def startApp(args):
    startup_path = Path(args.startup_dir).resolve()
    sys.path.append(f"{startup_path}")
    os.chdir(startup_path)

    if args.debug:
        logging.basicConfig(
            level=logging.NOTSET,
            format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
            datefmt="%m-%d %H:%M",
            filename=args.logfile,
            filemode="a" if args.filemode else "w",
            encoding="utf-8",
        )
    else:
        logging.basicConfig(
            level=logging.NOTSET,
            format="%(asctime)s %(name)-12s: %(message)s",
            datefmt="%m-%d %H:%M",
            handlers=[logging.NullHandler()],
        )

    cfg = startup_path.joinpath("pymud.cfg")
    cfg_data = None
    if os.path.exists(cfg):
        with open(cfg, "r", encoding="utf8", errors="ignore") as fp:
            cfg_data = json.load(fp)

    app = PyMudApp(cfg_data)
    app.run()


def main():
    parser = argparse.ArgumentParser(
        prog="pymud", description="PyMUD CLI argument help"
    )
    subparsers = parser.add_subparsers(help="'init' sets up the runtime environment")

    par_init = subparsers.add_parser(
        "init",
        description="Initialize PyMUD environment: create script directory, default config, and example script.",
    )
    par_init.add_argument(
        "-d",
        "--dir",
        dest="dir",
        metavar="dir",
        type=str,
        default="",
        help="Specify script directory to create. If omitted, a default based on OS is used.",
    )
    par_init.set_defaults(func=init_pymud_env)

    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        default=False,
        help="Enable debug mode. Logs everything at NOTSET level. Disabled by default.",
    )
    parser.add_argument(
        "-l",
        "--logfile",
        dest="logfile",
        metavar="logfile",
        default="pymud.log",
        help="Log filename in debug mode. Default is pymud.log in the current directory.",
    )
    parser.add_argument(
        "-a",
        "--appendmode",
        dest="filemode",
        action="store_true",
        default=True,
        help="Log file write mode. Default is append (True). Set to False to overwrite each run.",
    )
    parser.add_argument(
        "-s",
        "--startup_dir",
        dest="startup_dir",
        metavar="startup_dir",
        default=".",
        help="Startup directory (default: current dir). Allows launching PyMUD from any location.",
    )

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        startApp(args)


if __name__ == "__main__":
    main()
