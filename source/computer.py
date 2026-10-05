
from source.memory import ComputerMemory
from source.CPU import CPU
from source.ports import Ports
from source.graphics.screen import ScreenInterface


from source.utils import get_safe_path
import numpy as np
import os
import time


class Computer:
    def __init__(self):
        self.ports = Ports()
        self.mem = ComputerMemory()
        self.cpu = CPU()

        self.ports._cpu = self.cpu
        self.mem._cpu = self.cpu
        self.mem._ports = self.ports
        self.cpu._mem = self.mem
        self.ticks = 0

    def boot(self, bios_path='bios.bin'):
        SHADOW_LIMIT = 0x8000

        BIOS_PATH = get_safe_path(bios_path)

        file_size = os.path.getsize(BIOS_PATH)
        if file_size > SHADOW_LIMIT:
            raise ValueError(f"BIOS too large! {file_size} > {SHADOW_LIMIT}")

        self.mem._shadow_size = file_size

        try:
            self.mem._shadow = np.fromfile(BIOS_PATH, dtype=np.uint8)
        except IOError as e:
            raise e

        self.mem._library_size = SHADOW_LIMIT
        self.mem._kernel_size = SHADOW_LIMIT

        self.screen = ScreenInterface()

        self.cpu.reset()
        self.mem._ram.fill(0)
        self.ports.setup_default_ports(self.mem, self.screen)

        self.bios_path = bios_path

        print(f"System Booted. Shadow Size: {self.mem._shadow_size} bytes.")
        self.ticks = 0

    def boot_headless(self, bios_path='bios.bin'):
        SHADOW_LIMIT = 0x8000

        BIOS_PATH = get_safe_path(bios_path)

        file_size = os.path.getsize(BIOS_PATH)
        if file_size > SHADOW_LIMIT:
            raise ValueError(f"BIOS too large! {file_size} > {SHADOW_LIMIT}")

        self.mem._shadow_size = file_size

        try:
            self.mem._shadow = np.fromfile(BIOS_PATH, dtype=np.uint8)
        except IOError as e:
            raise e

        self.mem._library_size = SHADOW_LIMIT
        self.mem._kernel_size = SHADOW_LIMIT

        self.screen = ScreenInterface()
        self.screen.shutdown()

        self.cpu.reset()
        self.mem._ram.fill(0)
        self.ports.setup_default_ports(self.mem, self.screen)

        self.bios_path = bios_path

        print(f"System Booted. Shadow Size: {self.mem._shadow_size} bytes.")
        self.ticks = 0

    def reboot(self):
        self.boot(self.bios_path)

    def reboot_headless(self):
        self.boot_headless(self.bios_path)

    def step(self):
        if self.cpu.triple_faulted:
            print("CRITICAL: Triple Fault. System Halted.")
            return False

        for p in self.ports._ticking_devices:
            p.tick()
        
        if self.cpu._level > 1 and self.cpu.interrupts_enabled:
            irq_vector = self.ports.get_priority_vector()
            if irq_vector is not None:
                self.cpu.halted = False
                self.cpu.handle_irq(irq_vector)
                self.ports.ack_irq(irq_vector)

        if not self.cpu.halted:
            self.cpu.tick()
        return not (self.cpu.stopped or self.cpu.triple_faulted)

    def run(self):
        FRAME_TIME_NS = 16_666_666
        CHUNK_SIZE = 100

        last_vblank_time = time.perf_counter_ns()
        # last_tick_count = 0
        # self.ticks = 0
        running = True
        while running:
            count = 0
            while running and count < CHUNK_SIZE:
                self.ticks += 1
                count += 1
                running = self.step()
            current_time = time.perf_counter_ns()

            if current_time - last_vblank_time >= FRAME_TIME_NS:
                # print(f"ticks this frame: {self.ticks - last_tick_count}")
                # last_tick_count = self.ticks

                if current_time - last_vblank_time > FRAME_TIME_NS * 5:
                    last_vblank_time = current_time - FRAME_TIME_NS
                else:
                    last_vblank_time += FRAME_TIME_NS

                running = self.screen.pump_events()
        self.screen.shutdown()

    def run_headless(self, limit=None):
        count = 0
        while self.step():
            self.ticks += 1
            count += 1
            if limit and count >= limit:
                break