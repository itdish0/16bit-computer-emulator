
import numpy as np

class InputPort:
    def __init__(self):
        self.size = 4

        self._buffer = np.zeros(32, dtype=np.uint8)
        self._head = 0
        self._tail = 0
        self._key_overflow = False

        self._delta_x = 0
        self._delta_y = 0
        self._button_left = False
        self._button_middle = False
        self._button_right = False

    def read(self, offset):
        match offset:
            case 0:
                status = 0x00
                if self._head != self._tail:
                    status |= 0x01
                if self._key_overflow:
                    status |= 0x02
                if self._button_right:
                    status |= 0x08
                if self._button_middle:
                    status |= 0x10
                if self._button_left:
                    status |= 0x20
                return status
            case 1:
                return self.pop_byte()
            case 2:
                val = self._delta_x & 0xFF
                self._delta_x = 0
                return val
            case 3:
                val = self._delta_y & 0xFF
                self._delta_y = 0
                return val
            case _:
                return 0

    def write(self, offset, val):
        match offset:
            case 0:
                if val == 0xFF:
                    self._head = 0
                    self._tail = 0
                    self._key_overflow = False

                    self._delta_x = 0
                    self._delta_y = 0
                elif val == 0xFE:
                    self._key_overflow = False
            case 1:
                pass
            case 2:
                pass
            case 3:
                pass
            case _:
                pass

    def push_byte(self, b):
        self._buffer[self._head] = b
        self._head = (self._head + 1) & 0x1F
        if self._head == self._tail:
            self._buffer[self._tail] = 0x00
            self._tail = (self._tail + 1) & 0x1F
            self._key_overflow = True

    def pop_byte(self):
        if self._head == self._tail:
            return 0
        b = self._buffer[self._tail]
        self._tail = (self._tail + 1) & 0x1F
        return b

    def update_axes(self, x, y):
        self._delta_x += x
        self._delta_y += y

    def update_buttons(self, buttons):
        self._button_left = buttons[0]
        self._button_middle = buttons[1]
        self._button_right = buttons[2]
