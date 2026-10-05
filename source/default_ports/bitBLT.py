
class BitBLT:
    def __init__(self, mem):
        self.wrapper = None
        self.is_ticking = True

        self.mem = mem

        self.current_window = None

    WRITE_BUFFER = 0
    FILL_BUFFER = 1
    READ_BUFFER = 2
    READ_SCREEN = 3
    SET_PALETTE = 4
    READ_PALETTE = 5

    def status(self):
        status = 0
        window = self.current_window
        if window is None:
            return status
        if window.active:
            status |= 0x01
        if window.dirty:
            status |= 0x02
        return status

    def command(self, cmd):
        window = self.current_window
        if window is None:
            return
        match cmd:
            case 1:   # LOC
                window.blit_addr = self.wrapper.arg()
            case 2:   # POS
                x = self.wrapper.argl
                y = self.wrapper.argh
                if y >= window._height:
                    y = window._height-1
                if x >= window._width:
                    x = window._width-1
                window.blit_x = x
                window.blit_y = y
            case 3:   # SIZE
                w = self.wrapper.argl
                if w == 0:
                    w = 256
                h = self.wrapper.argh
                if h == 0:
                    h = 256
                window.blit_w = w
                window.blit_h = h
            case 5:   # STOP
                window.active = False
            case 0x0C:  # SET_TRANSPARENT_COLOR
                window.transparent_color = self.wrapper.arg()
            case 0x0D:  # SET_COLOR
                window.color = self.wrapper.arg()
            case 0x0F:  # SET_PIXEL
                window.set_pixel_buffer()
            case 0x10:  # GET_PIXEL
                c = window.get_pixel_buffer()
                self.wrapper.set_arg(c)
            case 0x11:  # GET_PIXEL_SCREEN
                c = window.get_pixel_screen()
                self.wrapper.set_arg(c)
        if window.active:
            return
        match cmd:
            case 4:   # WRITE_BUFFER
                window.start_blit(BitBLT.WRITE_BUFFER)
            case 6:   # SHOW_BUFFER
                window.show_buffer()
                window.dirty = True
            case 7:   # FILL_BUFFER
                window.start_blit(BitBLT.FILL_BUFFER)
            case 8:  # SET_PALETTE
                window.start_blit(BitBLT.SET_PALETTE)
            case 9:   # READ_BUFFER
                window.start_blit(BitBLT.READ_BUFFER)
            case 0x0A:  # READ_SCREEN
                window.start_blit(BitBLT.READ_SCREEN)
            case 0x0B:  # READ_PALETTE
                window.start_blit(BitBLT.READ_PALETTE)
            case 0x0E: # CLS
                window.clear_buffer(window.color)
            case _:
                pass

    def reset(self):
        self.current_window = None

    def ack_err(self):
        pass

    def ack_irq(self):
        pass

    def tick(self):
        window = self.current_window
        if window is None:
            return
        if not window.active:
            return
        match window.mode:
            case BitBLT.WRITE_BUFFER:
                b = self.mem.read(window._curr_blit_addr)
                window.blit_buffer_write(b)
                window._curr_blit_addr += 1
            case BitBLT.FILL_BUFFER:
                window.blit_buffer_write(window._curr_color)
            case BitBLT.SET_PALETTE:
                c = self.mem.read2(window._curr_blit_addr)
                window.set_palette_single(window._curr_blit_y, c)
                window._blit_h_left -= 1
                window._curr_blit_y += 1
                window._curr_blit_addr += 2
                if window._curr_blit_y == 0x100:
                    window.active = False
                    self.wrapper.raise_irq()
                    return
            case BitBLT.READ_PALETTE:
                c = window.get_palette_single(window._curr_blit_y)
                self.mem.write2(window._curr_blit_addr, c)
                window._blit_h_left -= 1
                window._curr_blit_y += 1
                window._curr_blit_addr += 2
                if window._curr_blit_y == 0x100:
                    window.active = False
                    self.wrapper.raise_irq()
                    return
            case BitBLT.READ_BUFFER:
                b = self.mem.read(window._curr_blit_addr)
                b = window.blit_buffer_read()
                self.mem.write(window._curr_blit_addr, b)
                window.blit_addr += 1
            case BitBLT.READ_SCREEN:
                b = self.mem.read(window._curr_blit_addr)
                b = window.blit_screen_read()
                self.mem.write(window.blit_addr, b)
                window._curr_blit_addr += 1
        if window.blit_done():
            window.active = False
            self.wrapper.raise_irq()
