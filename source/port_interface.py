

class PortInterface:
    def __init__(self, port, ports=None, irq_vector=-1):
        self.idflag = 0xFF
        self.argl = 0x00
        self.argh = 0x00
        self.size = 4
        self.port = port
        self.stream_mode = PortInterface.STREAM_NONE
        self.stream = bytearray()
        self._err_mask = 0x00
        self.stream_max = getattr(port, 'stream_max', PortInterface.DEFAULT_STREAM_MAX)
        self.custom_read = getattr(port, 'custom_read', False)
        self.custom_write = getattr(port, 'custom_write', False)
        self.custom_stream = getattr(port, 'custom_stream', False)
        port.wrapper = self
        self.ports = ports
        self.irq_vector = irq_vector

    CMD_NOP = 0x00
    CMD_ACK = 0xFE
    CMD_RST = 0xFF

    ERR_STREAM_OVERFLOW = 0xF0
    ERR_STREAM_NONE_R = 0xF1
    ERR_STREAM_NONE_W = 0xF2

    STREAM_NONE = 0x00
    STREAM_STR_IN = 0x01
    STREAM_STR_OUT = 0x02
    STREAM_DATA_OUT = 0x03

    DEFAULT_STREAM_MAX = 256

    def arg(self):
        return (self.argl) + (self.argh << 8)

    def set_arg(self, val):
        self.argl = val & 0xFF
        self.argh = (val >> 8) & 0xFF

    def read(self, offset):
        match offset:
            case 0:
                return self.port.status() | self._err_mask
            case 1:
                return self.read_stream()
            case 2:
                if self.custom_read:
                    return self.port.read_argl()
                return self.argl
            case 3:
                if self.custom_read:
                    return self.port.read_argh()
                return self.argh
            case _:
                return 0

    def write(self, offset, val):
        match offset:
            case 0:
                if val == 0:
                    pass
                elif val == 0xFE:
                    self._ack_err()
                    self.port.ack_err()
                elif val == 0xFF:
                    self._ack_err()
                    self.port.reset()
                elif self._err_mask == 0:
                    self.port.command(val)
            case 1:
                self.write_stream(val)
            case 2:
                if self.custom_write:
                    self.port.write_argl(val)
                else:
                    self.argl = val
            case 3:
                if self.custom_write:
                    self.port.write_argh(val)
                else:
                    self.argh = val
            case _:
                pass

    def _ack_err(self):
        self._err_mask = 0
        self.argl = 0
        self.argh = 0

    def err(self, category, detail=0x00):
        self.argl = category
        self.argh = detail
        self._err_mask = 0x80
        self.stream_mode = PortInterface.STREAM_NONE
        self.stream.clear()

    def begin_stream(self, mode):
        self.stream.clear()
        self.stream_mode = mode

    def read_stream(self):
        match self.stream_mode:
            case PortInterface.STREAM_NONE:
                self.err(PortInterface.ERR_STREAM_NONE_R)
                return 0
            case PortInterface.STREAM_DATA_OUT:
                return self.port.stream_next()
            case PortInterface.STREAM_STR_OUT:
                val = self.port.stream_str_next()
                if val == 0:
                    self.stream_mode = PortInterface.STREAM_NONE
                return val
            case _:
                return 0

    def write_stream(self, val):
        match self.stream_mode:
            case PortInterface.STREAM_NONE:
                self.err(PortInterface.ERR_STREAM_NONE_W)
            case PortInterface.STREAM_STR_IN:
                if val == 0:
                    self.port.stream_string(
                        "".join(chr(b) for b in self.stream)
                    )
                    self.stream_mode = PortInterface.STREAM_NONE
                else:
                    self.stream.append(val)
                    if len(self.stream) > self.stream_max:
                        self.err(PortInterface.ERR_STREAM_OVERFLOW)
            case _:
                pass

    def tick(self):
        self.port.tick()

    def raise_irq(self):
        if self.ports is not None:
            self.ports.raise_irq(self)

    def lower_irq(self):
        if self.ports is not None:
            self.ports.lower_irq(self)

    def ack_irq(self):
        self.port.ack_irq()

# Default implementation:
"""
class StandardPort:
    def __init__(self):
        self.wrapper = None

    def status(self):
        return 0

    def command(self, cmd):
        match cmd:
            case _:
                pass

    def reset(self):
        pass

    def ack_err(self):
        pass
"""
