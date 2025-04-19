import importlib
import importlib.util
from abc import ABCMeta
from typing import Any

from .objects import BaseObject, Command


class ModuleInfo:
    """
    Manages loaded module files. This class is managed by the Session class and should not be manually created or modified.

    For details on module classification and usage, see `scripts.html`.

    :param module_name: Name of the module (same as used in `import xxx`)
    :param session: The session that loads/creates this module
    """

    def __init__(self, module_name: str, session):
        self.session = session
        self._name = module_name
        self._ismainmodule = False
        self.load()

    def _load(self, reload=False):
        result = True
        if reload:
            self._module = importlib.reload(self._module)
        else:
            self._module = importlib.import_module(self.name)
        self._config = {}

        for attr_name in dir(self._module):
            attr = getattr(self._module, attr_name)
            if isinstance(attr, type) and attr.__module__ == self._module.__name__:
                if attr_name == "Configuration" or issubclass(attr, IConfig):
                    try:
                        self._config[f"{self.name}.{attr_name}"] = attr(
                            self.session, reload=reload
                        )
                        self.session.info(
                            f"Config object {self.name}.{attr_name} {'reloaded' if reload else 'created'} successfully."
                        )
                    except Exception as e:
                        result = False
                        self.session.error(
                            f"Failed to create config object {self.name}.{attr_name}. Error: {e}"
                        )

        self._ismainmodule = bool(self._config)
        return result

    def _unload(self):
        for key, config in self._config.items():
            if isinstance(config, Command):
                # Command objects automatically call their unload methods when removed from session, avoid recursion
                self.session.delObject(config)
            else:
                if hasattr(config, "__unload__"):
                    unload = getattr(config, "__unload__")
                    if callable(unload):
                        unload()
                if hasattr(config, "unload"):
                    unload = getattr(config, "unload")
                    if callable(unload):
                        unload()
                if isinstance(config, BaseObject):
                    self.session.delObject(config)

            del config
        self._config.clear()

    def load(self):
        "Load the module"
        if self._load():
            self.session.info(
                f"{'Main' if self.ismainmodule else 'Sub'} config module {self.name} loaded."
            )
        else:
            self.session.error(
                f"Failed to load {'main' if self.ismainmodule else 'sub'} config module {self.name}."
            )

    def unload(self):
        "Unload the module"
        self._unload()
        self._loaded = False
        self.session.info(
            f"{'Main' if self.ismainmodule else 'Sub'} config module {self.name} unloaded."
        )

    def reload(self):
        "Reload the module after updates"
        self._unload()
        self._load(reload=True)
        self.session.info(
            f"{'Main' if self.ismainmodule else 'Sub'} config module {self.name} reloaded."
        )

    @property
    def name(self):
        "Read-only: module name"
        return self._name

    @property
    def module(self):
        "Read-only: imported module object"
        return self._module

    @property
    def config(self):
        "Read-only dict of config instances (Configuration class or IConfig subclasses, if any)"
        return self._config

    @property
    def ismainmodule(self):
        "Read-only: whether this is the main config module"
        return self._ismainmodule


class IConfig(metaclass=ABCMeta):
    """
    Base interface for config types managed by PyMUD.

    To have PyMUD auto-manage a config type, inherit from IConfig and ensure the constructor accepts only one required argument: session.

    When PyMUD auto-creates an IConfig instance, it may pass a `reload` (bool) argument in kwargs. Use this to adjust behavior depending on whether the module is being loaded or reloaded.
    """

    def __init__(self, session, *args, **kwargs):
        self.session = session

    def __unload__(self):
        if self.session:
            self.session.delObject(self)


class Plugin:
    """
    Manages loaded plugin files. This class is managed by PyMudApp and should not be created manually.

    For plugin details, see `plugins.html`.

    :param name: Plugin filename, e.g. 'myplugin.py'
    :param location: Directory where the plugin is located. PyMUD auto-loads plugins from both the PyMUD package and current working directory.
    """

    def __init__(self, name, location):
        self._plugin_file = name
        self._plugin_loc = location
        self.reload()

    def reload(self):
        "Load or reload the plugin"
        self.modspec = importlib.util.spec_from_file_location(
            self._plugin_file[:-3], self._plugin_loc
        )
        self.mod = importlib.util.module_from_spec(self.modspec)
        self.modspec.loader.exec_module(self.mod)

        self._app_init = self._load_mod_function("PLUGIN_PYMUD_START")
        self._session_create = self._load_mod_function("PLUGIN_SESSION_CREATE")
        self._session_destroy = self._load_mod_function("PLUGIN_SESSION_DESTROY")
        self._app_destroy = self._load_mod_function("PLUGIN_PYMUD_DESTROY")

    def _load_mod_function(self, func_name):
        # Default fallback if the plugin file doesn't define a function
        def default_func(*args, **kwargs):
            pass

        result = default_func
        if func_name in self.mod.__dict__:
            func = self.mod.__dict__[func_name]
            if callable(func):
                result = func
        return result

    @property
    def name(self):
        "Plugin name, defined by the PLUGIN_NAME constant in the plugin file"
        return self.mod.__dict__["PLUGIN_NAME"]

    @property
    def desc(self):
        "Plugin description, defined by the PLUGIN_DESC constant in the plugin file"
        return self.mod.__dict__["PLUGIN_DESC"]

    @property
    def help(self):
        "Plugin help text, pulled from the plugin module's docstring"
        return self.mod.__doc__

    def onAppInit(self, app):
        """
        Called when the PyMUD app starts. Delegates to PLUGIN_PYMUD_START in the plugin.
        :param app: The PyMudApp instance
        """
        self._app_init(app)

    def onSessionCreate(self, session):
        """
        Called when a new session is created. Delegates to PLUGIN_SESSION_CREATE in the plugin.
        :param session: The new session instance
        """
        self._session_create(session)

    def onSessionDestroy(self, session):
        """
        Called when a session is closed (not just disconnected). Delegates to PLUGIN_SESSION_DESTROY in the plugin.
        :param session: The closed session instance
        """
        self._session_destroy(session)

    def onAppDestroy(self, app):
        """
        Called when the PyMUD app is closing. Delegates to PLUGIN_PYMUD_DESTROY in the plugin.
        :param app: The PyMudApp instance
        """
        self._app_destroy(app)

    def __getattr__(self, __name: str) -> Any:
        if hasattr(self.mod, __name):
            return self.mod.__getattribute__(__name)
