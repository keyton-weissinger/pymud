"""Session command handlers - implements all the system command handling functions"""

import asyncio

from ..settings import Settings


class SessionCommandHandlers:
    """Session command handlers - implements all the system command handling functions"""

    def handle_help(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #help, displays help information in the current session.
        When used without parameters, #help lists all available help topics.
        With parameters, it displays help for that system command. The # symbol is not needed in parameters.
        This function should not be called directly in code.

        Usage:
            - #help {topic}
            - When topic is not specified: Lists all available help topics.
            - When topic is specified: Lists help content for the specified topic. This help content is determined by the docstring of the called function.

        Parameters:
            :topic: Topic, supports all system commands. When typing the topic, please ignore the # symbol in the command
        """
        if code.length == 2:
            self._print_all_help()

        elif code.length == 3:
            topic = code.code[-1].lower()

            if topic in ("session",):
                command = getattr(self.application, f"handle_{topic}", None)
                docstring = command.__doc__
            elif topic in self._commands_alias.keys():
                command = self._commands_alias[topic]
                docstring = self._cmds_handler[command].__doc__
            elif topic in self._sys_commands:
                docstring = self._cmds_handler[topic].__doc__
            else:
                docstring = (
                    f"Topic {topic} not found, please check if your input is correct."
                )

            self.writetobuffer(docstring, True)

    def handle_exit(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #exit, exits the `PyMudApp` application.
        This function should not be called directly in code.

        *Note: When there are sessions still in connected state in the application, #exit will display a dialog box to confirm whether to close these sessions one by one*
        """
        self.application.act_exit()

    def handle_close(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #close, closes the current session and removes the current session from the session list of `PyMudApp`.
        This function should not be called directly in code.

        *Note: When the current session is in a connected state, #close will display a dialog box to confirm whether to close the session*
        """
        self.application.act_close_session()

    async def handle_wait(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #wait / #wa, asynchronously delays for a specified time, used for delay waiting between multiple commands.
        This function should not be called directly in code.

        Usage:
            - #wa {ms}

        Parameters:
            - ms: Wait time (milliseconds)
        """
        wait_time = code.code[2]
        if wait_time.isnumeric():
            msec = float(wait_time) / 1000.0
            await asyncio.sleep(msec)

    def handle_connect(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #connect / #con, connects to the remote server (only valid when the remote server is not connected).
        This function should not be called directly in code.
        """
        import math

        if not self.connected:
            self.open()
        else:
            duration = self._protocol.duration
            hour = duration // 3600
            min = (duration - 3600 * hour) // 60
            sec = duration % 60
            time_msg = ""
            if hour > 0:
                time_msg += f"{hour} hours"
            if min > 0:
                time_msg += f"{min} minutes"
            time_msg += f"{math.ceil(sec)} seconds"

            self.info("Already connected to the server for {}".format(time_msg))

    def handle_disconnect(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #disconnect / #dis, disconnects from the remote server (only valid when the remote server is already connected).
        This function should not be called directly in code.
        """
        self.disconnect()

    def handle_variable(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #variable / #var, operates session variables.
        This command can be used without parameters, with one parameter, or with two parameters.
        This function should not be called directly in code.

        Usage:
            - #var: Lists all variables in this session
            - #var {name}: Lists the value of the variable named {name} in this session
            - #var {name} {value}: Sets the value of the variable named {name} to {value} in this session, creates it if it doesn't exist
        """
        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        args = new_code[2:]

        if len(args) == 0:
            lines = self.buildDisplayLines(
                self._variables, f"  VARIABLE LIST IN SESSION {self.name}  "
            )

            for line in lines:
                self.writetobuffer(line, newline=True)

        elif len(args) == 1:
            if args[0] in self._variables.keys():
                obj = self.getVariable(args[0])
                var_dict = {args[0]: obj}
                lines = self.buildDisplayLines(
                    var_dict, f" VARIABLE [{args[0]}] IN SESSION {self.name} "
                )

                for line in lines:
                    self.writetobuffer(line, newline=True)

            else:
                self.warning(
                    f"Variable named {args[0]} does not exist in the current session"
                )

        elif len(args) == 2:
            val = None
            try:
                val = eval(args[1])
            except:
                val = args[1]

            self.setVariable(args[0], val)
            self.info(f"Successfully set variable {args[0]} to value {val}")

    def handle_global(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #global, operates global variables (shared across sessions).
        This command can be used without parameters, with one parameter, or with two parameters.
        This function should not be called directly in code.

        Usage:
            - #global: Lists all global variables
            - #global {name}: Lists the value of the global variable named {name}
            - #global {name} {value}: Sets the value of the global variable named {name} to {value}, creates it if it doesn't exist
        """
        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        args = new_code[2:]

        if len(args) == 0:
            lines = self.buildDisplayLines(
                self.application.globals, " GLOBAL VARIABLES LIST "
            )

            for line in lines:
                self.writetobuffer(line, newline=True)

        elif len(args) == 1:
            var = args[0]
            if var in self.application.globals.keys():
                var_dict = {var: self.application.get_globals(var)}
                lines = self.buildDisplayLines(var_dict, f" GLOBAL VARIABLE [{var}] ")

                for line in lines:
                    self.writetobuffer(line, newline=True)
            else:
                self.info(
                    "Variable named {} does not exist in the global space".format(var),
                    "Global variables",
                )

        elif len(args) == 2:
            val = None
            try:
                val = eval(args[1])
            except:
                val = args[1]
            self.application.set_globals(args[0], val)
            self.info(f"Successfully set global variable {args[0]} to value {val}")

    def _handle_objs(self, name: str, objs: dict, *args):
        if len(args) == 0:
            width = self.application.get_width()

            title = f"  {name.upper()} LIST IN SESSION {self.name}  "
            left = (width - len(title)) // 2
            right = width - len(title) - left
            self.writetobuffer("=" * left + title + "=" * right, newline=True)

            for id in sorted(objs.keys()):
                self.writetobuffer("  %r" % objs[id], newline=True)

            self.writetobuffer("=" * width, newline=True)

        elif len(args) == 1:
            if args[0] in objs.keys():
                obj = objs[args[0]]
                self.info(obj.__detailed__())
            else:
                self.warning(
                    f"No {name} with key {args[0]} exists in the current session, please check and try again."
                )

        elif len(args) == 2:
            # When the first parameter is an object name, process the object
            if args[0] in objs.keys():
                obj = objs[args[0]]
                if args[1] == "on":
                    obj.enabled = True
                    self.info(f"Object {obj}'s enabled state has been turned on.")
                elif args[1] == "off":
                    obj.enabled = False
                    self.info(f"Object {obj}'s enabled state has been disabled.")
                elif args[1] == "del":
                    obj.enabled = False
                    objs.pop(args[0])
                    self.info(f"Object {obj} has been deleted from the session.")
                else:
                    self.error(
                        f"The second parameter of #{name.lower()} command can only accept on/off/del"
                    )

            # When the first parameter is not an object name, create a new object
            else:
                pattern, code = args[0], args[1]
                if (len(pattern) >= 2) and (pattern[0] == "{") and (pattern[-1] == "}"):
                    pattern = pattern[1:-1]

                name = name.lower()
                try:
                    from ..objects import SimpleAlias, SimpleTimer, SimpleTrigger

                    if name == "alias":
                        ali = SimpleAlias(self, pattern, code)
                        self.addAlias(ali)
                        self.info(
                            f"Successfully created Alias {ali.id}: {ali.__repr__()}"
                        )
                    elif name == "trigger":
                        tri = SimpleTrigger(self, pattern, code)
                        self.addTrigger(tri)
                        self.info(
                            f"Successfully created Trigger {tri.id}: {tri.__repr__()}"
                        )
                    elif name == "timer":
                        ti = SimpleTimer(self, code)
                        self.addTimer(ti)
                        self.info(
                            f"Successfully created Timer {ti.id}: {ti.__repr__()}"
                        )
                    # elif name == "command":
                    #     cmd = SimpleCommand(self, pattern, code)
                    #     self.addCommand(cmd)
                    #     self.info("创建Command {} 成功: {}".format(cmd.id, cmd.__repr__()))
                except Exception as e:
                    self.error(f"Error occurred while creating {name}, error: {e}")

    def handle_alias(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #alias / #ali, manages alias objects.
        This function should not be called directly in code.

        Usage:
            - #alias: Lists all alias objects in this session
            - #alias {id}: Lists detailed information of the specified id alias object in this session
            - #alias {id} {on/off/del}: Performs enable/disable/delete operations on the specified id alias object
            - #alias {pattern} {code}: Creates an alias object
        """
        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        cmds = new_code[2:]
        self._handle_objs("Alias", self._aliases, *cmds)

    def handle_timer(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #timer / #ti, manages timer objects.
        This function should not be called directly in code.

        Usage:
            - #timer: Lists all timer objects in this session
            - #timer {id}: Lists detailed information of the specified id timer object in this session
            - #timer {id} {on/off/del}: Performs enable/disable/delete operations on the specified id timer object
            - #timer {code}: Creates a timer object
        """
        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        cmds = new_code[2:]
        self._handle_objs("Timer", self._timers, *cmds)

    def handle_command(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #command / #cmd, manages command objects.
        This function should not be called directly in code.

        Usage:
            - #command: Lists all command objects in this session
            - #command {id}: Lists detailed information of the specified id command object in this session
            - #command {id} {on/off/del}: Performs enable/disable/delete operations on the specified id command object
        """
        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        cmds = new_code[2:]
        self._handle_objs("Command", self._commands, *cmds)

    def handle_trigger(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #trigger / #tri / #action, manages trigger objects.
        This function should not be called directly in code.

        Usage:
            - #trigger: Lists all trigger objects in this session
            - #trigger {id}: Lists detailed information of the specified id trigger object in this session
            - #trigger {id} {on/off/del}: Performs enable/disable/delete operations on the specified id trigger object
            - #trigger {pattern} {code}: Creates a trigger object
        """
        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        cmds = new_code[2:]
        self._handle_objs("Trigger", self._triggers, *cmds)

    def handle_task(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #task, lists tasks running in the session.
        This function should not be called directly in code.

        Usage:
            - #task: Lists all tasks currently running in this session
        """
        width = self.application.get_width()
        title = f"  TASKS LIST IN SESSION {self.name}  "
        left = (width - len(title)) // 2
        right = width - len(title) - left
        self.writetobuffer("=" * left + title + "=" * right, newline=True)

        for task in sorted(self._tasks, key=lambda t: t.get_name()):
            self.writetobuffer(f"  {task.get_name()}", newline=True)

        self.writetobuffer("=" * width, newline=True)

    def handle_ignore(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #ignore / #ig / #t+/ #t-, sets the trigger ignore switch, similar in purpose to Mudlet's templineignore and tempEnableTimer.
        This function should not be called directly in code.

        Usage:
            - #ignore on or #t+: Temporarily sets trigger ignore, i.e., does not respond to server messages
            - #ignore off or #t-: Restores triggers to normal response
        """
        if code.length == 2:
            cmd = code.code[1].lower()

            if cmd == "t+":
                self._ignore = True
                self.info(
                    "Trigger ignore has been set, i.e., not responding to server responses."
                )
            elif cmd == "t-":
                self._ignore = False
                self.info("Trigger response has been restored.")
            else:
                self.info(
                    f"Trigger ignore state is {'enabled' if self._ignore else 'disabled'}, i.e., {'not responding' if self._ignore else 'responding'} to server responses."
                )

        elif code.length == 3:
            state = code.code[2].lower()

            if state == "on":
                self._ignore = True
                self.info(
                    "Trigger ignore has been set, i.e., not responding to server responses."
                )
            elif state == "off":
                self._ignore = False
                self.info("Trigger response has been restored.")
            else:
                self.warning(
                    f"#ignore command parameter {state} is invalid, valid values are on and off, case insensitive."
                )

    def handle_repeat(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #repeat / #rep, repeatedly executes the specified command.
        This function should not be called directly in code.

        Usage:
            - #repeat {num} {command}

        Parameters:
            - num: Number of repetitions, must be a positive integer. Repetition counts over 1000 will trigger a safety warning
            - command: The command to be repeated
        """
        cmds = code.code
        if code.length == 1:
            self.warning(
                f"{cmds[0]} {cmds[1]} command format is incorrect, format should be {cmds[1]} n command"
            )
            return

        if code.length == 2:
            self.warning(
                f"{cmds[0]} {cmds[1]} command format is incorrect, format should be {cmds[1]} n command"
            )
            return

        if code.length > 2:
            if cmds[2].isnumeric():
                times = int(cmds[2])
                if times <= 0:
                    self.warning(
                        f"{cmds[1]} command repetition parameter should be a positive integer!"
                    )
                    return

                if times > 1000:
                    self.warning(
                        f"Will execute command {times} times, please click confirm if correct, otherwise please cancel."
                    )
                    return

                self.create_task(self.handle_num(times, code=code, *args, **kwargs))

    async def handle_num(self, times, code=None, *args, **kwargs):
        """
        Execution function for embedded command #{num}, where num is a positive integer, repeatedly executes the specified command.
        This function should not be called directly in code.

        Usage:
            - #{num} {command}

        Parameters:
            - num: Number of repetitions, must be a positive integer
            - command: The command to be repeated
        """
        if code.length <= 2:
            self.warning(f"#{times} command needs parameters!")
            return

        cmdtext = " ".join(code.code[2:])
        for i in range(0, times):
            self.exec_command(cmdtext)
            await asyncio.sleep(Settings.client["repeat_interval"] / 1000.0)

    def handle_gmcp(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #gmcp, manages GMCP trigger objects.
        This function should not be called directly in code.

        Usage:
            - #gmcp: Lists all GMCP trigger objects in this session
            - #gmcp {id}: Lists detailed information of the specified id GMCP trigger object in this session
            - #gmcp {id} {on/off/del}: Performs enable/disable/delete operations on the specified id GMCP trigger object
        """
        new_cmd_text, new_code = code.expand(self, *args, **kwargs)
        cmds = new_code[2:]
        self._handle_objs("GMCPTrigger", self._gmcp, *cmds)

    def handle_message(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #message / #mess, outputs messages to the application message box.
        This function should not be called directly in code.

        Usage:
            - #message {msg}

        Parameters:
            - msg: The message to output
        """
        if code.length > 2:
            msg = " ".join(code.code[2:])
            self.application.writeToConsole(msg)

    def handle_all(self, code=None, *args, **kwargs):
        """
        Execution function for embedded command #all, executes the same command in all sessions in the application.
        This function should not be called directly in code.

        Usage:
            - #all {command}

        Parameters:
            - command: The command to execute
        """
        if code.length > 2:
            cmdtext = " ".join(code.code[2:])
            for sess in self.application.sessions.values():
                if sess.name != self.name:
                    sess.exec_command(cmdtext)
