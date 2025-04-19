"""
Objects supported in MUD sessions
"""

import asyncio
import logging
import re
from collections import namedtuple
from collections.abc import Iterable
from typing import Any

from .settings import Settings


class CodeLine:
    """
    Executable code block (single line) in PyMUD, should not be called directly by scripts.
    If scripts need to generate their own code blocks, use CodeBlock instead.
    """

    @classmethod
    def create_line(cls, line: str):
        hasvar = False
        code_params = []
        arg = ""
        brace_count, single_quote, double_quote = 0, 0, 0

        if len(line) > 0:
            if line[0] == "#":
                start_idx = 1
                code_params.append("#")
            else:
                start_idx = 0

            for i in range(start_idx, len(line)):
                ch = line[i]
                if ch == "{":
                    brace_count += 1
                    arg += ch
                elif ch == "}":
                    brace_count -= 1
                    if brace_count < 0:
                        raise Exception("Invalid code block, unmatched braces")
                    arg += ch
                elif ch == "'":
                    if single_quote == 0:
                        single_quote = 1
                    elif single_quote == 1:
                        single_quote = 0
                elif ch == '"':
                    if double_quote == 0:
                        double_quote = 1
                    elif double_quote == 1:
                        double_quote = 0

                elif ch == " ":
                    if (
                        (brace_count == 0)
                        and (double_quote == 0)
                        and (single_quote == 0)
                    ):
                        code_params.append(arg)
                        arg = ""
                    else:
                        arg += ch
                else:
                    arg += ch

            if (single_quote > 0) or (double_quote > 0):
                raise Exception("Unmatched quotes")

            if arg:
                code_params.append(arg)
                if arg[0] in ("@", "%"):
                    hasvar = True

            syncmode = "dontcare"
            if len(code_params) >= 2:
                if code_params[0] == "#":
                    if code_params[1] in ("gag", "replace"):
                        syncmode = "sync"
                    elif code_params[1] in ("wa", "wait"):
                        syncmode = "async"

            return (
                syncmode,
                hasvar,
                tuple(code_params),
            )
        else:
            return syncmode, hasvar, tuple()

    def __init__(self, _code: str) -> None:
        self.__code = _code
        self.__syncmode, self.__hasvar, self.code = CodeLine.create_line(_code)

    @property
    def length(self):
        return len(self.code)

    @property
    def hasvar(self):
        return self.__hasvar

    @property
    def commandText(self):
        return self.__code

    @property
    def syncMode(self):
        return self.__syncmode

    def execute(self, session, *args, **kwargs):
        session.exec_code(self, *args, **kwargs)

    def expand(self, session, *args, **kwargs):
        new_code_str = self.__code
        new_code = []

        line = kwargs.get("line", None) or session.getVariable("%line", "None")
        raw = kwargs.get("raw", None) or session.getVariable("%raw", "None")
        wildcards = kwargs.get("wildcards", None)

        for item in self.code:
            if len(item) == 0:
                continue
            # %1~%9, specifically refers to the matched content in captures
            if item in (f"%{i}" for i in range(1, 10)):
                idx = int(item[1:])
                if idx <= len(wildcards):
                    item_val = wildcards[idx - 1]
                else:
                    item_val = "None"
                new_code.append(item_val)
                new_code_str = new_code_str.replace(item, f"{item_val}", 1)

            # System variables, starting with %
            elif item == "%line":
                new_code.append(line)
                new_code_str = new_code_str.replace(item, f"{line}", 1)

            elif item == "%raw":
                new_code.append(raw)
                new_code_str = new_code_str.replace(item, f"{raw}", 1)

            elif item[0] == "%":
                item_val = session.getVariable(item, "")
                new_code.append(item_val)
                new_code_str = new_code_str.replace(item, f"{item_val}", 1)

            # Non-system variables, starting with @, add @ before variable name to reference
            elif item[0] == "@":
                item_val = session.getVariable(item[1:], "")
                new_code.append(item_val)
                new_code_str = new_code_str.replace(item, f"{item_val}", 1)

            else:
                new_code.append(item)

        return new_code_str, new_code

    async def async_execute(self, session, *args, **kwargs):
        return await session.exec_code_async(self, *args, **kwargs)


