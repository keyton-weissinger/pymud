"""Session variables module - handles variables and globals"""


class SessionVariables:
    """Session variables module - handles variables and globals"""

    @property
    def vars(self):
        """
        本会话内变量的辅助点访问器，可以通过vars+变量名快速访问该变量值

        .. code:: Python

            # 以下两个获取变量值的方法等价
            exp = session.vars.exp
            exp = session.getVariable('exp')

            # 以下两个为变量赋值的方法等价
            session.vars.exp = 10000
            session.setVariable('exp', 10000)
        """
        return self._variables

    @property
    def globals(self):
        """
        全局变量的辅助点访问器，可以通过globals+变量名快速访问该变量值

        全局变量与会话变量的区别在于，全局变量在所有会话之间是共享和统一的

        .. code:: Python

            # 以下两个获取全局变量值的方法等价
            hooked = session.globals.hooked
            hooked = session.getGlobal('hooked')

            # 以下两个为全局变量赋值的方法等价
            session.globals.hooked = True
            session.setGlobal('hooked', True)
        """
        return self.application.globals

    # Variables management
    def delVariable(self, name):
        """
        删除一个变量。删除变量是从session管理的变量列表中移除关键字，而不是设置为 None

        :param name: 变量名
        """
        assert isinstance(name, str), "name必须是一个字符串"
        if name in self._variables.keys():
            self._variables.pop(name)

    def setVariable(self, name, value):
        """
        设置一个变量的值。可以使用vars快捷点访问器实现同样效果。

        :param name: 变量名。变量名必须为一个字符串
        :param value: 变量的值。变量值可以为任意 Python 类型。但为了要保存变量数据到硬盘，建议使用可序列化类型。
        """
        assert isinstance(name, str), "name必须是一个字符串"
        self._variables[name] = value

    def getVariable(self, name, default=None):
        """
        获取一个变量的值。可以使用vars快捷点访问器实现类似效果，但vars访问时，默认值总为None。

        :param name: 变量名。变量名必须为一个字符串
        :param default: 当会话中不存在该变量时，返回的值。默认为 None。
        :return: 变量的值，或者 default
        """
        assert isinstance(name, str), "name必须是一个字符串"
        return self._variables.get(name, default)

    def setVariables(self, names, values):
        """
        同时设置一组变量的值。要注意，变量名称和值的数量要相同。当不相同时，抛出异常。

        :param names: 所有变量名的元组或列表
        :param values: 所有变量对应值的元祖或列表
        """
        assert isinstance(names, tuple) or isinstance(names, list), (
            "names命名应为元组或列表，不接受其他类型"
        )
        assert isinstance(values, tuple) or isinstance(values, list), (
            "values值应为元组或列表，不接受其他类型"
        )
        assert (len(names) > 0) and (len(values) > 0) and (len(names) == len(values)), (
            "names与values应不为空，且长度相等"
        )
        for index in range(0, len(names)):
            name = names[index]
            value = values[index]
            self.setVariable(name, value)

    def getVariables(self, names):
        """
        同时获取一组变量的值。

        :param names: 所有变量名的元组或列表
        :return: 返回所有变量值的元组。可在获取值时直接解包。
        """
        assert isinstance(names, tuple) or isinstance(names, list), (
            "names命名应为元组或列表，不接受其他类型"
        )
        assert len(names) > 0, "names应不为空"
        values = list()
        for name in names:
            value = self.getVariable(name)
            values.append(value)

        return tuple(values)

    def updateVariables(self, kvdict: dict):
        """
        使用字典更新一组变量的值。若变量不存在将自动添加。

        :param kvdict: 变量/值的字典
        """
        self._variables.update(kvdict)

    # Global variables management
    def delGlobal(self, name):
        """
        删除一个全局变量，使用方式与会话变量variable相同

        :param name: 全局变量的名称
        """
        assert isinstance(name, str), "name必须是一个字符串"
        self.application.del_globals(name)

    def setGlobal(self, name, value):
        """
        设置一个全局变量的值，使用方式与会话变量variable相同

        :param name: 全局变量的名称
        :param value: 全局变量的值
        """
        assert isinstance(name, str), "name必须是一个字符串"
        self.application.set_globals(name, value)

    def getGlobal(self, name, default=None):
        """
        获取一个全局变量的值，使用方式与会话变量variable相同

        :param name: 全局变量的名称
        :param default: 当全局变量不存在时的返回值
        :return: 全局变量的值，或者 default
        """
        assert isinstance(name, str), "name必须是一个字符串"
        return self.application.get_globals(name, default)
