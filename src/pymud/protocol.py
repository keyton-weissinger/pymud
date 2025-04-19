import datetime
import logging
from asyncio import BaseTransport, Protocol

from .settings import Settings

IAC = b"\xff"  # TELNET command character IAC
DONT = b"\xfe"
DO = b"\xfd"
WONT = b"\xfc"
WILL = b"\xfb"
SE = b"\xf0"
NOP = b"\xf1"
DM = b"\xf2"
BRK = b"\xf3"
IP = b"\xf4"
AO = b"\xf5"
AYT = b"\xf6"
EC = b"\xf7"
EL = b"\xf8"
GA = b"\xf9"
SB = b"\xfa"

LOGOUT = b"\x12"
ECHO = b"\x01"

CHARSET = b"*"
REQUEST = 1
ACCEPTED = 2
REJECTED = 3
TTABLE_IS = 4
TTABLE_REJECTED = 5
TTABLE_ACK = 6
TTABLE_NAK = 7

# TELNET & MUD PROTOCOLS OPTIONS
# IAC DO TTYPE        x18      https://tintin.mudhalla.net/protocols/mtts/
# IAC DO NAWS            x1F   Negotiate About Window Size  https://www.rfc-editor.org/rfc/rfc1073.html
# IAC DO NEW_ENVIRON    b"'"     https://tintin.mudhalla.net/protocols/mnes/
# IAC WILL b'\xc9'        GMCP 201   https://tintin.mudhalla.net/protocols/gmcp/
# IAC WILL b'F'        MSSP 70         https://tintin.mudhalla.net/protocols/mssp/
# IAC WILL CHARSET        b"*"      https://www.rfc-editor.org/rfc/rfc2066.html
# IAC WILL b'Z'        90, MUD Sound Protocol, MSP   http://www.zuggsoft.com/zmud/msp.htm

LINEMODE = b'"'  # LINEMODE, rfc1184 https://www.rfc-editor.org/rfc/rfc1184.html
SGA = b"\x03"  # SUPPRESS GO AHEAD, rfc858 https://www.rfc-editor.org/rfc/rfc858.html

TTYPE = (
    b"\x18"  # MUD Terminal Type Standard, https://tintin.mudhalla.net/protocols/mtts/
)
NAWS = b"\x1f"  # Negotiate About Window Size, RFC1073, https://www.rfc-editor.org/rfc/rfc1073.html
MNES = b"'"  # MUD NEW-ENVIRON Standard, https://tintin.mudhalla.net/protocols/mnes/

# Generic Mud Communication Protocol, https://tintin.mudhalla.net/protocols/gmcp/
GMCP = b"\xc9"

# Mud Server Data Protocol, https://tintin.mudhalla.net/protocols/msdp/
MSDP = b"E"
MSDP_VAR = 1
MSDP_VAL = 2
MSDP_TABLE_OPEN = 3
MSDP_TABLE_CLOSE = 4
MSDP_ARRAY_OPEN = 5
MSDP_ARRAY_CLOSE = 6

# Mud Server Status Protocol, https://tintin.mudhalla.net/protocols/mssp/
MSSP = b"F"
MSSP_VAR = 1
MSSP_VAL = 2

# Mud Client Compression Protocol, V1V2V3 versions, see http://www.zuggsoft.com/zmud/mcp.htm, https://tintin.mudhalla.net/protocols/mccp/
# MCCP V1 uses option 85(U) as negotiation option, defined in 1998;
# In 2000, MCCP V2 was defined, using option 86(V) as negotiation option.
# After that, MCCP1 was abandoned in 2004 due to illegal sub-negotiation content. Currently, all MUD servers have switched to support V2 protocol.
# In 2019, V3 protocol was defined, but used as a new protocol, not yet supported.
MCCP1 = b"U"  # MUD Client Compression Protocol V1, deprecated
MCCP2 = b"V"  # MUD Client Compression Protocol V2, Mud Client Compression Protocol, https://tintin.mudhalla.net/protocols/mccp/
MCCP3 = b"W"  # MUD Client Compression Protocol V3, V2 version can also be found at http://www.zuggsoft.com/zmud/mcp.htm

# MUD Sound Protocol, http://www.zuggsoft.com/zmud/msp.htm
MSP = b"Z"

# MUD eXtension Protocol, http://www.zuggsoft.com/zmud/mxp.htm
MXP = b"["

_cmd_name_str = {
    IAC: "IAC",
    WILL: "WILL",
    WONT: "WONT",
    DO: "DO",
    DONT: "DONT",
    SB: "SB",
    SE: "SE",
}

_option_name_str = {
    LINEMODE: "LINEMODE",
    SGA: "SGA",
    ECHO: "ECHO",
    CHARSET: "CHARSET",
    TTYPE: "TTYPE",
    NAWS: "NAWS",
    MNES: "MNES",
    GMCP: "GMCP",
    MSDP: "MSDP",
    MSSP: "MSSP",
    MCCP2: "MCCP2",
    MCCP3: "MCCP3",
    MSP: "MSP",
    MXP: "MXP",
}


def name_command(cmd):
    if cmd in _cmd_name_str.keys():
        return _cmd_name_str[cmd]
    else:
        return cmd


def name_option(opt):
    if opt in _option_name_str.keys():
        return _option_name_str[opt]
    return opt


