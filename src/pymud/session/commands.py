"""Session commands module - handles command execution and processing"""

import asyncio

from ..settings import Settings


class SessionCommands:
    """Session commands module - handles command execution and processing"""

    def exec(self, cmd: str, name=None, *args, **kwargs):
        r"""
        Execute MUD commands using exec_command in the session named 'name'. When name is not specified, execute in the current session.

        - Both exec and writeline write data to the server. The difference is that the content executed by exec is first processed by Alias and Command, so the actual content sent to the remote may not be the same as cmd.
        - exec is implemented internally by calling exec_command, and exec can implement exactly the same functionality as exec_command
        - exec is a function added later, so exec_command is retained for backward compatibility of scripts

        :param cmd: The command to execute
        :param name: The name of the session to execute the command in, when not specified, execute in the current session.
        :param args: Reserved for compatibility and extensibility, no need to specify when calling in scripts
        :param kwargs: Reserved for compatibility and extensibility, no need to specify when calling in scripts
        """
        name = name or self.name
        if name in self.application.sessions.keys():
            session = self.application.sessions[name]
            session.exec_command(cmd, *args, **kwargs)
        else:
            self.error(f"Session named {name} does not exist")

    async def exec_async(self, cmd: str, name=None, *args, **kwargs):
        """
        Asynchronous form of exec. Execute MUD commands using exec_command_async in the session named 'name'. When name is not specified, execute in the current session.

        - exec_async is implemented internally by calling exec_command_async, and exec_async can implement exactly the same functionality as exec_command_async
        - exec_async is a function added later, so exec_command_async is retained for backward compatibility of scripts
        - When called asynchronously, this function will not return until the corresponding code has finished executing. Can be used to ensure command execution is complete.
        """
        name = name or self.name
        if name in self.application.sessions.keys():
            session = self.application.sessions[name]
            return await session.exec_command_async(cmd, *args, **kwargs)
        else:
            self.error(f"Session named {name} does not exist")

    def exec_code(self, cl, *args, **kwargs):
        """
        Execute MUD command parsed into CodeLine form (must be a single command). In general, scripts should not call this method, but should use exec/exec_command.

        This is the core execution function for commands, the origin of all real calls (in synchronous call situations)

        :param cl: CodeLine form of execution code
        :param args: Reserved for compatibility and extensibility
        :param kwargs: Reserved for compatibility and extensibility
        """
        if cl.length == 0:
            self.writeline("")

        elif cl.code[0] == "#":
            ## handle # command codes
            cmd = cl.code[1]
            if cmd.isnumeric():
                times = 0
                try:
                    times = int(cmd)
                except ValueError:
                    pass

                if times > 0:
                    self.create_task(self.handle_num(times, code=cl, *args, **kwargs))
                else:
                    self.warning("#{num} {cmd} can only support positive integers!")

            elif cmd in self.application.sessions.keys():
                name = cmd
                if cl.length == 2:
                    self.application.activate_session(name)
                elif cl.length > 2:
                    sess_cmd = " ".join(cl.code[2:])
                    session = self.application.sessions[name]
                    if len(sess_cmd) == 0:
                        session.writeline("")
                    else:
                        try:
                            from ..objects import CodeBlock

                            cb = CodeBlock(sess_cmd)
                            cb.execute(session, *args, **kwargs)
                        except Exception:
                            session.exec_command(sess_cmd)

            else:
                if cmd in self._commands_alias.keys():
                    cmd = self._commands_alias[cmd]

                handler = self._cmds_handler.get(cmd, None)
                if handler and callable(handler):
                    if asyncio.iscoroutinefunction(handler):
                        self.create_task(handler(code=cl, *args, **kwargs))
                    else:
                        handler(code=cl, *args, **kwargs)
                else:
                    self.warning(f"Unrecognized command: {cl.commandText}")

        else:
            cmdtext, code = cl.expand(self, *args, **kwargs)
            self.exec_text(cmdtext)

    async def exec_code_async(self, cl, *args, **kwargs):
        """
        This method is the asynchronous implementation of exec_code. In general, scripts should not call this method, but should use exec_command_async.

        This is the core execution function for commands, the origin of all real calls (in asynchronous call situations).

        When called asynchronously, this function will not return until the corresponding code has finished executing. Can be used to ensure command execution is complete.

        :param cl: CodeLine form of execution code
        :param args: Reserved for compatibility and extensibility
        :param kwargs: Reserved for compatibility and extensibility
        """
        if cl.length == 0:
            self.writeline("")

        elif cl.code[0] == "#":
            ## handle # command codes
            cmd = cl.code[1]
            if cmd.isnumeric():
                times = 0
                try:
                    times = int(cmd)
                except ValueError:
                    pass

                if times > 0:
                    await self.handle_num(times, code=cl, *args, **kwargs)
                else:
                    self.warning("#{num} {cmd} can only support positive integers!")

            elif cmd in self.application.sessions.keys():
                name = cmd
                sess_cmd = " ".join(cl.code[2:])
                session = self.application.sessions[name]
                if len(sess_cmd) == 0:
                    session.writeline("")
                else:
                    try:
                        from ..objects import CodeBlock

                        cb = CodeBlock(sess_cmd)
                        return await cb.async_execute(session, *args, **kwargs)
                    except Exception:
                        return await session.exec_command_async(sess_cmd)

            else:
                if cmd in self._commands_alias.keys():
                    cmd = self._commands_alias[cmd]

                handler = self._cmds_handler.get(cmd, None)
                if handler and callable(handler):
                    if asyncio.iscoroutinefunction(handler):
                        await self.create_task(handler(code=cl, *args, **kwargs))
                    else:
                        handler(code=cl, *args, **kwargs)
                else:
                    self.warning(f"Unrecognized command: {cl.commandText}")

        else:
            cmdtext, code = cl.expand(self, *args, **kwargs)
            return await self.exec_text_async(cmdtext)

    def exec_text(self, cmdtext: str):
        """
        Execute MUD command in text form. Must be a single command, definitely not starting with #, and no parameter substitution

        In general, scripts should not call this method, but should use exec/exec_command.

        :param cmdtext: Plain text command
        """
        isNotCmd = True
        for command in self._commands.values():
            if (
                hasattr(command, "enabled")
                and command.enabled
                and hasattr(command, "match")
            ):
                state = command.match(cmdtext)
                if hasattr(state, "result") and state.result == getattr(
                    command, "SUCCESS", 1
                ):
                    # Command task name uses command id for subsequent error checking
                    task_name = getattr(command, "id", None)
                    task_name = f"task-{task_name}" if task_name else None
                    self.create_task(command.execute(cmdtext), name=task_name)
                    isNotCmd = False
                    break

        # Then judge whether it is an alias
        if isNotCmd:
            notAlias = True
            for alias in self._aliases.values():
                if (
                    hasattr(alias, "enabled")
                    and alias.enabled
                    and hasattr(alias, "match")
                ):
                    state = alias.match(cmdtext)
                    if hasattr(state, "result") and state.result == getattr(
                        alias, "SUCCESS", 1
                    ):
                        notAlias = False
                        break

            # Neither are aliases, so it's a regular command, send directly
            if notAlias:
                self.writeline(cmdtext)

    async def exec_text_async(self, cmdtext: str):
        """
        This method is the asynchronous implementation of exec_text. In general, scripts should not call this method, but should use exec_async/exec_command_async.

        When called asynchronously, this function will not return until the corresponding code has finished executing. Can be used to ensure command execution is complete.
        """
        result = None
        isNotCmd = True
        for command in self._commands.values():
            if (
                hasattr(command, "enabled")
                and command.enabled
                and hasattr(command, "match")
            ):
                state = command.match(cmdtext)
                if hasattr(state, "result") and state.result == getattr(
                    command, "SUCCESS", 1
                ):
                    # Command task name uses command id for subsequent error checking
                    task_name = getattr(command, "id", None)
                    task_name = f"task-{task_name}" if task_name else None
                    result = await self.create_task(
                        command.execute(cmdtext), name=task_name
                    )
                    isNotCmd = False
                    break

        # Then judge whether it is an alias
        if isNotCmd:
            notAlias = True
            for alias in self._aliases.values():
                if (
                    hasattr(alias, "enabled")
                    and alias.enabled
                    and hasattr(alias, "match")
                ):
                    state = alias.match(cmdtext)
                    if hasattr(state, "result") and state.result == getattr(
                        alias, "SUCCESS", 1
                    ):
                        notAlias = False
                        break

            # Neither are aliases, so it's a regular command, send directly
            if notAlias:
                self.writeline(cmdtext)

        return result

    def exec_command(self, line: str, *args, **kwargs) -> None:
        """
        Execute MUD command in the current session. Multiple commands can be separated by a separator.

        - In this function, multiple commands are sent to the server at once without waiting for confirmation that the previous command has finished executing.
        - If you want to wait for each command to finish executing before moving on to the next command, you should use the asynchronous form of this function exec_command_async
        - The difference between this function and writeline is that this function will first perform Command and Alias parsing, and if not, use writeline to send
        - If line does not contain Command and Alias, it is equivalent to writeline
        - This function uses the same method as exec, except that it cannot specify the session name
        - exec is a function added later, so exec_command is retained for backward compatibility of scripts

        :param line: Content to specify
        :param args: Reserved for compatibility and extensibility
        :param kwargs: Reserved for compatibility and extensibility
        """
        if ("#" not in line) and ("@" not in line) and ("%" not in line):
            cmds = line.split(self.seperator)
            for cmd in cmds:
                self.exec_text(cmd)
        else:
            from ..objects import CodeBlock

            cb = CodeBlock(line)
            cb.execute(self)

    def exec_command_after(self, wait: float, line: str):
        """
        Delay execution of command exec_command for a period of time

        :param wait: float, delay wait time, unit is seconds.
        :param line: str, content to execute after delay wait ends
        """

        async def delay_task():
            await asyncio.sleep(wait)
            self.exec_command(line)

        self.create_task(delay_task())

    async def exec_command_async(self, line: str, *args, **kwargs):
        """
        Asynchronous form of exec_command. Execute MUD commands in the current session. Multiple commands can be separated by a separator.

        - When called asynchronously, multiple commands are sent to the server one by one, each command waits for confirmation that the previous command has finished executing, and multiple commands will insert a certain time wait between them
        - The interval wait time between multiple commands is specified by Settings.client["interval"], unit is ms
        - This function uses the same method as exec_async, except that it cannot specify the session name
        - exec_async is a function added later, so exec_command_async is retained for backward compatibility of scripts
        """
        result = None
        if ("#" not in line) and ("@" not in line) and ("%" not in line):
            cmds = line.split(self.seperator)
            for cmd in cmds:
                result = await self.exec_text_async(cmd)
                if Settings.client["interval"] > 0:
                    await asyncio.sleep(Settings.client["interval"] / 1000.0)
        else:
            from ..objects import CodeBlock

            cb = CodeBlock(line)
            result = await cb.async_execute(self)

        return result