class CodeBlock:
    """
    Executable code block in PyMUD, can perform command and alias detection, and complete variable substitution.

    In general, you don't need to manually create CodeBlock objects, but use strings directly in SimpleTrigger, SimpleAlias, and other types. Or text entered at the command line will automatically create them.

    :param code: The code itself. Can be single line, multi-line, and multi-layer code blocks
    """

    @classmethod
    def create_block(cls, code: str) -> tuple:
        "Create code block and return the object itself"
        # If block is wrapped in {}, remove the braces and decompose directly

        if (len(code) >= 2) and (code[0] == "{") and (code[-1] == "}"):
            code = code[1:-1]

        code_lines = []
        line = ""
        brace_count = 0
        for i in range(0, len(code)):
            ch = code[i]
            if ch == "{":
                brace_count += 1
                line += ch
            elif ch == "}":
                brace_count -= 1
                if brace_count < 0:
                    raise Exception("Invalid code block, unmatched braces")
                line += ch
            elif ch == ";":
                if brace_count == 0:
                    code_lines.append(line)
                    line = ""
                else:
                    line += ch
            else:
                line += ch

        if line:
            code_lines.append(line)

        if len(code_lines) == 1:
            return (CodeLine(code),)
        else:
            codes = []
            for line in code_lines:
                codes.extend(CodeBlock.create_block(line))

            return tuple(codes)

    def __init__(self, code) -> None:
        self.__code = code
        self.codes = CodeBlock.create_block(code)

        self.__syncmode = "dontcare"

        for code in self.codes:
            if isinstance(code, CodeLine):
                if code.syncMode == "dontcare":
                    continue
                elif code.syncMode == "sync":
                    if self.__syncmode in ("dontcare", "sync"):
                        self.__syncmode = "sync"
                    elif self.__syncmode == "async":
                        self.__syncmode = "conflict"
                        break

                elif code.syncMode == "async":
                    if self.__syncmode in ("dontcare", "async"):
                        self.__syncmode = "async"
                    elif self.__syncmode == "sync":
                        self.__syncmode = "conflict"
                        break

    @property
    def syncmode(self):
        """
        Read-only property: Synchronization mode. Automatically determined based on code content when creating the code block.

        This property has four possible values:
            - ``dontcare``: Both sync and async are acceptable, neither forced sync nor forced async commands exist
            - ``sync``: Forced sync, only forced sync mode commands and other non-sync/async commands exist
            - ``async``: Forced async, only forced async mode commands and other non-sync/async commands exist
            - ``conflict``: Mode conflict, both forced sync and forced async commands exist simultaneously

        Forced sync mode commands include:
            - #gag
            - #replace

        Forced async mode commands include:
            - #wait
        """

        return self.__syncmode

    def execute(self, session, *args, **kwargs):
        """
        Execute this CodeBlock. Check syncmode before execution.
        - Only use synchronous execution when syncmode is sync.
        - Use asynchronous execution for all other syncmode values
        - When syncmode is conflict, sync commands are disabled and a warning is printed

        :param session: Session instance for command execution
        :param args: For compatibility and expansion, used for variable substitution and other purposes
        :param kwargs: For compatibility and expansion, used for variable substitution and other purposes
        """
        sync = kwargs.get("sync", None)
        if sync == None:
            if self.syncmode in ("dontcare", "async"):
                sync = False
            elif self.syncmode == "sync":
                sync = True
            elif self.syncmode == "conflict":
                session.warning(
                    "This command contains both forced sync and forced async commands, async execution will be used, sync commands will be disabled."
                )
                sync = False

        if sync:
            for code in self.codes:
                if isinstance(code, CodeLine):
                    code.execute(session, *args, **kwargs)
        else:
            session.create_task(self.async_execute(session, *args, **kwargs))

    async def async_execute(self, session, *args, **kwargs):
        """
        Execute this CodeBlock asynchronously. Parameters are the same as execute.
        """
        result = None
        for code in self.codes:
            if isinstance(code, CodeLine):
                result = await code.async_execute(session, *args, **kwargs)

            if Settings.client["interval"] > 0:
                await asyncio.sleep(Settings.client["interval"] / 1000.0)

        session.clean_finished_tasks()
        return result


