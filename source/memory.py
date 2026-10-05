
import numpy as np
from source.CPU import SEGFAULT

UNMAPPED_READ = 0x0
UNMAPPED_WRITE = 0x1


class ComputerMemory:

    def __init__(self):
        self._ram = np.zeros(0xFF00, dtype=np.ubyte)
        self._ports = None
        self._cpu = None

        self._shadow = []
        self._shadow_size = 0

        self._kernel_end = 0x7E00   # Also lib_start
        self._library_end = 0x8000

        self._usr_base = 0x8000
        self._usr_size = 0x0000

        self._resolve_usr_lib_offset()

    def _resolve_usr_lib_offset(self):
        self._usr_lib_offset = 0xFF00 - self._library_end

    def read(self, index):
        index &= 0xFFFF
        if self._cpu.kernel_mode():
            return self._read_raw(index)
        addr = self._get_usr_read_addr(index)
        if addr is None:
            return 0
        return self._read_raw(addr)

    def read2(self, index):
        index &= 0xFFFF
        if self._cpu.kernel_mode():
            return self._read2_raw(index)
        addr = self._get_usr_read_addr(index)
        if addr is None:
            return 0
        val = self._read2_raw(addr)
        return val

    def write(self, index, val):
        index &= 0xFFFF
        val &= 0xFF
        if self._cpu.kernel_mode():
            self._write_raw(index, val)
            return
        addr = self._get_usr_write_addr(index)
        if addr is None:
            return
        self._write_raw(addr, val)

    def write2(self, index, val):
        index &= 0xFFFF
        val &= 0xFFFF
        if self._cpu.kernel_mode():
            self._write2_raw(index, val)
            return
        addr = self._get_usr_write_addr(index)
        if addr is None:
            return
        self._write2_raw(addr, val)

    def _get_usr_read_addr(self, index):
        if index < self._usr_size:
            # User program
            return self._usr_base + index
        if index >= 0xFF00:
            # Ports
            return index
        if index >= self._kernel_end + self._usr_lib_offset:
            # Part of the Library
            return index - self._usr_lib_offset
        # Invalid memory space
        self._cpu.fault(SEGFAULT, UNMAPPED_READ)
        return None

    def _get_usr_write_addr(self, index):
        if index < self._usr_size:
            # User program
            return self._usr_base + index
        if index >= 0xFF00:
            # Ports
            return index
        # Invalid memory space
        self._cpu.fault(SEGFAULT, UNMAPPED_WRITE)
        return None

    def _read_raw(self, index):
        if index < self._shadow_size:
            return int(self._shadow[index])
        if index < 0xFF00:
            return int(self._ram[index])
        return self._ports.readport(index)

    def _read2_raw(self, index):
        if index < self._shadow_size:
            if index == self._shadow_size - 1:
                lower = self._shadow[index]
                upper = self._ram[index + 1]
            else:
                lower = self._shadow[index]
                upper = self._shadow[index + 1]
        elif index == 0xFFFF and self._shadow_size != 0:
            lower = self._ports.readport(index)
            upper = self._shadow[0]
        else:
            return self._read2_unshadow(index)
        return int(lower)+(int(upper) << 8)

    def _read2_unshadow(self, index):
        if index < 0xFEFF:
            lower = self._ram[index]
            upper = self._ram[index + 1]
        else:
            if index == 0xFEFF:
                lower = self._ram[index]
                upper = self._ports.readport(index + 1)
            elif index == 0xFFFF:
                lower = self._ports.readport(index)
                upper = self._ram[0]
            else:
                lower = self._ports.readport(index)
                upper = self._ports.readport(index + 1)
        return int(lower)+(int(upper) << 8)

    def _write_raw(self, index, value):
        if index < 0xFF00:
            self._ram[index] = value
            return
        self._ports.writeport(index, value)

    def _write2_raw(self, index, value):
        lower = value & 0xFF
        upper = (value >> 8) & 0xFF

        if index < 0xFEFF:
            self._ram[index] = lower
            self._ram[index + 1] = upper
            return

        if index == 0xFEFF:
            self._ram[index] = lower
            self._ports.writeport(index + 1, upper)
            return

        if index == 0xFFFF:
            self._ports.writeport(index, lower)
            self._ram[0] = upper
        else:
            self._ports.writeport(index, lower)
            self._ports.writeport(index + 1, upper)
