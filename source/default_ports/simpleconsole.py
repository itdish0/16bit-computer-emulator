class ConsoleIOPort:
    def __init__(self):
        self.size = 2
        self.idflag = 0x10
        self._in_buffer = ""
        self._out_buffer = bytearray()
        self._bufferoffset = 0
        self._bufferlen = 0

    def write(self, offset, val):
        match offset:
            case 0:
                if val == 0x00:
                    print("".join(chr(b) for b in self._out_buffer), end="", flush=True)
                    self._out_buffer.clear()
                else:
                    self._out_buffer.append(val)
            case 1:
                self._in_buffer = input()
                self._bufferoffset = 0
                self._bufferlen = len(self._in_buffer)

    def read(self, offset):
        match offset:
            case 1:
                if self._bufferoffset >= self._bufferlen:
                    return 0
                val = ord(self._in_buffer[self._bufferoffset])
                self._bufferoffset += 1
                return val
            case _:
                return 0