class BaseObject:
    """
    Base class for objects supported in MUD sessions.

    :param session: The session object this belongs to
    :param args: For compatibility and expansion
    :param kwargs: For compatibility and expansion

    Keywords supported in kwargs:
        :id: Unique ID. If not specified, defaults to __abbr__ + UniqueID
        :group: Group name. If not specified, defaults to empty string
        :enabled: Enabled state. If not specified, defaults to True
        :priority: Priority, smaller value means higher priority. If not specified, defaults to 100
        :timeout: Timeout in seconds. If not specified, defaults to 10
        :sync: Sync mode. If not specified, defaults to True
        :oneShot: One-time execution flag. If not specified, defaults to False
        :onSuccess: Success callback function. If not specified, defaults to self.onSuccess
        :onFailure: Failure callback function. If not specified, defaults to self.onFailure
        :onTimeout: Timeout callback function. If not specified, defaults to self.onTimeout
    """

    State = namedtuple("State", ("result", "id", "line", "wildcards"))

    NOTSET = N = -1
    FAILURE = F = 0
    SUCCESS = S = 1
    TIMEOUT = T = 2
    ABORT = A = 3

    __abbr__ = "obj"
    "Internal abbreviation code prefix"

    def __init__(self, session, *args, **kwargs):
        from .session import Session

        if isinstance(session, Session):
            self.session = session
        else:
            assert "session must be an instance of class Session!"

        self._enabled = True  # give a default value
        self.log = logging.getLogger(f"pymud.{self.__class__.__name__}")
        self.id = kwargs.get("id", session.getUniqueID(self.__class__.__abbr__))
        self.group = kwargs.get("group", "")  # Group
        self.enabled = kwargs.get("enabled", True)  # Enabled or not
        self.priority = kwargs.get("priority", 100)  # Priority
        self.timeout = kwargs.get("timeout", 10)  # Timeout
        self.sync = kwargs.get("sync", True)  # Sync mode, default
        self.oneShot = kwargs.get("oneShot", False)  # One-time execution, not default

        self.args = args
        self.kwarg = kwargs

        # Success, failure, timeout handler functions (if specified), otherwise use the class's custom functions
        self._onSuccess = kwargs.get("onSuccess", self.onSuccess)
        self._onFailure = kwargs.get("onFailure", self.onFailure)
        self._onTimeout = kwargs.get("onTimeout", self.onTimeout)

        self.log.debug(f"Object instance {self} created successfully.")

        self.session.addObject(self)

    @property
    def enabled(self):
        "Read-write property, enable or disable this object"
        return self._enabled

    @enabled.setter
    def enabled(self, en: bool):
        self._enabled = en

    def onSuccess(self, *args, **kwargs):
        "Default callback function executed after success"
        self.log.debug(f"{self} default success callback function executed.")

    def onFailure(self, *args, **kwargs):
        "Default callback function executed after failure"
        self.log.debug(f"{self} default failure callback function executed.")

    def onTimeout(self, *args, **kwargs):
        "Default callback function executed after timeout"
        self.log.debug(f"{self} default timeout callback function executed.")

    def debug(self, msg):
        "Record debug information in logging"
        self.log.debug(msg)

    def info(self, msg, *args):
        "Output info in session if session exists; output info in logging if not"
        if self.session:
            self.session.info(msg, *args)
        else:
            self.log.info(msg)

    def warning(self, msg, *args):
        "Output warning in session if session exists; output warning in logging if not"
        if self.session:
            self.session.warning(msg, *args)
        else:
            self.log.warning(msg)

    def error(self, msg, *args):
        "Output error in session if session exists; simultaneously output error in logging"
        if self.session:
            self.session.error(msg, *args)
        else:
            self.log.error(msg)

    def __repr__(self) -> str:
        return self.__detailed__()

    def __detailed__(self) -> str:
        group = f'group = "{self.group}" ' if self.group else ""
        return f'<{self.__class__.__name__}> id = "{self.id}" {group}enabled = {self.enabled}'


