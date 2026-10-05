
class DMAPort:
    def __init__(self, mem, disk):
        self.wrapper = None
        self.is_ticking = True

        self.mem = mem
        self.disk = disk

        self.target_loc = 0x0000
        self.target_size = 0x0000
        self.curr_loc = 0x0000
        self.completed_size = 0x0000
        self.active = False

    def status(self):
        status = 0
        if self.active:
            status |= 0x01
        return status

    def command(self, cmd):
        match cmd:
            case 1:   # LOC
                if self.active:
                    pass #return
                self.target_loc = self.wrapper.arg()
            case 2:   # SIZE
                if self.active:
                    pass #return
                self.target_size = self.wrapper.arg()
            case 3:   # START
                if self.active:
                    pass #return
                self.curr_loc = self.target_loc
                self.completed_size = 0x0000
                self.active = True
                self.disk.busy = True
            case 4:   # STOP
                self.active = False
                self.disk.busy = False
            case _:
                pass

    def reset(self):
        self.target_loc = 0x0000
        self.target_size = 0x0000
        self.curr_loc = 0x0000
        self.completed_size = 0x0000
        self.active = False

    def ack_err(self):
        pass

    def ack_irq(self):
        pass

    def tick(self):
        if not self.active:
            return
        if self.disk.dma_read_ready():
            if (self.disk.dma_end()
                    or self.curr_loc >= 0xFF00
                    or self.completed_size >= self.target_size):
                self.active = False
                self.disk.busy = False
                self.wrapper.raise_irq()
                return
            val = self.disk.dma_read()
            self.mem._write_raw(self.curr_loc, val)
            self.completed_size += 1
            self.curr_loc += 1
