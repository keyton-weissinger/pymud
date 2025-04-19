"""Session objects module - handles game objects like triggers, aliases, etc."""

from collections.abc import Iterable


class SessionObjects:
    """Session objects module - handles game objects like triggers, aliases, etc."""

    @property
    def tris(self):
        """
        本会话的触发器的辅助点访问器，可以通过tris+触发器id快速访问触发器

        .. code:: Python

            session.tris.mytri.enabled = False
        """
        return self._triggers

    @property
    def alis(self):
        """
        本会话的别名辅助点访问器，可以通过alis+别名id快速访问别名

        .. code:: Python

            session.alis.myali.enabled = False
        """
        return self._aliases

    @property
    def cmds(self):
        """
        本会话的命令辅助点访问器，可以通过cmds+命令id快速访问命令

        .. code:: Python

            session.cmds.mycmd.enabled = False
        """
        return self._commands

    @property
    def timers(self):
        """
        本会话的定时器辅助点访问器，可以通过timers+定时器id快速访问定时器

        .. code:: Python

            session.timers.mytimer.enabled = False
        """
        return self._timers

    @property
    def gmcp(self):
        """本会话的GMCP辅助访问器"""
        return self._gmcp

    def enableGroup(self, group: str, enabled=True):
        """
        使能或禁用Group中所有对象, 返回组内各对象个数。

        :param group: 组名，即各对象的 group 属性的值
        :param enabled: 使能/禁用开关。为True时表示使能， False为禁用
        :return: 5个整数的列表，依次表示改组内操作的 别名，触发器，命令，定时器，GMCP 的个数
        """
        counts = [0, 0, 0, 0, 0]
        for ali in self._aliases.values():
            if hasattr(ali, "group") and (ali.group == group):
                ali.enabled = enabled
                counts[0] += 1

        for tri in self._triggers.values():
            if hasattr(tri, "group") and (tri.group == group):
                tri.enabled = enabled
                counts[1] += 1

        for cmd in self._commands.values():
            if hasattr(cmd, "group") and (cmd.group == group):
                cmd.enabled = enabled
                counts[2] += 1

        for tmr in self._timers.values():
            if hasattr(tmr, "group") and (tmr.group == group):
                tmr.enabled = enabled
                counts[3] += 1

        for gmcp in self._gmcp.values():
            if hasattr(gmcp, "group") and (gmcp.group == group):
                gmcp.enabled = enabled
                counts[4] += 1

        return counts

    def _addObjects(self, objs):
        if isinstance(objs, list) or isinstance(objs, tuple):
            for item in objs:
                self._addObject(item)

        elif isinstance(objs, dict):
            for key, item in objs.items():
                if hasattr(item, "id"):
                    if key != item.id:
                        self.warning(
                            f"对象 {item} 字典键值 {key} 与其id {item.id} 不一致，将丢弃键值，以其id添加到会话中..."
                        )

                    self._addObject(item)

    def _addObject(self, obj):
        # Determine object type and add to the appropriate dictionary
        if hasattr(obj, "id"):
            objtype = obj.__class__.__name__

            if "Alias" in objtype:
                self._aliases[obj.id] = obj
            elif "Command" in objtype:
                self._commands[obj.id] = obj
            elif "GMCPTrigger" in objtype:
                self._gmcp[obj.id] = obj
            elif "Trigger" in objtype:
                self._triggers[obj.id] = obj
            elif "Timer" in objtype:
                self._timers[obj.id] = obj

    def addObject(self, obj):
        """
        向会话中增加单个对象，可直接添加 Alias, Trigger, GMCPTrigger, Command, Timer 或它们的子类

        :param obj: 特定对象本身，可以为 Alias, Trigger, GMCPTrigger, Command, Timer 或其子类
        """
        self._addObject(obj)

    def addObjects(self, objs):
        """
        向会话中增加多个对象，可直接添加 Alias, Trigger, GMCPTrigger, Command, Timer 或它们的子类的元组、列表或者字典(保持兼容性)

        :param objs: 多个特定对象组成的元组、列表或者字典，可以为 Alias, Trigger, GMCPTrigger, Command, Timer 或其子类
        """
        self._addObjects(objs)

    def _delObject(self, obj_id, obj_type):
        """Internal helper to delete objects by ID and type"""
        if obj_type == "Alias":
            self._aliases.pop(obj_id, None)
        elif obj_type == "Command":
            cmd = self._commands.pop(obj_id, None)
            if cmd and hasattr(cmd, "reset"):
                cmd.reset()
                if hasattr(cmd, "unload"):
                    cmd.unload()
                if hasattr(cmd, "__unload__"):
                    cmd.__unload__()
        elif obj_type == "Trigger":
            self._triggers.pop(obj_id, None)
        elif obj_type == "Timer":
            timer = self._timers.pop(obj_id, None)
            if timer and hasattr(timer, "enabled"):
                timer.enabled = False
        elif obj_type == "GMCPTrigger":
            self._gmcp.pop(obj_id, None)

    def delObject(self, obj):
        """
        从会话中移除一个对象，可直接删除 Alias, Trigger, GMCPTrigger, Command, Timer 或它们的子类本身

        :param obj: 要删除的多个特定对象组成的元组、列表或者字典，可以为 Alias, Trigger, GMCPTrigger, Command, Timer 或其子类
        """
        if isinstance(obj, (list, tuple, dict)):
            self.delObjects(obj)
            return

        # Try to determine the object type from its class name
        if hasattr(obj, "__class__") and hasattr(obj, "id"):
            objtype = obj.__class__.__name__

            if "Alias" in objtype:
                self._aliases.pop(obj.id, None)
            elif "Command" in objtype:
                if hasattr(obj, "reset"):
                    obj.reset()
                if hasattr(obj, "unload"):
                    obj.unload()
                if hasattr(obj, "__unload__"):
                    obj.__unload__()
                self._commands.pop(obj.id, None)
            elif "Trigger" in objtype:
                self._triggers.pop(obj.id, None)
            elif "Timer" in objtype:
                if hasattr(obj, "enabled"):
                    obj.enabled = False
                self._timers.pop(obj.id, None)
            elif "GMCPTrigger" in objtype:
                self._gmcp.pop(obj.id, None)
        # If the object is a string, try to find it in all collections
        elif isinstance(obj, str):
            if obj in self._aliases:
                self._aliases.pop(obj, None)
            elif obj in self._commands:
                cmd = self._commands.pop(obj, None)
                if cmd and hasattr(cmd, "reset"):
                    cmd.reset()
                    if hasattr(cmd, "unload"):
                        cmd.unload()
                    if hasattr(cmd, "__unload__"):
                        cmd.__unload__()
            elif obj in self._triggers:
                self._triggers.pop(obj, None)
            elif obj in self._timers:
                timer = self._timers.pop(obj, None)
                if timer and hasattr(timer, "enabled"):
                    timer.enabled = False
            elif obj in self._gmcp:
                self._gmcp.pop(obj, None)

    def delObjects(self, objs):
        """
        从会话中移除一组对象，可直接删除多个 Alias, Trigger, GMCPTrigger, Command, Timer

        :param objs: 要删除的一组对象的元组、列表或者字典(保持兼容性)，其中对象可以为 Alias, Trigger, GMCPTrigger, Command, Timer 或它们的子类
        """
        if isinstance(objs, list) or isinstance(objs, tuple):
            for item in objs:
                self.delObject(item)
        elif isinstance(objs, dict):
            for key, item in objs.items():
                self.delObject(item)
        else:
            self.delObject(objs)  # Just in case a single object was passed

    # Convenience methods for adding specific object types
    def addAliases(self, alis):
        """向会话中增加多个别名"""
        self._addObjects(alis)

    def addCommands(self, cmds):
        """向会话中增加多个命令"""
        self._addObjects(cmds)

    def addTriggers(self, tris):
        """向会话中增加多个触发器"""
        self._addObjects(tris)

    def addGMCPs(self, gmcps):
        """向会话中增加多个GMCPTrigger"""
        self._addObjects(gmcps)

    def addTimers(self, tis):
        """向会话中增加多个定时器"""
        self._addObjects(tis)

    def addAlias(self, ali):
        """向会话中增加一个别名"""
        self._addObject(ali)

    def addCommand(self, cmd):
        """向会话中增加一个命令"""
        self._addObject(cmd)

    def addTrigger(self, tri):
        """向会话中增加一个触发器"""
        self._addObject(tri)

    def addTimer(self, ti):
        """向会话中增加一个定时器"""
        self._addObject(ti)

    def addGMCP(self, gmcp):
        """向会话中增加一个GMCP触发器"""
        self._addObject(gmcp)

    # Convenience methods for deleting specific object types
    def delAlias(self, ali):
        """从会话中移除一个别名，可接受 Alias 对象或其 id"""
        if hasattr(ali, "id"):
            self._aliases.pop(ali.id, None)
        elif isinstance(ali, str) and (ali in self._aliases.keys()):
            self._aliases.pop(ali, None)

    def delAliases(self, ali_es: Iterable):
        """从会话中移除一组别名，可接受 Alias 对象或其 id 的迭代器"""
        for ali in ali_es:
            self.delAlias(ali)

    def delCommand(self, cmd):
        """从会话中移除一个命令，可接受 Command 对象或其 id"""
        if hasattr(cmd, "id"):
            if hasattr(cmd, "reset"):
                cmd.reset()
            self._commands.pop(cmd.id, None)
        elif isinstance(cmd, str) and (cmd in self._commands.keys()):
            if hasattr(self._commands[cmd], "reset"):
                self._commands[cmd].reset()
            self._commands.pop(cmd, None)

    def delCommands(self, cmd_s: Iterable):
        """从会话中移除一组命令，可接受可接受 Command 对象或其 id 的迭代器"""
        for cmd in cmd_s:
            self.delCommand(cmd)

    def delTrigger(self, tri):
        """从会话中移除一个触发器，可接受 Trigger 对象或其的id"""
        if hasattr(tri, "id"):
            self._triggers.pop(tri.id, None)
        elif isinstance(tri, str) and (tri in self._triggers.keys()):
            self._triggers.pop(tri, None)

    def delTriggers(self, tri_s: Iterable):
        """从会话中移除一组触发器，可接受可接受 Trigger 对象或其 id 的迭代器"""
        for tri in tri_s:
            self.delTrigger(tri)

    def delTimer(self, ti):
        """从会话中移除一个定时器，可接受 Timer 对象或其的id"""
        if hasattr(ti, "id"):
            if hasattr(ti, "enabled"):
                ti.enabled = False
            self._timers.pop(ti.id, None)
        elif isinstance(ti, str) and (ti in self._timers.keys()):
            if hasattr(self._timers[ti], "enabled"):
                self._timers[ti].enabled = False
            self._timers.pop(ti, None)

    def delTimers(self, ti_s: Iterable):
        """从会话中移除一组定时器，可接受可接受 Timer 对象或其 id 的迭代器"""
        for ti in ti_s:
            self.delTimer(ti)

    def delGMCP(self, gmcp):
        """从会话中移除一个GMCP触发器，可接受 GMCPTrigger 对象或其的id"""
        if hasattr(gmcp, "id"):
            self._gmcp.pop(gmcp.id, None)
        elif isinstance(gmcp, str) and (gmcp in self._gmcp.keys()):
            self._gmcp.pop(gmcp, None)

    def delGMCPs(self, gmcp_s: Iterable):
        """从会话中移除一组GMCP触发器，可接受可接受 GMCPTrigger 对象或其 id 的迭代器"""
        for gmcp in gmcp_s:
            self.delGMCP(gmcp)