class GMCPTrigger(BaseObject):
    """
    GMCP Trigger class, inherits from BaseObject.

    GMCP triggers process data based on the GMCP protocol, and their usage is similar to Trigger objects

    But GMCPTrigger must be triggered by a specified name, and when triggered, its value is passed directly to the object itself

    :param session: The session this object belongs to
    :param name: The GMCP name corresponding to the trigger
    """

    def __init__(self, session, name, *args, **kwargs):
        self.event = asyncio.Event()
        self.value = None
        super().__init__(session, id=name, *args, **kwargs)

    def __del__(self):
        self.reset()

    def reset(self):
        "Reset event, used for async execution"
        self.event.clear()

    async def triggered(self):
        """
        Awaitable function for async triggering. Its usage is similar to Trigger.triggered(), and its parameters and return values are compatible with it.
        """
        self.reset()
        await self.event.wait()
        state = BaseObject.State(True, self.id, self.line, self.value)
        self.reset()
        return state

    def __call__(self, value) -> Any:
        try:
            # import json
            value_exp = eval(value)
        except:
            value_exp = value

        self.line = value
        self.value = value_exp

        if callable(self._onSuccess):
            self.event.set()
            self._onSuccess(self.id, value, value_exp)

    def __detailed__(self) -> str:
        group = f'group = "{self.group}" ' if self.group else ""
        return f'<{self.__class__.__name__}> name = "{self.id}" value = "{self.value}" {group}enabled = {self.enabled} '


