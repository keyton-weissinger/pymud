# Example script: How to play PKUXKX in PyMud

import webbrowser

from pymud import Alias, SimpleAlias, SimpleCommand, SimpleTrigger, Timer, Trigger

# In PyMud, use #load {filename} to load the corresponding configuration as a script file for support. Multiple script loading is supported
# This example script provides code examples for all PyMud-supported variables (Variable), triggers (Trigger, including single-line and multi-line triggers), aliases (Alias), timers (Timer), and commands (Command, this example uses the SimpleCommand subclass)
# When using #load {filename} to load a configuration file, if there is a class type named Configuration, this type will be automatically created during the #load operation; if there is no Configuration class, the file will only be imported
# For example, to load the configuration specified in this file, use #load pymud.pkuxkx

# In PyMud, Trigger, Alias, Command are all subclasses of the matching object (MatchObject) and use the same processing logic
# Matching objects have patterns to match. After a matching object succeeds, the object's onSuccess method will be called
# Trigger and Alias only have success, meaning only the onSuccess method will be called. This method's parameters reference MushClient, passing name, line, wildcards three parameters with the same meaning as in MushClient


class Configuration:
    # Meaning under hpbrief long
    HP_KEYS = (
        "combat_exp",
        "potential",
        "max_neili",
        "neili",
        "max_jingli",
        "jingli",
        "max_qi",
        "eff_qi",
        "qi",
        "max_jing",
        "eff_jing",
        "jing",
        "vigour/qi",
        "vigour/yuan",
        "food",
        "water",
        "fighting",
        "busy",
    )

    # Class constructor, passing parameter session, which is the session itself
    def __init__(self, session) -> None:
        self.session = session
        self._triggers = {}
        self._commands = {}
        self._aliases = {}
        self._timers = {}

        self._initTriggers()
        self._initCommands()
        self._initAliases()
        self._initTimers()

    def _initTriggers(self):
        """
        Initialize triggers.
        This example creates 2 triggers, corresponding to automatically opening the browser to access the URL for fullme links, and triggers for the hpbrief command
        """
        # In the Trigger constructor, only session (session) and pattern (matching pattern) are given as positional parameters, all other parameters are implemented using named parameters
        # For detailed supported named parameters, refer to the constructors of BaseObject and MatchObject, here's a simple list
        # id         : Unique identifier, automatically generated if not specified
        # group      : Group name, empty if not specified
        # enabled    : Enabled status, default True
        # priority   : Priority, default 100, smaller is higher
        # oneShot    : Single match, default False
        # ignoreCase : Ignore case, default False
        # isRegExp   : Regular expression mode, default True
        # keepEval   : Continuous matching, default False
        # raw        : Raw matching mode, default False. In raw matching mode, ANSI colors under VT100 are not decoded, so colors can be matched; normal matching only matches text

        # 1. Trigger for fullme link, matching URL
        # When matching is successful, calls ontri_webpage
        self._triggers["tri_webpage"] = self.tri_webpage = Trigger(
            self.session,
            id="tri_webpage",
            patterns=r"^http://fullme.pkuxkx.net/robot.php.+$",
            group="sys",
            onSuccess=lambda id, line, wildcards: webbrowser.open(line),
        )
        # 2. Trigger for fullme link, because it requires multi-line matching (3 lines), the matching pattern is a tuple of 3 regular expression patterns (all list types can be identified), no need to specify multiline flag and linesToMatch quantity like in MushClient
        # When matching is successful, calls ontri_hpbrief
        # Special note: This hpbrief trigger matching requires set hpbrief long to support
        self._triggers["tri_hp"] = self.tri_hp = Trigger(
            self.session,
            id="tri_hpbrief",
            patterns=(
                r"^[> ]*#(\d+.?\d*[KM]?),(\d+),(\d+),(\d+),(\d+),(\d+)$",
                r"^[> ]*#(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)$",
                r"^[> ]*#(\d+),(\d+),(-?\d+),(-?\d+),(\d+),(\d+)$",
            ),
            group="sys",
            onSuccess=self.ontri_hpbrief,
        )

        # 3. Now simple Trigger is supported, for example
        self._triggers["tri_gem"] = SimpleTrigger(
            self.session, r"^[> ]*从.+身上.+[◎☆★].+", "pack gem", group="sys"
        )

        self.session.addTriggers(self._triggers)

    def _initCommands(self):
        """Initialize commands, this example creates 1 command, supporting the hpbrief command"""

        # Command is an asynchronously executed command, can be understood as a combination of Alias+Trigger+Timer. After issuing a command in MUD, there will be different states of success, failure, timeout, and in these three states, onSuccess, onFailure, onTimeout methods will be called respectively
        # Here's an example of Command application: Let's say movement (s/e/n/w, etc.) is implemented as a Command.
        # 1. When moving in a certain direction, if successful, you will move to the next room;
        # 2. If unsuccessful, there will be descriptions like "There is no exit in this direction";
        # 3. When the character is in an unconscious state, movement commands will not have any response, and after exceeding the set timeout, onTimeout will be called
        # In the above implementation, when executing commands, we can clearly determine what to do next based on the command execution results
        # This example uses SimpleCommand, which adds the following parameters based on MatchObject:
        # 1. succ_tri: Trigger when the command executes successfully, cannot be empty
        # 2. fail_tri: Trigger when the command fails, can be empty
        # 3. retry_tri: Trigger when the command needs to be retried, can be empty (still using movement as an example, when moving in a certain direction, if "You are busy now" appears, you can try the command again after waiting 2s, until reaching the maximum number of attempts

        # Commands can be called synchronously, or can be called asynchronously using await syntax in asynchronous functions (async)
        # For example, the hpbrief below can be used like this:
        # self.session.exec_command("hpbrief")
        # self.session.exec_command_after(2, "hpbrief")
        # await self.cmd_hpbrief.execute("hpbrief")

        # Asynchronous implementation means that the process can be implemented in a loop rather than a callback, which is good for code readability
        # Assuming a Command cmd_move has been implemented, now to go from ct to execute "s;s;w" walking instructions to reach Chunlai Teahouse, then determine whether to drink based on the current hpbrief results, then walk back to the central square, you can implement it in the function like this:
        # async def gotodrink(self):
        #     for step in "s;s;w".split(";"):
        #         await self.cmd_move.execute(step)
        #         await self.cmd_hpbrief.execute("hpbrief")
        #     await asyncio.sleep(1)
        #     water = self.session.getVariable("water")
        #     if int(water) < 300:
        #         self.session.writeline("drink")
        #     await asyncio.sleep(1)
        #     for step in "e;n;n".split(";"):
        #         await self.cmd_move.execute(step)

        self._commands["cmd_hpbrief"] = self.cmd_hpbrief = SimpleCommand(
            self.session,
            id="cmd_hpbrief",
            patterns="^hpbrief$",
            succ_tri=self.tri_hp,
            group="status",
            onSuccess=self.oncmd_hpbrief,
        )
        self.session.addCommands(self._commands)

    def _initAliases(self):
        """Initialize aliases, this example creates 1 alias, which is get xxx from corpse"""

        # get xxx from corpse alias operation, when matching is successful, the getfromcorpse function will be automatically called
        # For example, gp silver is equivalent to get silver from corpse
        self._aliases["ali_get"] = Alias(
            self.session, r"^gp\s(.+)$", id="ali_get", onSuccess=self.getfromcorpse
        )

        # 3. Now simple Alias is supported, it can also support #wait (abbreviated as #wa) waiting, of course, Trigger also supports
        # Walking from Yangzhou Central Square to West Gate, inserting a 100ms wait between each step
        self._aliases["ali_yz_xm"] = SimpleAlias(
            self.session, "^yz_xm$", "w;#wa 100;w;#wa 100;w;#wa 100;w", group="sys"
        )

        self.session.addAliases(self._aliases)

    def _initTimers(self):
        """Initialize timers, this example creates 1 timer, printing information every 2 seconds"""

        self._timers["tm_test"] = self.tm_test = Timer(
            self.session, timeout=2, id="tm_test", onSuccess=self.onTimer
        )
        self.session.addTimers(self._timers)

    def getfromcorpse(self, name, line, wildcards):
        cmd = f"get {wildcards[0]} from corpse"
        self.session.writeline(cmd)

    def onTimer(self, name, *args, **kwargs):
        self.session.info(
            "This information will be printed every 2 seconds", "Timer Test"
        )

    def ontri_hpbrief(self, name, line, wildcards):
        self.session.setVariables(self.HP_KEYS, wildcards)

    def oncmd_hpbrief(self, name, cmd, line, wildcards):
        # To save server resources, you should use hpbrief instead of the hp command
        # But the hpbrief command data looks too complicated, so format the hpbrief number string output to look like hp
        # ┌───Personal Status────────────────────┬─────────────────────────────┐
        # │【Spirit】 1502    / 1502     [100%]    │【Energy】 4002    / 4002    (+   0)    │
        # │【Health】 2500    / 2500     [100%]    │【Inner Force】 5324    / 5458    (+   0)    │
        # │【Qi】 0       / 0        [  0%]    │【Meditation】 101%               [Normal]    │
        # │【Food】 222     / 400      [Hungry]    │【Potential】 36,955                       │
        # │【Water】 247     / 400      [Thirsty]    │【Experience】 2,341,005                    │
        # ├─────────────────────────────┴─────────────────────────────┤
        # │【Status】 Healthy, Angry                                                             │
        # └────────────────────────────────────────────PKUXKX────────┘
        var1 = self.session.getVariables(
            ("jing", "effjing", "maxjing", "jingli", "maxjingli")
        )
        line1 = "【Spirit】 {0:<8} [{5:3.0f}%] / {1:<8} [{2:3.0f}%]  |【Energy】 {3:<8} / {4:<8} [{6:3.0f}%]".format(
            var1[0],
            var1[1],
            100 * float(var1[1]) / float(var1[2]),
            var1[3],
            var1[4],
            100 * float(var1[0]) / float(var1[2]),
            100 * float(var1[3]) / float(var1[4]),
        )
        var2 = self.session.getVariables(("qi", "effqi", "maxqi", "neili", "maxneili"))
        line2 = "【Health】 {0:<8} [{5:3.0f}%] / {1:<8} [{2:3.0f}%]  |【Inner Force】 {3:<8} / {4:<8} [{6:3.0f}%]".format(
            var2[0],
            var2[1],
            100 * float(var2[1]) / float(var2[2]),
            var2[3],
            var2[4],
            100 * float(var2[0]) / float(var2[2]),
            100 * float(var2[3]) / float(var2[4]),
        )
        var3 = self.session.getVariables(
            ("food", "water", "exp", "pot", "fighting", "busy")
        )
        line3 = "【Food】 {0:<4} 【Water】{1:<4} 【Experience】{2:<9} 【Potential】{3:<10}【{4}】【{5}】".format(
            var3[0],
            var3[1],
            var3[2],
            var3[3],
            "Not Fighting" if var3[4] == "0" else "Fighting",
            "Not Busy" if var3[5] == "0" else "Busy",
        )
        self.session.info(line1, "Status")
        self.session.info(line2, "Status")
        self.session.info(line3, "Status")
