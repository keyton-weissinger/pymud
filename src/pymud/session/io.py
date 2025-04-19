"""Session IO module - handles input/output operations"""

import asyncio
import time

from ..settings import Settings


class SessionIO:
    """Session IO module - handles input/output operations"""

    def getPlainText(self, rawText: str, trim_newline=False) -> str:
        """
        将带有VT100或者MXP转义字符的字符串转换为正常字符串（删除所有转义）。 **脚本中无需调用。**

        :param rawText: 原始文本对象
        :param trim_newline: 返回值是否删除末尾的回车符和换行符

        :return: 经处理后的纯文本字符串
        """
        plainText = self.PLAIN_TEXT_REGX.sub("", rawText)
        if trim_newline:
            plainText = plainText.rstrip("\n").rstrip("\r")

        return plainText

    def writetobuffer(self, data, newline=False):
        """
        将数据写入到用于本地显示的缓冲中。 **脚本中无需调用。**

        :param data: 写入的数据, 应为 str 类型
        :param newline: 是否额外增加换行符
        """
        self.buffer.insert_text(data)
        self.log.log(data)

        if len(data) > 0 and (data[-1] == "\n"):
            self._line_count += 1

        if newline:
            self.buffer.insert_text(self.newline_cli)
            self._line_count += 1
            self.log.log(self.newline_cli)

    def clear_half(self):
        """
        清除半数缓冲。 **脚本中无需调用。**

        半数的数量由 Settings.client['buffer_lines'] 确定，默认为5000行。
        """
        if (
            (Settings.client["buffer_lines"] > 0)
            and (self._line_count >= 2 * Settings.client["buffer_lines"])
            and self.buffer.document.is_cursor_at_the_end
        ):
            self._line_count = self.buffer.clear_half()

    def feed_data(self, data) -> None:
        """
        由协议对象调用，将收到的远程数据加入会话缓冲。永远只会传递1个字节的数据，以bytes形式。 **脚本中无需调用。**

        :param data: 传入的数据， bytes 格式
        """
        self._line_buffer.extend(data)

        if (len(data) == 1) and (data[0] == ord("\n")):
            self.go_ahead()

    def feed_eof(self) -> None:
        """
        由协议对象调用，处理收到远程 eof 数据，即远程断开连接。 **脚本中无需调用。**
        """
        self._eof = True
        if self.connected:
            self._transport.write_eof()
        self.state = "DISCONNECTED"
        self.syslog.info(f"服务器断开连接! {self._protocol.__repr__}")

    def feed_gmcp(self, name, value) -> None:
        """
        由协议对象调用，处理收到远程 GMCP 数据。 **脚本中无需调用。**

        :param name: 收到的GMCP数据的 name
        :param value: 收到的GMCP数据的 value。 该数据值类型为 字符串形式执行过eval后的结果
        """
        nothandle = True
        if name in self._gmcp.keys():
            gmcp = self._gmcp[name]
            if hasattr(gmcp, "__call__"):
                gmcp(value)
                nothandle = False

        if nothandle:
            self.info(f"{name}: {value}", "GMCP")

    def feed_msdp(self, name, value) -> None:
        """
        由协议对象调用，处理收到远程 MSDP 数据。 **脚本中无需调用。**

        :param name: 收到的MSDP数据的 name
        :param value: 收到的MSDP数据的 value
        """
        pass

    def feed_mssp(self, name, value) -> None:
        """
        由协议对象调用，处理收到远程 MSSP 数据。 **脚本中无需调用。**

        :param name: 收到的MSSP数据的 name
        :param value: 收到的MSSP数据的 value
        """
        pass

    def go_ahead(self) -> None:
        """
        对当前接收缓冲内容进行处理并放到显示缓冲中。 **脚本中无需调用。**

        触发器的响应在该函数中进行处理。
        """
        raw_line = self._line_buffer.decode(
            self.encoding, Settings.server["encoding_errors"]
        )
        tri_line = self.getPlainText(raw_line, trim_newline=True)
        self._line_buffer.clear()

        # MXP SUPPORT
        # 目前只有回复功能支持，还没有对内容进行解析，待后续完善
        if Settings.server["MXP"]:
            if raw_line == "\x1b[1z<SUPPORT>\r\n":
                self.write(b"\x1b[1z<SUPPORTS>")
            else:
                self.warning("MXP支持尚未开发，请暂时不要打开MXP支持设置")

        # 全局变量%line
        self.setVariable("%line", tri_line)
        # 全局变量%raw
        self.setVariable("%raw", raw_line.rstrip("\n").rstrip("\r"))

        # 此处修改，为了处理#replace和#gag命令
        # 将显示行数据暂存到session的display_line中，可以由trigger改变显示内容
        self.display_line = raw_line

        if not self._ignore:
            # 修改实现，形成列表时即排除非使能状态触发器，加快响应速度
            all_tris = [
                tri
                for tri in self._triggers.values()
                if hasattr(tri, "enabled") and tri.enabled
            ]
            all_tris.sort(
                key=lambda tri: tri.priority if hasattr(tri, "priority") else 0
            )

            for tri in all_tris:
                if hasattr(tri, "raw") and tri.raw and hasattr(tri, "match"):
                    state = tri.match(raw_line, docallback=True)
                elif hasattr(tri, "match"):
                    state = tri.match(tri_line, docallback=True)
                else:
                    continue

                if hasattr(state, "result") and state.result == getattr(
                    tri, "SUCCESS", 1
                ):
                    if hasattr(tri, "oneShot") and tri.oneShot:
                        self._triggers.pop(tri.id)

                    if not hasattr(tri, "keepEval") or not tri.keepEval:
                        break

        # 将数据写入缓存添加到此处
        if len(self.display_line) > 0:
            self.clear_half()
            self.writetobuffer(self.display_line)

    def set_exception(self, exc: Exception):
        """
        由协议对象调用，处理异常。 **脚本中无需调用。**

        :param exc: 异常对象
        """
        self.error(f"连接过程中发生异常，异常信息为： {exc}")

    def write(self, data) -> None:
        """
        向服务器写入数据（RAW格式字节数组/字节串）。 **一般不应在脚本中直接调用。**

        :param data: 向传输中写入的数据, 应为 bytes, bytearray, memoryview 类型
        """
        if self._transport and not self._transport.is_closing():
            self._transport.write(data)

    def writeline(self, line: str) -> None:
        """
        向服务器中写入一行，用于向服务器写入不经别名或命令解析时的数据。将自动在行尾添加换行符。

        - 如果line中包含分隔符（由Settings.client.seperator指定，默认为半角分号;）的多个命令，将逐行依次写入。
        - 当 Settings.cleint["echo_input"] 为真时，向服务器写入的内容同时在本地缓冲中回显。

        :param line: 字符串行内容
        """
        if self.seperator in line:
            lines = line.split(self.seperator)
            for ln in lines:
                if Settings.client["echo_input"]:
                    self.writetobuffer(f"\x1b[32m{ln}\x1b[0m", True)
                else:
                    self.log.log(f"\x1b[32m{ln}\x1b[0m\n")

                cmd = ln + self.newline
                self.write(
                    cmd.encode(self.encoding, Settings.server["encoding_errors"])
                )

        else:
            if Settings.client["echo_input"]:
                self.writetobuffer(f"\x1b[32m{line}\x1b[0m", True)
            else:
                self.log.log(f"\x1b[32m{line}\x1b[0m\n")

            cmd = line + self.newline
            self.write(cmd.encode(self.encoding, Settings.server["encoding_errors"]))

        self._activetime = time.time()

    async def waitfor(self, line: str, awaitable, wait_time=0.05) -> None:
        """
        调用writline向服务器中写入一行后，等待到可等待对象再返回。

        :param line: 使用writeline写入的行
        :param awaitable: 等待的可等待对象
        :param wait_time: 写入行前等待的延时，单位为s。默认0.05
        """
        await asyncio.sleep(wait_time)
        self.writeline(line)
        return await awaitable

    def replace(self, newstr):
        """
        将当前行内容显示替换为newstr。该方法仅在用于触发器的同步处置中才能正确相应

        :param newstr: 替换后的内容
        """
        if len(newstr) > 0:
            newstr += Settings.client["newline"]
        self.display_line = newstr