class MatchObject(BaseObject):
    """
    Objects that support content matching, including Alias, Trigger, Command and their subclass objects. Inherits from BaseObject

    :param session: Same as BaseObject, the session this object belongs to
    :param patterns: Patterns for matching. See patterns property for details
    :param args: For compatibility and expansion
    :param kwargs: For compatibility and expansion

    MatchObject adds some new kwargs keywords, including:
        :ignoreCase: Ignore case, default is False
        :isRegExp: Whether it's a regular expression, default is True
        :keepEval: Whether to continue matching, default is False
        :raw: Whether to match raw data containing VT100 ANSI markers, default is False
    """

    __abbr__ = "mob"

    def __init__(self, session, patterns, *args, **kwargs):
        self.ignoreCase = kwargs.get("ignoreCase", False)  # Ignore case, not default
        self.isRegExp = kwargs.get("isRegExp", True)  # Regular expression, default
        self.expandVar = kwargs.get(
            "expandVar", True
        )  # Expand variables (replace variables with values), default
        self.keepEval = kwargs.get("keepEval", False)  # Don't interrupt, not default
        self.raw = kwargs.get(
            "raw", False
        )  # Raw data matching. When matching raw data, VT100 instructions are not parsed

        self.wildcards = []
        self.lines = []
        self.event = asyncio.Event()

        self.patterns = patterns

        super().__init__(session, patterns=patterns, *args, **kwargs)

    def __del__(self):
        pass

    @property
    def patterns(self):
        """
        Read-write property, matching patterns for this object. This property can be dynamically changed at runtime, effective immediately.

        - The patterns in the constructor specify the initial matching patterns.
        - This property supports both string and other iterable objects (such as tuples, lists) in two forms.
            - When it's a string, single-line matching mode is used
            - When it's an iterable object, multi-line matching mode is used. The number of lines in multi-line mode is determined by the iterable object.
        """
        return self._patterns

    @patterns.setter
    def patterns(self, patterns):
        self._patterns = patterns

        if isinstance(patterns, str):
            self.multiline = False
            self.linesToMatch = 1
        elif isinstance(patterns, Iterable):
            self.multiline = True
            self.linesToMatch = len(patterns)

        if self.isRegExp:
            flag = 0
            if self.ignoreCase:
                flag = re.I
            if not self.multiline:
                self._regExp = re.compile(
                    self.patterns, flag
                )  # Consider adding flags here
            else:
                self._regExps = []
                for line in self.patterns:
                    self._regExps.append(re.compile(line, flag))

                self.linesToMatch = len(self._regExps)
                self._mline = 0

    def reset(self):
        "Reset event, used for async execution without waiting for results. Only effective for async."
        self.event.clear()

    def set(self):
        "Set event flag, can be used to manually force triggering, only effective for async triggers."
        self.event.set()

    def match(self, line: str, docallback=True) -> BaseObject.State:
        """
        Matching function. Called by Session.

        :param line: Data line to match
        :param docallback: Whether to execute callback function after successful match, default is True

        :return: BaseObject.State type, a named tuple object containing result, id, name, line, wildcards
        """
        result = self.NOTSET

        if not self.multiline:  # Not multi-line
            if self.isRegExp:
                m = self._regExp.match(line)
                if m:
                    result = self.SUCCESS
                    self.wildcards.clear()
                    if len(m.groups()) > 0:
                        self.wildcards.extend(m.groups())

                    self.lines.clear()
                    self.lines.append(line)
            else:
                # if line.find(self.patterns) >= 0:
                # if line == self.patterns:
                if self.patterns in line:
                    result = self.SUCCESS
                    self.lines.clear()
                    self.lines.append(line)
                    self.wildcards.clear()

        else:  # Multi-line matching case
            # multilines match. For multi-line matching, limited by the way lines are captured, must go line by line, setting state flags for processing.
            if self._mline == 0:  # When matching hasn't started yet, match the 1st line
                m = self._regExps[0].match(line)
                if m:
                    self.lines.clear()
                    self.lines.append(line)
                    self.wildcards.clear()
                    if len(m.groups()) > 0:
                        self.wildcards.extend(m.groups())
                    self._mline = 1  # Next state (middle line)
            elif (self._mline > 0) and (self._mline < self.linesToMatch - 1):
                m = self._regExps[self._mline].match(line)
                if m:
                    self.lines.append(line)
                    if len(m.groups()) > 0:
                        self.wildcards.extend(m.groups())
                    self._mline += 1
                else:
                    self._mline = 0
            elif self._mline == self.linesToMatch - 1:  # Final line
                m = self._regExps[self._mline].match(line)
                if m:
                    self.lines.append(line)
                    if len(m.groups()) > 0:
                        self.wildcards.extend(m.groups())
                    result = self.SUCCESS

                self._mline = 0

        state = BaseObject.State(
            result, self.id, "\n".join(self.lines), tuple(self.wildcards)
        )

        # When executing using the callback method, execute the function callback (only when both self.sync and docallback are true)
        # When docallback is true, it's actually matching and triggering, when false, it only returns the match result without actually triggering
        if docallback:
            if self.sync:
                if state.result == self.SUCCESS:
                    self._onSuccess(state.id, state.line, state.wildcards)
                elif state.result == self.FAILURE:
                    self._onFailure(state.id, state.line, state.wildcards)
                elif state.result == self.TIMEOUT:
                    self._onTimeout(state.id, state.line, state.wildcards)

            if state.result == self.SUCCESS:
                self.event.set()

        self.state = state
        return state

    async def matched(self) -> BaseObject.State:
        """
        Async mode of the match function, returns only after matching succeeds. Returns BaseObject.state

        Async matching mode is used for Trigger's async mode and Command matching.
        """
        # Wait, then reset
        try:
            self.reset()
            await self.event.wait()
            self.reset()
        except Exception as e:
            self.error(f"Exception encountered in async execution, {e}")

        return self.state

    def __detailed__(self) -> str:
        group = f'group = "{self.group}" ' if self.group else ""
        return f'<{self.__class__.__name__}> id = "{self.id}" {group}enabled = {self.enabled} patterns = "{self.patterns}"'


class Alias(MatchObject):
    """
    Alias type, inherits from MatchObject.

    Its connotation is exactly the same as MatchObject, only the abbreviation is overridden.
    """

    __abbr__ = "ali"


