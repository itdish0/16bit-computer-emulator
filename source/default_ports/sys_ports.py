
class SysPorts:
    def __init__(self, mem, cpu):
        self.wrapper = None

        self.mem = mem
        self.cpu = cpu

    def status(self):
        return 0

    def command(self, cmd):
        match cmd:
            case 1:   # Setup kernel size
                if self.mem._shadow_size == 0:
                    return
                self.mem._kernel_end = self.wrapper.argh << 8
                self.mem._library_end = self.wrapper.argl << 8
                self.mem._resolve_usr_lib_offset()
            case 2:   # UNSHADOW
                self.mem._shadow_size = 0
                self.cpu.queue_pc(self.wrapper.arg())
            case 3:   # SANDBOX
                self.mem._usr_base = self.wrapper.argh << 8
                self.mem._usr_size = self.wrapper.argl << 8
            case 4:   # USER_MODE
                self.cpu._level = 3
                self.cpu.queue_pc(self.wrapper.arg())
            case _:
                pass

    def reset(self):
        self.cpu.fault(-1)
