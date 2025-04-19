"""Session display module - handles formatting and displaying text"""

import datetime
from collections.abc import Iterable

from wcwidth import wcswidth

from ..settings import Settings


class SessionDisplay:
    """Session display module - handles formatting and displaying text"""

    def getMaxLength(self, iter: Iterable):
        """Get the maximum display width of strings in an iterable"""
        return wcswidth(sorted(iter, key=lambda s: wcswidth(s), reverse=True)[0])

    def splitByPrintableWidth(self, str, printable_length):
        """Split a string into chunks based on display width"""
        strlist = []
        startindex = 0
        remain = False
        split_str = ""
        for idx in range(1, len(str)):
            remain = True
            split_str = str[startindex:idx]
            if wcswidth(split_str) >= printable_length:
                strlist.append(split_str)
                startindex = idx
                remain = False

        if remain:
            strlist.append(str[startindex:])

        return strlist

    def buildDisplayLines(self, vars: dict, title: str):
        """Build formatted lines for displaying variables"""
        MIN_MARGIN = 4
        KEY_WIDTH = (self.getMaxLength(vars.keys()) // 4) * 4 + 4
        VALUE_WIDTH = 20
        VAR_WIDTH = KEY_WIDTH + 3 + VALUE_WIDTH
        display_lines = []
        vars_simple = {}
        vars_complex = {}

        for k, v in vars.items():
            if k in ("%line", "%raw", "%copy"):
                continue

            import dataclasses

            if dataclasses.is_dataclass(v) or (
                isinstance(v, Iterable) and not isinstance(v, str)
            ):
                vars_complex[k] = v
            else:
                vars_simple[k] = v

        totalWidth = self.application.get_width() - 2

        # draw title
        left_margin = (totalWidth - len(title)) // 2
        right_margin = totalWidth - len(title) - left_margin
        title_line = "{}{}{}".format("=" * left_margin, title, "=" * right_margin)
        display_lines.append(title_line)

        # draw simple vars
        vars_per_line = totalWidth // VAR_WIDTH
        left_margin = (totalWidth - vars_per_line * VAR_WIDTH) // 2
        left_margin = min(MIN_MARGIN, left_margin)
        right_margin = totalWidth - vars_per_line * VAR_WIDTH - left_margin
        right_margin = min(left_margin, right_margin)

        line = " " * left_margin
        cursor = left_margin
        var_count = 0

        var_keys = sorted(vars_simple.keys())
        for key in var_keys:
            if len(key) < KEY_WIDTH:
                name = key.rjust(KEY_WIDTH)
            else:
                name = key.rjust(KEY_WIDTH + VAR_WIDTH)

            value_dis = vars_simple[key].__repr__()
            var_display = "{0} = {1}".format(name, value_dis)

            if (cursor + wcswidth(var_display) > totalWidth) or (
                var_count >= vars_per_line
            ):
                display_lines.append(line)

                line = " " * left_margin
                cursor = left_margin
                var_count = 0

            line += var_display
            cursor += wcswidth(var_display)
            var_count += 1

            # 下一处判定
            for x in range(vars_per_line, 0, -1):
                next_start = left_margin + (vars_per_line - x) * VAR_WIDTH
                if cursor < next_start:
                    line += " " * (next_start - cursor)
                    cursor = next_start

                    if (vars_per_line - x) > var_count:
                        var_count = vars_per_line - x
                    break

        if cursor > left_margin:
            display_lines.append(line)

        var_keys = sorted(vars_complex.keys())
        for key in var_keys:
            name = key.rjust(KEY_WIDTH)
            value_dis = vars_complex[key].__repr__()
            allow_len = totalWidth - left_margin - KEY_WIDTH - 3 - right_margin
            line = "{0}{1} = ".format(" " * left_margin, name.rjust(KEY_WIDTH))
            if wcswidth(value_dis) > allow_len:
                value = vars_complex[key]
                if isinstance(value, dict):
                    max_len = self.getMaxLength(value.keys())
                    line += "{"
                    display_lines.append(line)
                    line = " " * (left_margin + KEY_WIDTH + 4)
                    for k, v in value.items():
                        subvalue_dis = "{},".format(v.__repr__())
                        allow_len_subvalue = allow_len - max_len - 4
                        if wcswidth(subvalue_dis) > allow_len_subvalue:
                            subvalue_lines = self.splitByPrintableWidth(
                                subvalue_dis, allow_len_subvalue
                            )
                            line += "{0}: ".format(k.ljust(max_len))
                            for subline in subvalue_lines:
                                line += subline
                                display_lines.append(line)
                                line = " " * (left_margin + KEY_WIDTH + 4 + max_len + 2)

                            line = " " * (left_margin + KEY_WIDTH + 4)
                        else:
                            val_line = "{0}: {1}".format(k.ljust(max_len), subvalue_dis)
                            line += val_line
                            display_lines.append(line)
                            line = " " * (left_margin + KEY_WIDTH + 4)
                    line = line[:-1] + "}"
                    display_lines.append(line)
                elif isinstance(value, list):
                    line += "["
                    for v in value:
                        val_line = "{0},".format(v.__repr__())
                        line += val_line
                        display_lines.append(line)
                        line = " " * (left_margin + KEY_WIDTH + 4)
                    line = line[:-1] + "]"
                    display_lines.append(line)
                else:
                    value_lines = self.splitByPrintableWidth(value_dis, allow_len)
                    for val_line in value_lines:
                        line += val_line
                        display_lines.append(line)
                        line = " " * (left_margin + KEY_WIDTH + 3)
            else:
                line = "{0}{1} = {2}".format(
                    " " * left_margin,
                    key.rjust(KEY_WIDTH),
                    vars_complex[key].__repr__(),
                )
                display_lines.append(line)

        display_lines.append("=" * totalWidth)

        return display_lines

    def _print_all_help(self):
        """打印所有可用的help主题, 并根据终端尺寸进行排版"""
        import math

        width = self.application.get_width()

        cmds = ["session"]
        cmds.extend(self._commands_alias.keys())
        cmds.extend(self._sys_commands)
        cmds = list(set(cmds))
        cmds.sort()

        cmd_count = len(cmds)
        left = (width - 8) // 2
        right = width - 8 - left
        self.writetobuffer("#" * left + "  HELP  " + "#" * right, newline=True)
        cmd_per_line = (width - 2) // 20
        lines = math.ceil(cmd_count / cmd_per_line)
        left_space = (width - cmd_per_line * 20) // 2

        for idx in range(0, lines):
            start = idx * cmd_per_line
            end = (idx + 1) * cmd_per_line
            if end > cmd_count:
                end = cmd_count
            line_cmds = cmds[start:end]
            self.writetobuffer(" " * left_space)
            for cmd in line_cmds:
                if cmd in self._commands_alias.keys():
                    self.writetobuffer(f"\x1b[32m{cmd.upper():<20}\x1b[0m")
                else:
                    self.writetobuffer(f"{cmd.upper():<20}")

            self.writetobuffer("", newline=True)

        self.writetobuffer("#" * width, newline=True)

    def info(self, text, title=None):
        """
        显示一条提示信息
        """
        if not title:
            title = "INFO"
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")

        # Style the text with the INFO style from Settings
        self.rawoutput(
            f"{Settings.INFO_STYLE}[{time_str}][{title}] {text}{Settings.CLR_STYLE}\n"
        )

    def warning(self, text, title=None):
        """
        显示一条警告信息
        """
        if not title:
            title = "WARN"
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")

        # Style the text with the WARN style from Settings
        self.rawoutput(
            f"{Settings.WARN_STYLE}[{time_str}][{title}] {text}{Settings.CLR_STYLE}\n"
        )

    def error(self, text, title=None):
        """
        显示一条错误信息
        """
        if not title:
            title = "ERROR"
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")

        # Style the text with the ERROR style from Settings
        self.rawoutput(
            f"{Settings.ERROR_STYLE}[{time_str}][{title}] {text}{Settings.CLR_STYLE}\n"
        )

    def replace(self, new_text):
        """
        替换当前行内容
        """
        if not hasattr(self, "_curr_line"):
            return

        self._curr_line.text = new_text

    def getPlainText(self, text):
        """
        获取文本的纯文本内容，即去除其中的ANSI控制字符的文本
        """
        return self._stripper.sub("", text)

    def output(self, text):
        """
        输出文本到会话窗口
        """
        if hasattr(self, "buffer") and self.buffer:
            self.buffer.append(text)
        else:
            # If no buffer exists, use rawoutput
            self.rawoutput(text)

    def rawoutput(self, text):
        """
        直接输出原始文本到会话窗口，不经过任何处理
        """
        if hasattr(self, "application") and self.application and hasattr(self, "name"):
            self.application.output(text, self.name)

    def showAll(self, session_list=None):
        """
        显示所有会话窗口
        """
        if session_list is None and hasattr(self, "application"):
            self.application.setAllWindowsVisible()
        elif session_list is not None:
            for name in session_list:
                self.application.setWindowVisible(name)

    def hideAll(self, session_list=None):
        """
        隐藏所有会话窗口
        """
        if session_list is None and hasattr(self, "application"):
            self.application.setAllWindowsInvisible()
        elif session_list is not None:
            for name in session_list:
                self.application.setWindowInvisible(name)

    def showWindow(self):
        """
        显示当前会话窗口
        """
        if hasattr(self, "application") and hasattr(self, "name"):
            self.application.setWindowVisible(self.name)

    def hideWindow(self):
        """
        隐藏当前会话窗口
        """
        if hasattr(self, "application") and hasattr(self, "name"):
            self.application.setWindowInvisible(self.name)

    def clearBuffer(self):
        """
        清空当前会话的缓冲区
        """
        if hasattr(self, "buffer"):
            self.buffer.text = ""