class SimpleAlias(Alias):
    """
    SimpleAlias type, inherits from Alias, includes all functionality of Alias, and creates a use case for onSuccess using the CodeBlock object.

    :param session: The session this object belongs to, same as MatchObject
    :param patterns: Matching patterns, same as MatchObject
    :param code: str, code to execute when matching succeeds, implemented using CodeBlock
    """

    def __init__(self, session, patterns, code, *args, **kwargs):
        self._code = code
        self._codeblock = CodeBlock(code)
        super().__init__(session, patterns, *args, **kwargs)

    def onSuccess(self, id, line, wildcards):
        "Overrides the default onSuccess method of the base class, executes the code parameter passed in the constructor using CodeBlock"
        self._codeblock.execute(self.session, id=id, line=line, wildcards=wildcards)

    def __detailed__(self) -> str:
        group = f'group = "{self.group}" ' if self.group else ""
        return f'<{self.__class__.__name__}> id = "{self.id}" {group}enabled = {self.enabled} patterns = "{self.patterns}" code = "{self._code}"'

    def __repr__(self) -> str:
        return self.__detailed__()


class Trigger(MatchObject):
    """
    Trigger type, inherits from MatchObject.

    Its connotation is exactly the same as MatchObject, only the abbreviation is overridden and an async triggered method is added.
    """

    __abbr__ = "tri"

    def __init__(self, session, patterns, *args, **kwargs):
        super().__init__(session, patterns, *args, **kwargs)
        self._task = None

    async def triggered(self):
        """
        Awaitable function for async triggering. Implemented internally through MatchObject.matched

        The difference is in the management of the created matched task.
        """
        if isinstance(self._task, asyncio.Task) and (not self._task.done()):
            self._task.cancel()

        self._task = self.session.create_task(self.matched())
        return await self._task


class SimpleTrigger(Trigger):
    """
    SimpleTrigger type, inherits from Trigger, includes all functionality of Trigger, and creates a use case for onSuccess using the CodeBlock object.

    :param session: The session this object belongs to, same as MatchObject
    :param patterns: Matching patterns, same as MatchObject
    :param code: str, code to execute when matching succeeds, implemented using CodeBlock
    """

    def __init__(self, session, patterns, code, *args, **kwargs):
        self._code = code
        self._codeblock = CodeBlock(code)
        super().__init__(session, patterns, *args, **kwargs)

    def onSuccess(self, id, line, wildcards):
        "Overrides the default onSuccess method of the base class, executes the code parameter passed in the constructor using CodeBlock"

        raw = self.session.getVariable("%raw")
        self._codeblock.execute(
            self.session, id=id, line=line, raw=raw, wildcards=wildcards
        )

    def __detailed__(self) -> str:
        group = f'group = "{self.group}" ' if self.group else ""
        return f'<{self.__class__.__name__}> id = "{self.id}" {group}enabled = {self.enabled} patterns = "{self.patterns}" code = "{self._code}"'

    def __repr__(self) -> str:
        return self.__detailed__()


class Command(MatchObject):
    """
    Command type, inherits from MatchObject.
    Commands are PyMUD's biggest feature, they are integrated objects that incorporate sync/async execution, response waiting, and processing.
    To use commands, you cannot directly use the Command type, but should always inherit and use its subclasses, and must override the base class's execute method.

    For help on using Command, please see the help page

    :param session: The session this object belongs to
    :param patterns: Matching patterns
    """

    __abbr__ = "cmd"

    def __init__(self, session, patterns, *args, **kwargs):
        super().__init__(session, patterns, sync=False, *args, **kwargs)
        self._tasks = set()

    def __unload__(self):
        """
        Automatically called when removing tasks from the session.
        Can clear various subclass objects managed by the command here.
        This function needs to be overridden in subclasses.
        """
        pass

    def unload(self):
        """
        Same as the __unload__ method, subclasses only need to override one method
        """
        pass

    def create_task(self, coro, *args, name=None):
        """
        Create and manage tasks. Tasks created by Command are also managed by Session.
        Internally, it calls asyncio.create_task to create tasks.

        :param coro: Coroutine or awaitable object contained in the task
        :param name: Task name, parameter supported only in Python 3.10
        """
        task = self.session.create_task(coro, *args, name)
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)
        return task

    def remove_task(self, task: asyncio.Task, msg=None):
        """
        Cancel tasks and remove them from the task management list. Tasks cancelled and removed by Command are also cancelled and removed by Session.

        :param task: The task to cancel
        :param msg: Message provided when cancelling the task, parameter supported only in Python 3.10
        """

        result = self.session.remove_task(task, msg)
        self._tasks.discard(task)
        # if task in self._tasks:
        #     self._tasks.remove(task)
        return result

    def reset(self):
        """
        Reset command, cancel and clear all tasks managed by this object.
        """

        super().reset()

        for task in list(self._tasks):
            if isinstance(task, asyncio.Task) and (not task.done()):
                self.remove_task(task)

    async def execute(self, cmd, *args, **kwargs):
        """
        Entry function for command calls. This function is automatically called by Session.
        Commands called through the ``Session.exec`` series of methods ultimately execute this method of the command.

        Subclasses must implement and override this method.
        """
        self.reset()
        return


