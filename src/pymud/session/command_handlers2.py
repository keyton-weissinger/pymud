"""Session command handlers part 2 - additional system command handling functions"""

import pickle

from ..settings import Settings


class SessionCommandHandlers2:
    """Session command handlers part 2 - additional system command handling functions"""

    def handle_load(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #load, performs module loading operation for the current session. When loading multiple modules, separate them with spaces or commas.
        This function should not be called directly in code.

        Usage:
            - #load {mod1}: Loads the module with the specified name
            - #load {mod1} {mod2} ... {modn}: Loads multiple modules with the specified names
            - #load {mod1},{mod2},...{modn}: Loads multiple modules with the specified names
        """
        modules = ",".join(code.code[2:]).split(",")
        self.load_module(modules)

    def handle_reload(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #reload, reloads modules/plugins.
        This function should not be called directly in code.

        Usage:
            - #reload: Reloads all loaded modules
            - #reload {modname}: Reloads the module named modname
            - #reload {plugins}: Reloads the plugin named plugins
            - #reload {mod1} {mod2} ... {modn}: Reloads multiple modules/plugins with the specified names
            - #reload {mod1},{mod2},...{modn}: Reloads multiple modules/plugins with the specified names
        """
        args = list()
        if isinstance(code, object) and hasattr(code, "code"):
            args = code.code[2:]

        if len(args) == 0:
            self.reload_module()

        elif len(args) >= 1:
            modules = ",".join(args).split(",")
            for mod in modules:
                mod = mod.strip()
                if mod in self._modules.keys():
                    self.reload_module(mod)

                elif mod in self.plugins.keys():
                    self.application.reload_plugin(self.plugins[mod])
                    self.info(f"Plugin {mod} has been successfully reloaded!")
                else:
                    self.warning(
                        f"Specified name {mod} was not found as a module or a plugin, reload failed."
                    )

    def handle_unload(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #unload, unloads modules.
        This function should not be called directly in code.

        Usage:
            - #unload {modname}: Unloads the loaded module with the specified name
            - #unload {mod1} {mod2} ... {modn}: Unloads multiple modules/plugins with the specified names
            - #unload {mod1},{mod2},...{modn}: Unloads multiple modules/plugins with the specified names
        """
        args = code.code[2:]

        if len(args) == 0:
            modules = self._modules.values()
            self.unload_module(modules)
            self.reset()

        elif len(args) >= 1:
            modules = ",".join(args).split(",")
            self.unload_module(modules)

    def handle_modules(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #modules / #mods, displays the list of loaded modules. This command takes no parameters.
        This function should not be called directly in code.

        Usage:
            - #mods: Displays the list of all modules loaded in the current session
        """
        args = code.code[2:]

        if len(args) == 0:
            count = len(self._modules.keys())
            if count == 0:
                self.info(
                    "No modules have been loaded in the current session.", "MODULES"
                )
            else:
                self.info(
                    f"The current session has loaded {count} modules, including (in order of loading): {list(self._modules.keys())}",
                    "MODULES",
                )

        elif len(args) >= 1:
            modules = ",".join(args).split(",")
            for mod in modules:
                if mod in self._modules.keys():
                    module = self._modules[mod]
                    if hasattr(module, "ismainmodule") and module.ismainmodule:
                        self.info(
                            f"The module {module.name} contains the following configurations: {', '.join(module.config.keys())}"
                        )
                    else:
                        self.info(
                            f"Module {module.name} is a submodule and does not contain configurations."
                        )

                else:
                    self.info(
                        f"The module with the specified name {mod} does not exist in this session, it may not have been loaded yet"
                    )

    def handle_reset(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #reset, resets all scripts. This command takes no parameters.
        Reset operation will reset all triggers, commands, unfinished tasks, and clear all triggers, commands, aliases, and variables.
        This function should not be called directly in code.

        Usage:
            - #reset: Reset all scripts
        """
        self.reset()

    def handle_save(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #save, saves the current session variables (except for system variables and temporary variables) to a file. This command takes no parameters.
        System variables include %line, %copy, and %raw, while temporary variables are variables whose names start with an underscore.
        This function should not be called directly in code.

        Usage:
            - #save: Save current session variables
        """
        file = f"{self.name}.mud"

        with open(file, "wb") as fp:
            saved = dict()
            saved.update(self._variables)
            keys = list(saved.keys())
            for key in keys:
                if key.startswith("_"):
                    saved.pop(key)
            saved.pop("%line", None)
            saved.pop("%raw", None)
            saved.pop("%copy", None)
            pickle.dump(saved, fp)
            self.info(f"Session variable information has been saved to {file}")

    def handle_clear(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #clear / #cls, clears the current session buffer and display.
        This function should not be called directly in code.

        Usage:
            - #cls: Clear current session buffer and display
        """
        self.buffer.text = ""

    def handle_test(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #test / #show, trigger test command. Similar to the #show command in zmud.
        This function should not be called directly in code.

        Usage:
            - #test {some_text}: Tests how triggers respond when the server receives {some_text}. In this case, triggers do not actually respond.
            - #tt {some_text}: Different from #test in that if there is a matching trigger, the trigger will actually respond regardless of whether it is enabled.
        """
        cmd = code.code[1].lower()
        docallback = False
        if cmd == "test":
            docallback = True

        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        line = new_cmd_text[6:]  # Take all content after #test

        if "\n" in line:
            lines = line.split("\n")
        else:
            lines = []
            lines.append(line)

        info_all = []
        info_enabled = []  # Organize the content to be displayed for each line, then output them all at once, not line by line
        info_disabled = []
        triggered = 0
        triggered_enabled = 0
        triggered_disabled = 0

        tris_enabled = [
            tri
            for tri in self._triggers.values()
            if hasattr(tri, "enabled") and tri.enabled
        ]
        tris_enabled.sort(
            key=lambda tri: tri.priority if hasattr(tri, "priority") else 0
        )

        tris_disabled = [
            tri
            for tri in self._triggers.values()
            if hasattr(tri, "enabled") and not tri.enabled
        ]
        tris_disabled.sort(
            key=lambda tri: tri.priority if hasattr(tri, "priority") else 0
        )

        for raw_line in lines:
            tri_line = self.getPlainText(raw_line)

            block = False
            for tri in tris_enabled:
                if hasattr(tri, "raw") and tri.raw and hasattr(tri, "match"):
                    state = tri.match(raw_line, docallback=docallback)
                elif hasattr(tri, "match"):
                    state = tri.match(tri_line, docallback=docallback)
                else:
                    continue

                if (
                    hasattr(state, "result")
                    and hasattr(tri, "SUCCESS")
                    and state.result == tri.SUCCESS
                ):
                    triggered_enabled += 1
                    if not block:
                        triggered += 1
                        info_enabled.append(f"    {tri.__detailed__()} normal trigger.")
                        info_enabled.append(f"      Captured: {state.wildcards}")

                        if not hasattr(tri, "keepEval") or not tri.keepEval:
                            info_enabled.append(
                                f"      {Settings.WARN_STYLE}This trigger does not have keepEval enabled, it will block subsequent triggers.{Settings.CLR_STYLE}"
                            )
                            block = True
                    else:
                        info_enabled.append(
                            f"    {Settings.WARN_STYLE}{tri.__detailed__()} can trigger, but due to priority and keepEval settings, the trigger will not fire.{Settings.CLR_STYLE}"
                        )

            for tri in tris_disabled:
                if hasattr(tri, "raw") and tri.raw and hasattr(tri, "match"):
                    state = tri.match(raw_line, docallback=docallback)
                elif hasattr(tri, "match"):
                    state = tri.match(tri_line, docallback=docallback)
                else:
                    continue

                if (
                    hasattr(state, "result")
                    and hasattr(tri, "SUCCESS")
                    and state.result == tri.SUCCESS
                ):
                    triggered_disabled += 1
                    info_disabled.append(
                        f"    {Settings.WARN_STYLE}{tri.__detailed__()} can trigger, but is currently disabled.{Settings.CLR_STYLE}"
                    )

            if triggered_enabled + triggered_disabled > 0:
                info_all.append(
                    f"{Settings.INFO_STYLE}====={line} matches triggers that can fire: {triggered_enabled + triggered_disabled} total, {triggered} actually firing===={Settings.CLR_STYLE}"
                )

                if triggered_enabled > 0:
                    info_all.append(
                        f"{Settings.INFO_STYLE}Enabled and triggerable triggers: {triggered_enabled} total:{Settings.CLR_STYLE}"
                    )
                    info_all.extend(info_enabled)

                if triggered_disabled > 0:
                    info_all.append(
                        f"{Settings.INFO_STYLE}Disabled but triggerable triggers: {triggered_disabled} total:{Settings.CLR_STYLE}"
                    )
                    info_all.extend(info_disabled)

            else:
                info_all.append(f"Line {line} did not match any triggers.")

        for line in info_all:
            self.writetobuffer(line, newline=True)

    def handle_plugins(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #plugins, lists/loads plugins.
        This function should not be called directly in code.

        Usage:
            - #plugins: Lists all plugins loaded in the current application
        """
        if code.length == 2:
            self.info(
                f"Currently loaded {len(self.plugins)} plugins, including: {list(self.plugins.keys())}"
            )

        elif code.length == 3:
            plugin_name = code.code[2]
            if plugin_name in self.plugins.keys():
                plugin = self.plugins[plugin_name]
                if hasattr(plugin, "description"):
                    self.info(
                        f"Description of plugin {plugin_name}: {plugin.description}",
                        "PLUGIN",
                    )
                elif hasattr(plugin, "__doc__"):
                    self.info(
                        f"Description of plugin {plugin_name}: {plugin.__doc__}",
                        "PLUGIN",
                    )
                else:
                    self.info(
                        f"Plugin {plugin_name} does not provide description information.",
                        "PLUGIN",
                    )
            else:
                self.warning(
                    f"Plugin {plugin_name} not found, please check if your input is correct."
                )

    def handle_replace(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #replace, replaces the current line with the specified string. Same as #gag.
        #replace command is specialized for trigger response, calling it directly from the command line has no effect.
        This function should not be called directly in code.

        Usage:
            - #replace {str}

        Parameters:
            :str: String used to replace this line, if empty, completely replaces this line (gag)
        """
        if code.length > 2:
            text = " ".join(code.code[2:])
        else:
            text = ""

        self.replace(text)

    def handle_gag(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #gag, hides the display of this line (blocks the display of certain lines).
        #gag command is specialized for trigger response, calling it directly from the command line has no effect.
        This function should not be called directly in code.
        """
        self.replace("")

    def handle_py(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #py, executes specified Python code.
        This function should not be called directly in code.

        Usage:
            - #py {code}: Executes Python code
            - #py {code};{code};{code}: Executes Python code, multiple statements separated by semicolons

        :param code: Python code to execute
        """
        code_text = " ".join(code.code[2:])
        if len(code_text) == 0:
            self.warning("Python code cannot be empty.")
            return

        try:
            result = eval(code_text, globals(), {"session": self})
            if result != None:
                self.info(f"Execution result: {result}", "Python")
        except Exception:
            try:
                exec(code_text, globals(), {"session": self})
            except Exception as e:
                self.error(
                    f"Error occurred during Python code execution: {e}", "Python"
                )

    def handle_info(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #info, outputs info level prompt information. @ or % variables can be used in the command.
        This function should not be called directly in code.

        Usage:
            - #info {msg}

        Parameters:
            - msg: Information to output
        """
        if code.length > 2:
            new_cmd_text, new_code = code.expand(self, *args, **kwargs)
            msg = " ".join(new_code[2:])
            self.info(msg)

    def handle_warning(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #warning, outputs warning level warning information. @ or % variables can be used in the command.
        This function should not be called directly in code.

        Usage:
            - #warning {msg}

        Parameters:
            - msg: Warning information to output
        """
        if code.length > 2:
            new_cmd_text, new_code = code.expand(self, *args, **kwargs)
            msg = " ".join(new_code[2:])
            self.warning(msg)

    def handle_error(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #error, outputs error level error information. @ or % variables can be used in the command.
        This function should not be called directly in code.

        Usage:
            - #error {msg}

        Parameters:
            - msg: Error information to output
        """
        if code.length > 2:
            new_cmd_text, new_code = code.expand(self, *args, **kwargs)
            msg = " ".join(new_code[2:])
            self.error(msg)

    def handle_log(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #log, writes logging information. @ or % variables can be used in the command.
        This function should not be called directly in code.

        Usage:
            - #log {msg}

        Parameters:
            - msg: Log information to write
        """
        if code.length > 2:
            new_cmd_text, new_code = code.expand(self, *args, **kwargs)
            msg = " ".join(new_code[2:])
            self.log.info(msg)
