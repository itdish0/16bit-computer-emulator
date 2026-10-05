
from source.default_ports.simpleconsole import ConsoleIOPort
from source.default_ports.disk_port import DiskPort
from source.default_ports.dma_port import DMAPort
from source.default_ports.sys_ports import SysPorts
from source.default_ports.screen_ports import ScreenPorts
from source.default_ports.input_port import InputPort
from source.default_ports.bitBLT import BitBLT

from source.port_interface import PortInterface as PortInt
from source.CPU import SEGFAULT

IRQ_VECTORS = 12
SYS_PORT_READ = 0x2
SYS_PORT_WRITE = 0x3

class Ports:

    def __init__(self):
        self.ports = [None] * 0x100
        self.port_privilege = [True] * 0x100

        self._ticking_devices = []
        self._cpu = None
        self._irq_lines = [None] * IRQ_VECTORS

    def setup_default_ports(self, mem, screen):
        sys = SysPorts(mem, self._cpu)
        disk = DiskPort("System")
        dma = DMAPort(mem, disk)
        bit_blt = BitBLT(mem)
        screen_ports = ScreenPorts(screen, bit_blt)

        input_port = InputPort()

        screen.screen_port = screen_ports
        screen.input_port = input_port

        self._register_internal(0x00, 4, PortInt(sys))
        self._register_internal(0x04, 4, PortInt(disk, self, 0x02), ticking=True)
        self._register_internal(0x08, 4, PortInt(dma, self, 0x01), ticking=True)
        self._register_internal(0x0C, 4, PortInt(screen_ports, self, 0x03), ticking=True)
        self._register_internal(0x10, 4, PortInt(bit_blt, self, 0x04), ticking=True, privileged=False)
        self._register_internal(0x14, 4, input_port, privileged=False)
        self._register_internal(0xF0, 2, ConsoleIOPort(), privileged=False)

    def writeport(self, index, val):
        index &= 0xFF
        port = self.ports[index]
        if port is None:
            return
        privileged = self.port_privilege[index]
        if privileged and not self._cpu.kernel_mode():
            self._cpu.fault(SEGFAULT, SYS_PORT_WRITE)
            return
        port.write(index-port.base_addr, val)

    def readport(self, index):
        index &= 0xFF
        port = self.ports[index]
        if port is None:
            return 0
        privileged = self.port_privilege[index]
        if privileged and not self._cpu.kernel_mode():
            self._cpu.fault(SEGFAULT, SYS_PORT_READ)
            return 0
        return port.read(index-port.base_addr)

    def _register_internal(self, offset, size, port, ticking=False, privileged=True):
        port.base_addr = offset
        for i in range(offset, offset + size):
            self.ports[i] = port
            self.port_privilege[i] = privileged
        if ticking:
            self._ticking_devices.append(port)

    def raise_irq(self, trigger):
        vector = trigger.irq_vector
        if vector >= 0 and vector < IRQ_VECTORS:
            self._irq_lines[vector] = trigger

    def lower_irq(self, trigger):
        vector = trigger.irq_vector
        if vector >= 0 and vector < IRQ_VECTORS:
            self._irq_lines[vector] = None

    def ack_irq(self, vector):
        if vector >= 0 and vector < IRQ_VECTORS:
            self._irq_lines[vector].ack_irq()
            self._irq_lines[vector] = None

    def get_priority_vector(self):
        for i, p in enumerate(self._irq_lines):
            if p is not None:
                return i
        return None