class SimpleCommand(Command):
    """
    A command type that provides basic encapsulation for basic applications of commands, inherits from Command.

    SimpleCommand should not be understood as a "simple" command, as its use is not simple.
    Only after becoming proficient in using Command to establish your own command subclasses, can you simplify code using the SimpleCommand type for certain scenarios.

    :param session: The session this object belongs to
    :param patterns: Matching patterns
    :param succ_tri: Response trigger list representing success, can be a single trigger or a group of triggers, must be specified

    Special support for kwargs keyword parameters:
        :fail_tri: Response trigger list representing failure, can be a single trigger or a group of triggers, can be None
        :retry_tri: Response trigger list representing retry, can be a single trigger or a group of triggers, can be None
    """

    MAX_RETRY = 20

    def __init__(self, session, patterns, succ_tri, *args, **kwargs):
        super().__init__(session, patterns, succ_tri, *args, **kwargs)
        self._succ_tris = list()
        self._fail_tris = list()
        self._retry_tris = list()
        self._executed_cmd = ""

        if isinstance(succ_tri, Iterable):
            self._succ_tris.extend(succ_tri)
        else:
            if isinstance(succ_tri, Trigger):
                self._succ_tris.append(succ_tri)

        fail_tri = kwargs.get("fail_tri", None)
        if fail_tri:
            if isinstance(fail_tri, Iterable):
                self._fail_tris.extend(fail_tri)
            else:
                if isinstance(fail_tri, Trigger):
                    self._fail_tris.append(fail_tri)

        retry_tri = kwargs.get("retry_tri", None)
        if retry_tri:
            if isinstance(retry_tri, Iterable):
                self._retry_tris.extend(retry_tri)
            else:
                if isinstance(retry_tri, Trigger):
                    self._retry_tris.append(retry_tri)

    async def execute(self, cmd, *args, **kwargs):
        """
        Overrides the execute method of the base class, SimpleCommand's default implementation.

        :param cmd: The actual command entered during execution

        kwargs accepts the following parameters, used once during execution:
            :onSuccess: Callback for success
            :onFailure: Callback for failure
            :onTimeout: Callback for timeout
        """
        self.reset()
        # 0. check command
        cmd = cmd or self.patterns
        # 1. save the command, to use later.
        self._executed_cmd = cmd
        # 2. writer command
        retry_times = 0
        while True:
            # 1. create awaitables
            tasklist = list()
            for tr in self._succ_tris:
                tr.reset()
                tasklist.append(self.session.create_task(tr.triggered()))
            for tr in self._fail_tris:
                tr.reset()
                tasklist.append(self.session.create_task(tr.triggered()))
            for tr in self._retry_tris:
                tr.reset()
                tasklist.append(self.session.create_task(tr.triggered()))

            await asyncio.sleep(0.1)
            self.session.writeline(cmd)

            done, pending = await asyncio.wait(
                tasklist, timeout=self.timeout, return_when="FIRST_COMPLETED"
            )

            tasks_done = list(done)

            tasks_pending = list(pending)
            for t in tasks_pending:
                t.cancel()

            result = self.NOTSET
            if len(tasks_done) > 0:
                task = tasks_done[0]
                _, name, line, wildcards = task.result()
                # success
                if name in (tri.id for tri in self._succ_tris):
                    result = self.SUCCESS
                    break

                elif name in (tri.id for tri in self._fail_tris):
                    result = self.FAILURE
                    break

                elif name in (tri.id for tri in self._retry_tris):
                    retry_times += 1
                    if retry_times > self.MAX_RETRY:
                        result = self.FAILURE
                        break

                    await asyncio.sleep(2)

            else:
                result = self.TIMEOUT
                break

        if result == self.SUCCESS:
            self._onSuccess(name=self.id, cmd=cmd, line=line, wildcards=wildcards)
            _outer_onSuccess = kwargs.get("onSuccess", None)
            if callable(_outer_onSuccess):
                _outer_onSuccess(name=self.id, cmd=cmd, line=line, wildcards=wildcards)

        elif result == self.FAILURE:
            self._onFailure(name=self.id, cmd=cmd, line=line, wildcards=wildcards)
            _outer_onFailure = kwargs.get("onFailure", None)
            if callable(_outer_onFailure):
                _outer_onFailure(name=self.id, cmd=cmd, line=line, wildcards=wildcards)

        elif result == self.TIMEOUT:
            self._onTimeout(name=self.id, cmd=cmd, timeout=self.timeout)
            _outer_onTimeout = kwargs.get("onTimeout", None)
            if callable(_outer_onTimeout):
                _outer_onTimeout(name=self.id, cmd=cmd, timeout=self.timeout)

        return result


