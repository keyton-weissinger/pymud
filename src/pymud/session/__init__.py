"""
PyMud Session Package

This package provides the Session class and its components for MUD client session management.
All components are now properly organized in separate modules for better maintainability.
"""

from .command_handlers import SessionCommandHandlers
from .command_handlers2 import SessionCommandHandlers2
from .commands import SessionCommands
from .core import Session as BaseSession
from .display import SessionDisplay
from .io import SessionIO
from .modules import SessionModules
from .objects import SessionObjects
from .variables import SessionVariables


# Define the main Session class that combines the base Session with SessionCommandHandlers
class Session(BaseSession, SessionCommandHandlers):
    """
    Main session management object that implements all processing for each character.

    **Session objects are created and managed by the PyMudApp object. No manual creation is required.**

    This class is composed of the following modules:
    - core.py: Core functionality and initialization
    - io.py: Input/output related functions
    - variables.py: Variable management functionality
    - objects.py: Game object (triggers, aliases, etc.) management
    - modules.py: Module management functionality
    - commands.py: Command execution functionality
    - display.py: Display and formatting functionality
    - command_handlers.py: Command handler functions

    For complete documentation on using this class, please refer to each component module.
    """

    pass


__all__ = [
    "Session",
    "SessionIO",
    "SessionVariables",
    "SessionObjects",
    "SessionModules",
    "SessionCommands",
    "SessionDisplay",
    "SessionCommandHandlers",
    "SessionCommandHandlers2",
]
