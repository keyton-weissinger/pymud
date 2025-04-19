"""Session modules functionality - handles loading, unloading, and reloading modules"""

from ..modules import ModuleInfo


class SessionModules:
    """Session modules functionality - handles loading, unloading, and reloading modules"""

    def load_module(self, module_names):
        """
        Module loading function.

        :param module_names: List of modules to load. When it's a tuple/list, loads a series of modules with the specified names; when it's a string, loads a single module.

        Examples:
            - session.load_module('mymodule'):  Loads the module corresponding to the file named mymodule.py
            - session.load_modules(['mymod1', 'mymod2']): Loads the modules corresponding to mymod1.py and mymod2.py files in sequence
        """
        if isinstance(module_names, (list, tuple)):
            for mod in module_names:
                mod = mod.strip()
                self._load_module(mod)

        elif isinstance(module_names, str):
            mod = module_names.strip()
            self._load_module(mod)

    def _load_module(self, module_name):
        """Load module with the specified name"""
        try:
            if module_name not in self._modules.keys():
                self._modules[module_name] = ModuleInfo(module_name, self)

            else:
                mod = self._modules[module_name]
                if isinstance(mod, ModuleInfo):
                    mod.reload()

        except Exception as e:
            import traceback

            self.error(
                f"Module {module_name} failed to load, exception: {e}, type: {type(e)}."
            )
            self.error(f"Exception traceback: {traceback.format_exc()}")

    def unload_module(self, module_names):
        """
        Module unloading function. When unloading a module, it will automatically call the unload method of the Configuration class object in the module.

        Generally use the #unload command to unload modules, rather than using the unload_module function in scripts

        :param module_names: List of modules to unload. When it's a tuple/list, unloads a series of modules with the specified names; when it's a string, unloads a single module.
        """
        if isinstance(module_names, (list, tuple)):
            for mod in module_names:
                mod = mod.strip()
                self._unload_module(mod)

        elif isinstance(module_names, str):
            mod = module_names.strip()
            self._unload_module(mod)

    def _unload_module(self, module_name):
        """Unload module with the specified name. Unloading supports modules that need Configuration to implement __unload__ or unload method"""
        if module_name in self._modules.keys():
            mod = self._modules.pop(module_name)
            if isinstance(mod, ModuleInfo):
                mod.unload()

        else:
            self.warning(f"Specified module name {module_name} is not loaded.")

    def reload_module(self, module_names=None):
        """
        Module reloading function.

        Generally use the #reload command to reload modules, rather than using the reload_module function in scripts

        :param module_names: List of modules to reload. When it's a tuple/list, unloads a series of modules with the specified names; when it's a string, unloads a single module. When not specified, reloads all loaded modules.
        """
        if module_names is None:
            for name, module in self._modules.items():
                if isinstance(module, ModuleInfo):
                    module.reload()

            self.info("All configuration modules have been completely reloaded.")

        elif isinstance(module_names, (list, tuple)):
            for mod in module_names:
                mod = mod.strip()
                if mod in self._modules.keys():
                    module = self._modules[mod]
                    if isinstance(module, ModuleInfo):
                        module.reload()
                else:
                    self.warning(
                        f"Specified module name {mod} is not loaded, cannot reload."
                    )

        elif isinstance(module_names, str):
            if module_names in self._modules.keys():
                module = self._modules[module_names]
                if isinstance(module, ModuleInfo):
                    module.reload()
            else:
                self.warning(
                    f"Specified module name {module_names} is not loaded, cannot reload."
                )