class Timer(BaseObject):
    """
    Timer type, inherits from MatchObject. PyMUD supports any number of timers simultaneously.

    :param session: The session this object belongs to

    The kwargs used in Timer are all inherited from BaseObject, including:
        - id: Identifier
        - group: Group name
        - enabled: Enabled status
        - timeout: Timer duration
        - onSuccess: Function to execute when timer expires
    """

    __abbr__ = "ti"

    def __init__(self, session, *args, **kwargs):
        self._task = None
        self._halt = False
        super().__init__(session, *args, **kwargs)

    def __del__(self):
        self.reset()

    def startTimer(self):
        "Start the timer"
        if not isinstance(self._task, asyncio.Task):
            self._halt = False
            self._task = asyncio.create_task(self.onTimerTask())

        asyncio.ensure_future(self._task)

    async def onTimerTask(self):
        "Timer task call method, no need to call in scripts"

        while self._enabled:
            await asyncio.sleep(self.timeout)

            if callable(self._onSuccess):
                self._onSuccess(self.id)

            if self.oneShot or self._halt:
                break

    def reset(self):
        "Reset timer, clear created timer tasks"
        try:
            self._halt = True
            if isinstance(self._task, asyncio.Task) and (not self._task.done()):
                self._task.cancel()

            self._task = None
        except asyncio.CancelledError:
            pass

    @property
    def enabled(self):
        "Read-write property, timer enabled status"
        return self._enabled

    @enabled.setter
    def enabled(self, en: bool):
        self._enabled = en
        if not en:
            self.reset()
        else:
            self.startTimer()

    def __detailed__(self) -> str:
        group = f'group = "{self.group}" ' if self.group else ""
        return f'<{self.__class__.__name__}> id = "{self.id}" {group}enabled = {self.enabled} timeout = {self.timeout}'

    def __repr__(self) -> str:
        return self.__detailed__()


class SimpleTimer(Timer):
    """
    SimpleTimer type, inherits from Timer, includes all functionality of Timer, and creates a use case for onSuccess using the CodeBlock object.

    :param session: The session this object belongs to, same as MatchObject
    :param code: str, code to execute when the timer task expires, implemented using CodeBlock
    """

    def __init__(self, session, code, *args, **kwargs):
        self._code = code
        self._codeblock = CodeBlock(code)
        super().__init__(session, *args, **kwargs)

    def onSuccess(self, id):
        "Overrides the default onSuccess method of the base class, executes the code parameter passed in the constructor using CodeBlock"
        self._codeblock.execute(self.session, id=id)

    def __detailed__(self) -> str:
        group = f'group = "{self.group}" ' if self.group else ""
        return f'<{self.__class__.__name__}> id = "{self.id}" {group}enabled = {self.enabled} timeout = {self.timeout} code = "{self._code}"'