class MudClientProtocol(Protocol):
    """
    Asyncio protocol implementation for MUD clients
    Basic protocol: TELNET
    Extended protocols: GMCP, MCDP, MSP, MXP, etc.
    """

    def __init__(self, session, *args, **kwargs) -> None:
        """
        MUD client protocol implementation, parameters include:
          + session: session managing the protocol
        In addition, the following named parameters can be accepted:
          + onConnected: callback when connection is established, contains 2 parameters: MudClientProtocol itself and the generated Transport object
          + onDisconnected: callback when connection is disconnected, contains 1 parameter: MudClientProtocol itself
        """

        self.log = logging.getLogger("pymud.MudClientProtocol")
        self.session = session  # Data processing session
        self.connected = False  # Connection status flag
        self._iac_handlers = dict()  # Supported option negotiation handler functions
        self._iac_subneg_handlers = dict()  # Option sub-negotiation handler functions

        for k, v in _option_name_str.items():
            func = getattr(
                self, f"handle_{v.lower()}", None
            )  # Option negotiation handler function, handler functions use lowercase letters
            self._iac_handlers[k] = func
            subfunc = getattr(
                self, f"handle_{v.lower()}_sb", None
            )  # Sub-negotiation handler function
            self._iac_subneg_handlers[k] = subfunc

        self.encoding = Settings.server[
            "default_encoding"
        ]  # Basic byte string encoding
        self.encoding_errors = Settings.server[
            "encoding_errors"
        ]  # Error handling during encoding/decoding
        self.mnes = Settings.mnes

        self._extra = dict()  # Dictionary storing extra related information

        self.mssp = dict()  # Store server-related parameters from MSSP protocol
        self.msdp = dict()  # Store all server data from MSDP protocol
        self.gmcp = dict()  # Store all server data from GMCP protocol

        self._extra.update(kwargs=kwargs)

        self.on_connection_made = kwargs.get("onConnected", None)  # Connection callback
        self.on_connection_lost = kwargs.get(
            "onDisconnected", None
        )  # Disconnection callback

    def get_extra_info(self, name, default=None):
        """Get transport information or extra protocol information."""
        if self._transport:
            default = self._transport._extra.get(name, default)
        return self._extra.get(name, default)

    def connection_made(self, transport: BaseTransport) -> None:
        self._transport = transport  # Save transport
        self._when_connected = datetime.datetime.now()  # Connection establishment time
        self._last_received = datetime.datetime.now()  # Last received data time

        # self.session.set_transport(self._transport)                         # Assign transport to session

        # self.reader = self._reader_factory(loop = self.loop, encoding = self.encoding, encoding_errors = self.encoding_errors)
        # self.writer = self._writer_factory(self._transport, self, self.reader, self.loop)

        self._state_machine = "normal"  # State machine flag, normal,
        self._bytes_received_count = 0  # Total bytes received (including commands)
        self._bytes_count = 0  # Bytes received (excluding negotiation), i.e., bytes written to streamreader
        self.connected = True

        self.log.info(f"Connection established to: {self}.")

        # If onConnected callback function is set, call it
        if self.on_connection_made and callable(self.on_connection_made):
            self.on_connection_made(self._transport)

        # Set future
        # self._waiter_connected.set_result(True)

    def connection_lost(self, exc) -> None:
        if not self.connected:
            return

        self.connected = False

        if exc is None:
            self.log.info(f"Connection has been disconnected: {self}.")
            self.session.feed_eof()
        else:
            self.log.warning(
                f"Connection has been disconnected due to exception: {self}, {exc}."
            )
            self.session.set_exception(exc)

        self._transport.close()
        self._transport = None
        # self.session.set_transport(None)

        # If onDisconnected callback function is set, call it
        if self.on_connection_lost and callable(self.on_connection_lost):
            self.on_connection_lost(self)

        self._state_machine = "normal"  # Reset state machine flag to normal

    def eof_received(self):
        self.log.debug("Received EOF from server, connection closed.")
        self.connection_lost(None)

    def data_received(self, data: bytes) -> None:
        self._last_received = datetime.datetime.now()

        for byte in data:
            byte = bytes(
                [
                    byte,
                ]
            )
            self._bytes_received_count += 1

            # State machine is normal, next could receive command including IAC or normal characters
            if self._state_machine == "normal":
                if (
                    byte == IAC
                ):  # If IAC is received, switch state machine to wait for command
                    self._state_machine = "waitcommand"
                    self.session.go_ahead()
                else:  # Otherwise, received is normal data, pass to reader
                    self.session.feed_data(byte)

            # State machine is waiting for command, the next byte should only include: WILL/WONT/DO/DONT/SB
            elif self._state_machine == "waitcommand":
                if byte in (
                    WILL,
                    WONT,
                    DO,
                    DONT,
                ):  # At this point, the subsequent option is only 1 byte
                    self._iac_command = byte
                    self._state_machine = "waitoption"  # Next is option
                elif byte == SB:
                    self._iac_command = byte
                    self._iac_sub_neg_data = (
                        IAC + SB
                    )  # Save complete sub-negotiation command
                    self._state_machine = "waitsubnegotiation"  # Next is sub-negotiation, terminated with IAC SE
                elif (
                    byte == NOP
                ):  # No operation TODO: Confirm if NOP is just IAC NOP with nothing else
                    self.log.debug("Received NOP instruction from server: IAC NOP")
                    self._state_machine = "normal"
                    # Handle NOP and GA signals the same way
                    self.session.go_ahead()
                elif byte == GA:
                    self.log.debug("Received GA instruction from server: IAC GA")
                    self._state_machine = "normal"
                    # Handle NOP and GA signals the same way, send out the entire buffer
                    self.session.go_ahead()
                else:  # Error data, cannot handle, log error and restore state machine to normal
                    self.log.error(
                        f"Received unhandled illegal command during negotiation with server: {byte}"
                    )
                    self._state_machine = "normal"

            elif self._state_machine == "waitoption":  # Next can accept options
                if byte in _option_name_str.keys():
                    iac_handler = self._iac_handlers[
                        byte
                    ]  # Choose the corresponding handler function based on the option
                    if iac_handler and callable(iac_handler):
                        self.log.debug(
                            f"Received IAC option negotiation: IAC {name_command(self._iac_command)} {name_option(byte)}, and passed to handler function {iac_handler.__name__}"
                        )
                        iac_handler(self._iac_command)  # Execute IAC negotiation
                    else:
                        self.log.debug(
                            f"Received unsupported (no handler function defined) IAC negotiation: IAC {name_command(self._iac_command)} {name_option(byte)}, will use default handler (not accept)"
                        )
                        self._iac_default_handler(self._iac_command, byte)
                    self._state_machine = (
                        "normal"  # State machine returns to normal state
                    )
                else:
                    self.log.warning(
                        f"Received unrecognized (not in defined range) IAC negotiation: IAC {name_command(self._iac_command)} {name_option(byte)}, will use default handler (not accept)"
                    )
                    self._iac_default_handler(self._iac_command, byte)
                    self._state_machine = (
                        "normal"  # State machine returns to normal state
                    )

            elif self._state_machine == "waitsubnegotiation":  # When received IAC SB
                # At this point, the next byte should be an optional option, at least not IAC
                if byte != IAC:
                    self._iac_sub_neg_option = byte  # Save sub-negotiation option
                    self._iac_sub_neg_data += byte  # Save all sub-negotiation content
                    self._state_machine = (
                        "waitsbdata"  # Next state, wait for sub-negotiation data
                    )
                else:
                    self.log.error(
                        "Error received IAC in byte waiting for option code in sub-negotiation"
                    )
                    self._state_machine = (
                        "normal"  # Discard all previous states at this point
                    )

            elif self._state_machine == "waitsbdata":
                self._iac_sub_neg_data += byte  # Save all sub-negotiation content
                if byte == IAC:
                    # In sub-negotiation, if IAC is received, the next byte could be something else, or SE.
                    #   When the next byte is something else, IAC is a character in the sub-negotiation
                    #   When the next byte is SE, it indicates the end of the sub-negotiation command
                    # Based on the above reasons, the state machine transition rules under sub-negotiation are:
                    #   1. After receiving IAC in sub-negotiation, the state switches to waitse
                    #   2. After waitse, if SE is received, the sub-negotiation ends, return to normal
                    #   3. After waitse, if what is received is not SE, return to waitsubnegotiation state
                    self._state_machine = "waitse"
                else:
                    # During sub-negotiation, all non-IAC bytes received are the specific content of the sub-negotiation
                    pass

            elif self._state_machine == "waitse":
                self._iac_sub_neg_data += byte  # Save all sub-negotiation content
                if (
                    byte == SE
                ):  # IAC SE indicates the sub-negotiation has been completely received
                    self._state_machine = "normal"
                    if self._iac_sub_neg_option in _option_name_str.keys():
                        iac_subneg_handler = self._iac_subneg_handlers[
                            self._iac_sub_neg_option
                        ]  # Choose the corresponding handler function based on the option sub-negotiation
                        if iac_subneg_handler and callable(iac_subneg_handler):
                            self.log.debug(
                                f"Received {name_option(self._iac_sub_neg_option)} option sub-negotiation: {self._iac_sub_neg_data}, and passed to handler function {iac_subneg_handler.__name__}"
                            )
                            iac_subneg_handler(self._iac_sub_neg_data)
                        else:
                            self.log.debug(
                                f"Received unsupported (no handler function defined) {name_option(self._iac_sub_neg_option)} option sub-negotiation: {self._iac_sub_neg_data}, will discard data without processing."
                            )
                else:
                    self._state_machine = "waitsbdata"

    # public properties
    @property
    def duration(self):
        """Total time since client connection, in seconds, expressed as a float"""
        return (datetime.datetime.now() - self._when_connected).total_seconds()

    @property
    def idle(self):
        """Total time since receiving the last data from the server, in seconds, expressed as a float"""
        return (datetime.datetime.now() - self._last_received).total_seconds()

    # public protocol methods
    def __repr__(self):
        "Representation under %r"
        hostport = self.get_extra_info("peername", ["-", "closing"])[:2]
        return "<Peer {0} {1}>".format(*hostport)

    def _iac_default_handler(self, cmd, option):
        """
        Default IAC negotiation handler, directly replies not accepting for unrecognized options
        Replies DONT for WILL, WONT; replies WONT for DO, DONT
        """
        if cmd in (WILL, WONT):
            ack = DONT

        elif cmd in (DO, DONT):
            ack = WONT

        else:
            # Abnormal situation, this should be an impossible branch as ensured by previous function calls and handling. Retained for code integrity
            self.log.error(
                f"Option negotiation entered abnormal branch, reference data: , _iac_default_handler, {cmd}, {option}"
            )
            return

        self.session.write(IAC + ack + option)
        self.log.debug(
            f"Used default negotiation handler to reject the server's request of IAC {name_command(cmd)} {name_option(option)}, reply is IAC {name_command(ack)} {name_option(option)}"
        )

    # SGA done.
    def handle_sga(self, cmd):
        """
        SGA, suppress go ahead, suppresses GA signals. In a full-duplex environment, GA signals are not needed, so by default agree to suppress
        """
        if cmd == WILL:
            if Settings.server["SGA"]:
                self.session.write(IAC + DO + SGA)
                self.log.debug(
                    "Sent option negotiation, agree to suppress GA signal IAC DO SGA."
                )
            else:
                self.session.write(IAC + DONT + SGA)
                self.log.debug(
                    "Sent option negotiation, disagree to suppress GA signal IAC DONT SGA."
                )

        else:
            self.log.warning(
                f"Received unhandled SGA negotiation from server: IAC {name_command(cmd)} SGA"
            )

    # ECHO done.
    def handle_echo(self, cmd):
        """
        ECHO, echo. Default is disagree
        """
        if cmd == WILL:
            if Settings.server["ECHO"]:
                self.session.write(IAC + DO + ECHO)
                self.log.debug(
                    "Sent option negotiation, agree to ECHO option negotiation IAC DO ECHO."
                )
            else:
                self.session.write(IAC + DONT + ECHO)
                self.log.debug(
                    "Sent option negotiation, disagree to ECHO option negotiation IAC DONT ECHO."
                )

        else:
            self.log.warning(
                f"Received unhandled ECHO negotiation from server: IAC {name_command(cmd)} ECHO"
            )

    def handle_charset(self, cmd):
        """
        CHARSET, character set negotiation https://www.rfc-editor.org/rfc/rfc2066.html
        """
        nohandle = False
        if cmd == WILL:
            # 1. Reply agreeing to CHARSET negotiation
            self.session.write(IAC + DO + CHARSET)
            self.log.debug(
                "Sent option negotiation, agree to CHARSET negotiation IAC DO CHARSET. Waiting for sub-negotiation"
            )
        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled CHARSET negotiation from server: IAC {name_command(cmd)} TTYPE"
            )

    def handle_charset_sb(self, data: bytes):
        "Character set sub-negotiation"
        # b'\xff\xfa*\x01;UTF-8\xff\xf0'
        # IAC SB CHARSET \x01 ; UTF-8 IAC SE
        unhandle = True
        self.log.debug("charset sub-negotiation")
        if data[3] == REQUEST:
            charset_list = data[4:-2].decode(self.encoding).lower().split(";")
            # If server has UTF-8 option, default to choose UTF-8
            if "utf-8" in charset_list:
                sbneg = bytearray()
                sbneg.extend(IAC + SB + CHARSET)
                sbneg.append(ACCEPTED)
                sbneg.extend(b"UTF-8")
                sbneg.extend(IAC + SE)
                self.session.write(sbneg)
                self.log.debug(
                    'Sent CHARSET sub-negotiation, agree to UTF-8 encoding IAC SB ACCEPTED "UTF-8" IAC SE'
                )
                unhandle = False

        if unhandle:
            self.log.warning(f"Unhandled CHARSET sub-negotiation: {data}")

    def handle_ttype(self, cmd):
        """
        Handle MUD Terminal Type Standard protocol negotiation https://tintin.mudhalla.net/protocols/mtts/
        server - IAC DO TTYPE
        client - IAC WILL TTYPE
        Wait for sub-negotiation, sub-negotiation see handle_ttype_sb below
        """
        nohandle = False
        if cmd == WILL:
            nohandle = True
        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            # 1. Reply agreeing to MTTS negotiation
            self.session.write(IAC + WILL + TTYPE)
            self._mtts_index = 0
            self.log.debug(
                "Sent option negotiation, agree to MTTS(TTYPE) negotiation IAC WILL TTYPE. Waiting for sub-negotiation"
            )
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled TTYPE/MTTS negotiation from server: IAC {name_command(cmd)} TTYPE"
            )

    def handle_ttype_sb(self, data):
        """
        Handle TTYPE/MTTS sub-negotiation, detailed information see handle_ttype
        server - IAC   SB TTYPE SEND IAC SE
        client - IAC   SB TTYPE IS   "TINTIN++" IAC SE
        server - IAC   SB TTYPE SEND IAC SE
        client - IAC   SB TTYPE IS   "XTERM" IAC SE
        server - IAC   SB TTYPE SEND IAC SE
        client - IAC   SB TTYPE IS   "MTTS 137" IAC SE
        """
        IS, SEND = b"\x00", 1

        # Server sub-negotiation must be 6 bytes, content is IAC SB TTYPE SEND IAC SE
        # Since the IAC SB TTYPE and later IAC SE are fixed and written in the sub-negotiation data, they were checked previously, so we don't check here
        # Therefore, to check the server's sub-negotiation command, only check that the length is 6 and the 4th byte is SEND
        if (len(data) == 6) and (data[3] == SEND):
            if self._mtts_index == 0:
                # First received, reply with client's full name, all uppercase
                self.session.write(
                    IAC
                    + SB
                    + TTYPE
                    + IS
                    + Settings.__appname__.encode(self.encoding, self.encoding_errors)
                    + IAC
                    + SE
                )
                self._mtts_index += 1
                self.log.debug(
                    f'Reply to first MTTS sub-negotiation: IAC SB TTYPE IS "{Settings.__appname__}" IAC SE'
                )
            elif self._mtts_index == 1:
                # Second received, reply with client terminal type, here default set to XTERM (using system console), ANSI (code already supports), will be changed later when functionality is improved
                # VT100 https://tintin.mudhalla.net/info/vt100/
                # XTERM https://tintin.mudhalla.net/info/xterm/
                self.session.write(IAC + SB + TTYPE + IS + b"XTERM" + IAC + SE)
                self._mtts_index += 1
                self.log.debug(
                    'Reply to second MTTS sub-negotiation: IAC SB TTYPE IS "XTERM" IAC SE'
                )
            elif self._mtts_index == 2:
                # Third received, reply with client's supported standard features, here default set to 783 (supports ANSI, VT100, UTF-8, 256 COLORS, TRUECOLOR, MNES), will be changed later when functionality is improved
                # Modify terminal standard according to improved terminal emulation functionality
                #       1 "ANSI"              Client supports all common ANSI color codes.
                #       2 "VT100"             Client supports all common VT100 codes.
                #       4 "UTF-8"             Client is using UTF-8 character encoding.
                #       8 "256 COLORS"        Client supports all 256 color codes.
                #      16 "MOUSE TRACKING"    Client supports xterm mouse tracking.
                #      32 "OSC COLOR PALETTE" Client supports OSC and the OSC color palette.
                #      64 "SCREEN READER"     Client is using a screen reader.
                #     128 "PROXY"             Client is a proxy allowing different users to connect from the same IP address.
                #     256 "TRUECOLOR"         Client supports truecolor codes using semicolon notation.
                #     512 "MNES"              Client supports the Mud New Environment Standard for information exchange.
                #    1024 "MSLP"              Client supports the Mud Server Link Protocol for clickable link handling.
                #    2048 "SSL"               Client supports SSL for data encryption, preferably TLS 1.3 or higher.
                self.session.write(IAC + SB + TTYPE + IS + b"MTTS 783" + IAC + SE)
                self._mtts_index += 1
                self.log.debug(
                    'Reply to third MTTS sub-negotiation: IAC SB TTYPE IS "MTTS 783" IAC SE'
                )
            else:
                self.log.warning(
                    f"Received {self._mtts_index + 1}th (normally 3) MTTS sub-negotiation, will not respond"
                )
        else:
            self.log.warning(
                f"Received incorrect MTTS sub-negotiation: {data}, will not respond"
            )

    def handle_naws(self, cmd):
        """
        Handle screen size negotiation https://www.rfc-editor.org/rfc/rfc1073.html
        When the server sends a request to negotiate size, the logic is:
        (server sends)  IAC DO NAWS
        (client sends)  IAC WILL NAWS
        (client sends)  IAC SB NAWS 0(WIDTH1) 80(WIDTH0) 0(HEIGHT1) 24(HEIGHT0) IAC SE
        This client does not actively negotiate NAWS, only when the server negotiates NAWS is needed, then negotiation proceeds.
        The default size given for negotiation is: self._extra["naws_width"] and self._extra["naws_height"]
        """
        nohandle = False
        if cmd == WILL:
            nohandle = True
        elif cmd == WONT:
            nohandle = True
        elif (
            cmd == DO
        ):  # Under normal circumstances, only handles the server's IAC DO NAWS
            # 1. Reply agreeing to NAWS
            self.session.write(IAC + WILL + NAWS)
            self.log.debug(
                "Sent option negotiation, agree to NAWS negotiation IAC WILL NAWS."
            )
            # 2. Send sub-negotiation confirming size
            width_bytes = Settings.client["naws_width"].to_bytes(2, "big")
            height_bytes = Settings.client["naws_height"].to_bytes(2, "big")
            sb_cmd = IAC + SB + NAWS + width_bytes + height_bytes + IAC + SE
            self.session.write(sb_cmd)
            self.log.debug(
                "Sent NAWS option sub-negotiation, specifying window size. IAC SB NAWS (width = %d, height = %d) IAC SE"
                % (Settings.client["naws_width"], Settings.client["naws_height"])
            )
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled NAWS negotiation from server: IAC {name_command(cmd)} NAWS"
            )

    def handle_mnes(self, cmd):
        """
        Handle MUD New-Env Standard negotiation https://tintin.mudhalla.net/protocols/mnes/
        MNES as an extension of MTTS. MTTS is designed to only respond to specific client features, MNES can provide more extensions
        """
        nohandle = False
        if cmd == WILL:
            nohandle = True
        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            # 1. Reply agreeing to MNES
            self.session.write(IAC + WILL + MNES)
            self.log.debug(
                "Sent option negotiation, agree to MNES negotiation IAC WILL MNES. Waiting for server sub-negotiation"
            )
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled MNES negotiation from server: IAC {name_command(cmd)} MNES"
            )

    def handle_mnes_sb(self, data: bytes):
        """
        Handle MNES sub-negotiation https://tintin.mudhalla.net/protocols/mnes/

        """

        # server - IAC   SB MNES SEND VAR "CLIENT_NAME" SEND VAR "CLIENT_VERSION" IAC SE
        # client - IAC   SB MNES IS   VAR "CLIENT_NAME" VAL "TINTIN++" IAC SE
        # client - IAC   SB MNES IS   VAR "CLIENT_VERSION" VAL "2.01.7" IAC SE
        # server - IAC   SB MNES SEND VAR "CHARSET" IAC SE
        # client - IAC   SB MNES INFO VAR "CHARSET" VAL "ASCII" IAC SE
        def send_mnes_value(var: str, val: str):
            sbneg = bytearray()
            sbneg.extend(IAC + SB + MNES)
            sbneg.append(IS)
            sbneg.extend(var.encode(self.encoding))
            sbneg.append(VAL)
            sbneg.extend(val.encode(self.encoding))
            sbneg.extend(IAC + SE)
            self.session.write(sbneg)
            self.log.debug(f"Reply to MNES request: {var} = {val}")

        IS, SEND, INFO = 0, 1, 2
        VAR, VAL = 0, 1

        request_var = list()
        var_name = bytearray()
        state_machine = "wait_cmd"
        for idx in range(3, len(data) - 1):
            byte = data[idx]
            if state_machine == "wait_cmd":  # Next byte is command, should be SEND
                if byte == SEND:
                    state_machine = "wait_var"

            elif state_machine == "wait_var":
                if byte == VAR:
                    state_machine = "wait_var_content"
                    var_name.clear()

            elif state_machine == "wait_var_content":
                if byte not in (SEND, IAC):
                    var_name.append(byte)
                else:
                    if len(var_name) > 0:
                        request_var.append(var_name.decode(self.encoding))
                    state_machine = "wait_cmd"

        self.log.debug(
            f"Received {len(request_var)} MNES sub-negotiation request variables: {request_var}"
        )
        for var_name in request_var:
            if var_name in self.mnes.keys():
                send_mnes_value(var_name, self.mnes[var_name])

    def handle_gmcp(self, cmd):
        """
        Handle Generic MUD Communication Protocol, GMCP negotiation https://tintin.mudhalla.net/protocols/gmcp/
        server - IAC WILL GMCP
        client - IAC   DO GMCP
        client - IAC   SB GMCP 'MSDP {"LIST" : "COMMANDS"}' IAC SE
        server - IAC   SB GMCP 'MSDP {"COMMANDS":["LIST","REPORT","RESET","SEND","UNREPORT"]}' IAC SE
        """
        nohandle = False
        if cmd == WILL:
            # 1. Reply agreeing or disagreeing to GMCP
            if Settings.server["GMCP"]:
                self.session.write(IAC + DO + GMCP)
                self.log.debug(
                    "Sent option negotiation, agree to GMPC negotiation IAC DO GMCP."
                )
            else:
                self.session.write(IAC + DONT + GMCP)
                self.log.debug(
                    "Sent option negotiation, disagree to GMPC negotiation IAC DONT GMCP."
                )

            # 2. Send GMCP sub-negotiation, get MSDP related commands? To be determined for future processing
            # MSDP protocol supported, do not use GMCP to get MSDP related commands, i.e., do not use MDSP over GMCP
            # self.session.write(IAC + SB + GMCP + b'MSDP {"LIST" : "COMMANDS"}' + IAC + SE)
            # self.log.debug(f'Sent GMPC sub-negotiation IAC SB GMCP ''MSDP {"LIST" : "COMMANDS"}'' IAC SE.')
        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled GMCP negotiation from server: IAC {name_command(cmd)} GMCP"
            )

    def handle_gmcp_sb(self, data: bytes):
        """
        Handle GMCP sub-negotiation https://tintin.mudhalla.net/protocols/gmcp/
        """
        # Evennia GMCP data example:
        # After sending IAC DO GMCP, when sending MSDP sub-negotiation request, will receive both MSDP data and GMCP data
        # b'\xff\xfa\xc9Core.Lists ["commands", "lists", "configurable_variables", "reportable_variables", "reported_variables", "sendable_variables"]\xff\xf0'
        # b'\xff\xfa\xc9Reportable.Variables ["name", "location", "desc"]\xff\xf0'
        # b'\xff\xfa\xc9GMCP.Move [{"result":"true","dir":["southeast","southwest","northup"],"short":"\xb9\xcf\xb2\xbd"}]\xff\xf0'
        # b'\xff\xfa\xc9GMCP.Status {"qi":1045,"name":"\xc4\xbd\xc8\xdd\xca\xc0\xbc\xd2\xbc\xd2\xd4\xf4","id":"xqtraveler\'s murong jiazei#7300006"}\xff\xf0',
        # Received GMCP option sub-negotiation:
        # Server sub-negotiation length is uncertain, middle using string to represent a series of content, content length is total length-5
        # Sub-negotiation total length-5 is the state content of sub-negotiation, first 3 bytes of sub-negotiation are IAC SB GMCP, last 2 bytes are IAC SE
        gmcp_data = data[3:-2].decode(self.encoding)

        space_split = gmcp_data.find(" ")
        name = gmcp_data[:space_split]
        value = gmcp_data[space_split + 1 :]

        # try:
        #     value = eval(value_str)
        # except:
        #     value = value_str

        self.log.debug(f"Received GMCP sub-negotiation data: {name} = {value}")
        self.session.feed_gmcp(name, value)

    def handle_msdp(self, cmd):
        """
        Handle MUD Server Data Protocol, MSDP negotiation https://tintin.mudhalla.net/protocols/msdp/
        """
        # server - IAC WILL MSDP
        # client - IAC   DO MSDP
        # client - IAC   SB MSDP MSDP_VAR "LIST" MSDP_VAL "COMMANDS" IAC SE
        # server - IAC   SB MSDP MSDP_VAR "COMMANDS" MSDP_VAL MSDP_ARRAY_OPEN MSDP_VAL "LIST" MSDP_VAL "REPORT" MSDP_VAL "SEND" MSDP_ARRAY_CLOSE IAC SE
        # client - IAC   SB MSDP MSDP_VAR "LIST" MSDP_VAL "REPORTABLE_VARIABLES" IAC SE
        # server - IAC   SB MSDP MSDP_VAR "REPORTABLE_VARIABLES" MSDP_VAL "HINT" IAC SE
        # client - IAC   SB MSDP MSDP_VAR "SEND" MSDP_VAL "HINT" IAC SE
        # server - IAC   SB MSDP MSDP_VAR "HINT" MSDP_VAL "THE GAME" IAC SE

        nohandle = False
        if cmd == WILL:
            # 1. Reply agreeing or disagreeing to MSDP
            if Settings.server["MSDP"]:
                self.session.write(IAC + DO + MSDP)
                self.log.debug(
                    "Sent option negotiation, agree to MSDP negotiation IAC DO MSDP."
                )
                self.send_msdp_sb(b"LIST", b"LISTS")
                self.send_msdp_sb(b"LIST", b"REPORTABLE_VARIABLES")

            else:
                self.session.write(IAC + DONT + MSDP)
                self.log.debug(
                    "Sent option negotiation, disagree to MSDP negotiation IAC DONT MSDP."
                )

        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled MSDP negotiation from server: IAC {name_command(cmd)} MSDP"
            )

    def send_msdp_sb(self, cmd: bytes, param: bytes):
        """
        Send MSDP sub-negotiation, get MSDP related data
        """
        sbneg = bytearray()
        sbneg.extend(IAC + SB + MSDP)
        sbneg.append(MSDP_VAR)
        sbneg.extend(cmd)
        sbneg.append(MSDP_VAL)
        sbneg.extend(param)
        sbneg.extend(IAC + SE)
        self.session.write(sbneg)
        self.log.debug(
            f'Sent MSDP sub-negotiation querying supported MSDP commands IAC SB MSDP MSDP_VAR "{cmd.decode(self.encoding)}" MSDP_VAL "{param.decode(self.encoding)}" IAC SE.'
        )

    def handle_msdp_sb(self, data):
        """
        Handle MSDP sub-negotiation https://tintin.mudhalla.net/protocols/msdp/
        """
        # b'\xff\xfaE\x01commands\x02\x05\x02bot_data_in\x02client_gui\x02client_options\x02default\x02echo\x02external_discord_hello\x02get_client_options\x02get_inputfuncs\x02get_value\x02hello\x02login\x02monitor\x02monitored\x02list\x02report\x02send\x02unreport\x02repeat\x02supports_set\x02text\x02unmonitor\x02unrepeat\x02webclient_options\x06\xff\xf0'
        msdp_data = dict()  # Save server available msdp command list

        # Server sub-negotiation length is uncertain, containing several VAR and corresponding several VAL (each VAL may contain several in array or table form)
        # Variable names and values are all represented as strings
        # Sub-negotiation total length-5 is the state content of sub-negotiation, first 3 bytes of sub-negotiation are IAC SB MSDP, last 2 bytes are IAC SE
        var_name = bytearray()
        val_in_array = list()
        val_in_table = dict()
        val_in_text = bytearray()

        table_var_name, table_var_value = bytearray(), bytearray()

        state_machine = "wait_var"
        for idx in range(3, len(data) - 2):
            byte = data[idx]
            if state_machine == "wait_var":  # Next byte is type MSDP_VAR
                if byte == MSDP_VAR:
                    # Receive variable name
                    state_machine = "wait_var_name"
                    var_name.clear()  # var_name waiting to receive variable name
                else:
                    self.log.warning(
                        f"MSDP state machine error: In state wait_var received data that is not MSDP_VAR, but {str(byte)}"
                    )
            elif state_machine == "wait_var_name":
                if (
                    byte == MSDP_VAL
                ):  # MSDP_VAL indicates variable name ends, next is value
                    val_in_array.clear()
                    val_in_table.clear()
                    val_in_text.clear()
                    current_var = var_name.decode(self.encoding)
                    msdp_data[current_var] = None
                    state_machine = "wait_var_value"
                elif byte in (
                    MSDP_ARRAY_OPEN,
                    MSDP_ARRAY_CLOSE,
                    MSDP_TABLE_OPEN,
                    MSDP_TABLE_CLOSE,
                ):  # Theoretically shouldn't be this
                    self.log.warning(
                        f"MSDP state machine error: In state wait_var_name received data that is not MSDP_VAL, but {byte}"
                    )
                    # Should discard data, directly return
                else:
                    var_name.append(byte)
            elif state_machine == "wait_var_value":
                if byte == MSDP_ARRAY_OPEN:  # value is an array
                    state_machine = "wait_val_in_array"
                elif byte == MSDP_TABLE_OPEN:  # value is a table, save using dictionary
                    state_machine = "wait_val_in_table"
                elif byte in (IAC, MSDP_VAR, MSDP_VAL):  # Normal data value ends
                    current_val = val_in_text.decode(self.encoding)
                    msdp_data[current_var] = current_val
                    state_machine = "wait_end"
                    self.log.debug(
                        f"Received text form MSDP sub-negotiation data: {current_var} = '{current_val}'"
                    )
                else:  # value is normal data
                    val_in_text.append(byte)
            elif state_machine == "wait_val_in_array":
                if byte == MSDP_ARRAY_CLOSE:
                    # Last val has ended
                    val_in_array.append(val_in_text.decode(self.encoding))
                    val_in_text.clear()
                    msdp_data[current_var] = val_in_array
                    state_machine = "wait_end"
                    self.log.debug(
                        f"Received array form MSDP sub-negotiation data: {current_var} = '{val_in_array}'"
                    )
                elif byte == MSDP_VAL:
                    if (
                        len(val_in_text) > 0
                    ):  # One VAL is completed, save to array, there are more vals
                        val_in_array.append(val_in_text.decode(self.encoding))
                        val_in_text.clear()
                else:
                    val_in_text.append(byte)
            elif state_machine == "wait_val_in_table":
                if byte == MSDP_TABLE_CLOSE:
                    # Last group has ended
                    val_in_table[table_var_name.decode[self.encoding]] = (
                        table_var_value.decode[self.encoding]
                    )
                    msdp_data[current_var] = val_in_table
                    state_machine = "wait_end"
                    self.log.debug(
                        f"Received table form MSDP sub-negotiation data: {current_var} = '{val_in_table}'"
                    )
                elif byte == MSDP_VAR:
                    if (
                        len(table_var_name) > 0
                    ):  # Previous VAL is completed, save to table, continue with VAR
                        val_in_table[table_var_name.decode[self.encoding]] = (
                            table_var_value.decode[self.encoding]
                        )
                        table_var_name.clear()
                        table_var_value.clear()
                    state_machine_table = "wait_table_var"
                elif byte == MSDP_VAL:
                    state_machine_table = "wait_table_val"
                else:
                    if state_machine_table == "wait_table_var":
                        table_var_name.append(byte)
                    elif state_machine_table == "wait_table_val":
                        table_var_value.append(byte)
                    else:
                        self.log.warning(
                            f"MSDP state machine error: In state wait_val_in_table, state is incorrect, is {state_machine_table}, received data is {byte}"
                        )

        # Update MSDP_supported data to server
        self.msdp.update(msdp_data)
        self.log.debug(
            f"MSDP server status sub-negotiation processing completed, received {len(msdp_data.keys())} sets of VAR/VAL data."
        )

    def handle_mssp(self, cmd):
        """
        Handle MUD Server Status Protocol, MSSP negotiation https://tintin.mudhalla.net/protocols/mssp/
        server - IAC WILL MSSP
        client - IAC DO MSSP
        server - IAC SB MSSP MSSP_VAR "PLAYERS" MSSP_VAL "52" MSSP_VAR "UPTIME" MSSP_VAL "1234567890" IAC SE
        """
        nohandle = False
        if cmd == WILL:
            # 1. Reply agreeing to MSSP negotiation
            if Settings.server["MSSP"]:
                self.session.write(IAC + DO + MSSP)
                self._mtts_index = 0
                self.log.debug(
                    "Sent option negotiation, agree to MSSP negotiation IAC DO MSSP. Waiting for sub-negotiation"
                )
            else:
                self.session.write(IAC + DONT + MSSP)
                self.log.debug(
                    "Sent option negotiation, disagree to MSSP negotiation IAC DONT MSSP. Waiting for sub-negotiation"
                )
        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled MSSP negotiation from server: IAC {name_command(cmd)} MSSP"
            )

    def handle_mssp_sb(self, data):
        """
        Handle MSSP sub-negotiation
        server - IAC SB MSSP MSSP_VAR "PLAYERS" MSSP_VAL "52" MSSP_VAR "UPTIME" MSSP_VAL "1234567890" IAC SE
        # The following status information is mandatory
        NAME               Name of the MUD.
        PLAYERS            Current number of logged in players.
        UPTIME             Unix time value of the startup time of the MUD.
        For detailed status information definition, see https://tintin.mudhalla.net/protocols/mssp/
        """

        def add_svr_status(var: bytearray, val: bytearray):
            if len(var) > 0:
                var_str = var.decode(self.encoding)
                val_str = val.decode(self.encoding)
                svrStatus[var_str] = val_str
                self.session.feed_mssp(var_str, val_str)
                self.log.debug(
                    f"Received server status (from MSSP sub-negotiation): {var_str} = {val_str}"
                )

        svrStatus = dict()  # Use dictionary to save server status information

        # Server sub-negotiation length is uncertain, containing several VAR (VARIABLE, variable name) and corresponding number of VAL (VALUE, variable value)
        # Variable names and values are all represented as strings
        # Sub-negotiation total length-5 is the state content of sub-negotiation, first 3 bytes of sub-negotiation are IAC SB MSSP, last 2 bytes are IAC SE
        var, val = bytearray(), bytearray()
        next_bytes = "type"
        for idx in range(3, len(data) - 2):
            byte = data[idx]
            if byte == MSSP_VAR:
                # Indicates previous group of VAR, VAL has been received
                add_svr_status(var, val)
                # Reset var, val variables to receive the next one
                var.clear()
                val.clear()
                next_bytes = "var"
            elif byte == MSSP_VAL:
                next_bytes = "val"
            else:
                if next_bytes == "var":
                    var.append(byte)
                elif next_bytes == "val":
                    val.append(byte)
                else:
                    self.log.warning(
                        "Received abnormal sequence in MSSP sub-negotiation!!"
                    )

        # After data processing, the last group of VAR/VAL before ending IAC SE still needs to be added
        add_svr_status(var, val)
        # Update status to server
        self.mssp.update(svrStatus)
        self.log.debug(
            f"MSSP server status sub-negotiation processing completed, received {len(svrStatus.keys())} sets of VAR/VAL data."
        )

    def handle_mccp2(self, cmd):
        """
        Handle MUD Client Compression Protocol V2 negotiation https://mudhalla.net/tintin/protocols/mccp/
        server - IAC WILL MCCP2
        client - IAC DONT MCCP2
        Currently does not accept client compression (not implemented)
        """
        nohandle = False
        if cmd == WILL:
            # 1. Reply disagreeing to MCCP2 negotiation
            if Settings.server["MCCP2"]:
                self.session.write(IAC + DO + MCCP2)
                self.log.debug(
                    "Sent option negotiation, agree to MCCP V2 negotiation IAC DO MCCP2"
                )
            else:
                self.session.write(IAC + DONT + MCCP2)
                self.log.debug(
                    "Sent option negotiation, disagree to MCCP V2 negotiation IAC DONT MCCP2"
                )

        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled MCCP V2 negotiation from server: IAC {name_command(cmd)} MCCP2"
            )

    def handle_mccp3(self, cmd):
        """
        Handle MUD Client Compression Protocol V3 negotiation https://mudhalla.net/tintin/protocols/mccp/
        server - IAC WILL MCCP3
        client - IAC DONT MCCP3
        Currently does not accept client compression (not implemented)
        """
        nohandle = False
        if cmd == WILL:
            # 1. Reply disagreeing to MCCP3 negotiation
            if Settings.server["MCCP3"]:
                self.session.write(IAC + DO + MCCP3)
                self.log.debug(
                    "Sent option negotiation, agree to MCCP V3 negotiation IAC DO MCCP3"
                )
            else:
                self.session.write(IAC + DONT + MCCP3)
                self.log.debug(
                    "Sent option negotiation, disagree to MCCP V3 negotiation IAC DONT MCCP3"
                )

        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled MCCP V3 negotiation from server: IAC {name_command(cmd)} MCCP3"
            )

    def handle_msp(self, cmd):
        """
        Handle MUD Sound Protocol negotiation http://www.zuggsoft.com/zmud/msp.htm
        server - IAC WILL MSP
        client - IAC DONT MSP
        Currently does not accept MUD Sound Protocol (not implemented)
        """
        nohandle = False
        if cmd == WILL:
            # 1. Reply disagreeing to MSP negotiation
            if Settings.server["MSP"]:
                self.session.write(IAC + DO + MSP)
                self.log.debug(
                    "Sent option negotiation, agree to MSP negotiation IAC DO MSP"
                )
            else:
                self.session.write(IAC + DONT + MSP)
                self.log.debug(
                    "Sent option negotiation, disagree to MSP negotiation IAC DONT MSP"
                )

        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled MSP negotiation from server: IAC {name_command(cmd)} MSP"
            )

    def handle_mxp(self, cmd):
        """
        Handle MUD eXtension Protocol negotiation http://www.zuggsoft.com/zmud/mxp.htm
        server - IAC WILL MXP
        client - IAC DONT MXP
        Currently does not accept MUD eXtension Protocol (not implemented)
        """
        nohandle = False
        if cmd == WILL:
            if Settings.server["MXP"]:
                self.session.write(IAC + DO + MXP)
                self.log.debug(
                    "Sent option negotiation, agree to MXP negotiation IAC DO MXP"
                )
            else:
                self.session.write(IAC + DONT + MXP)
                self.log.debug(
                    "Sent option negotiation, disagree to MXP negotiation IAC DONT MXP"
                )

        elif cmd == WONT:
            nohandle = True
        elif cmd == DO:
            nohandle = True
        elif cmd == DONT:
            nohandle = True
        else:
            nohandle = True

        if nohandle:
            self.log.warning(
                f"Received unhandled MXP negotiation from server: IAC {name_command(cmd)} MXP"
            )
