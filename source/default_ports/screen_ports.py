
# GPU Ports that are privileged

from source.graphics.Window import Window


class ScreenPorts:
    def __init__(self, screen, bit_blt, size=0x80000):
        self.wrapper = None

        self._windows = [None] * 256
        self._next_available_handle = 0
        self._remaining_size = size
        self._current_handle = 0
        self.current_window = None

        self.compositor_handle = 0
        self.compositor_x = 0
        self.compositor_y = 0
        self._fill_color = (0, 0, 0)

        self._screen = screen
        self._bit_blt = bit_blt

    def _new_window(self, width, height):
        if width == 0:
            width = 256
        if height == 0 or height > 192:
            height = 192
        size = 4 * width * height
        if size > self._remaining_size:
            # Throw err
            return 0xFF
        handle = self._next_available_handle
        if handle is None:
            # Throw err
            return 0xFF
        self._remaining_size -= size
        window = Window(width, height)
        self._windows[handle] = window
        self._update_next_available_handle()
        return handle

    def _update_next_available_handle(self):
        handle_found = False
        curr_handle = self._next_available_handle
        while not handle_found:
            curr_handle += 1
            if curr_handle > 255:
                curr_handle = None
                break
            handle_found = self._windows[curr_handle] is None
        self._next_available_handle = curr_handle

    def _remove_window(self, handle):
        window = self._windows[handle]
        if window is None:
            # Throw err
            return 0xFF
        size = 4 * window._width * window._height
        self._remaining_size -= size
        self._windows[handle] = None
        if handle == self._next_available_handle:
            self._current_handle = 0
            self.current_window = None
        if handle < self._next_available_handle:
            self._next_available_handle = handle
        return handle

    def _select_window(self, handle):
        self._current_handle = handle
        window = self._windows[handle]
        self.current_window = window
        self._bit_blt.current_window = window
        if window is None:
            # Throw err
            pass

    def _blit_window(self):
        window = self._windows[self.compositor_handle]
        if window is None:
            # Throw err
            return
        self._screen.draw_array(
            window.get_drawable(), self.compositor_x, self.compositor_y
        )

    def status(self):
        status = 0
        if self.current_window is None:
            status |= 0x01
        return 0

    def command(self, cmd):
        match cmd:
            case 1:   # SEL_WIN
                self._select_window(self.wrapper.argl)
            case 2:   # NEW_WIN
                self.wrapper.argl = self._new_window(
                    self.wrapper.argl, self.wrapper.argh
                )
            case 3:   # DEL_WIN
                self._remove_window(self.wrapper.argl)
            case 4:   # BLT_WIN
                self._blit_window()
            case 5:   # SCRN_SHOW
                self._screen.update()
            case 6:   # SCRN_FILL
                self._screen.clear(self._fill_color)
            case 7:   # SET_FILL_CLR
                c = self.wrapper.arg()
                r = (c & 0xF800) >> 11
                g = (c & 0x07E0) >> 5
                b = (c & 0x001F)
                self._fill_color = (
                    (r * 255) // 31,
                    (g * 255) // 63,
                    (b * 255) // 31
                )
            case 8:   # SET_BLT_HNDL
                self.compositor_handle = self.wrapper.argl
            case 9:   # SET_BLIT_X
                arg = self.wrapper.arg()
                argm = arg & 0x7FFF
                if arg & 0x8000 != 0:
                    self.compositor_x = -argm
                else:
                    self.compositor_x = argm
            case 0xA:   # SET_BLIT_Y
                arg = self.wrapper.arg()
                argm = arg & 0x7FFF
                if arg & 0x8000 != 0:
                    self.compositor_y = -argm
                else:
                    self.compositor_y = argm
            case _:
                pass

    def vblank(self):
        self.wrapper.raise_irq()

    def reset(self):
        pass

    def ack_err(self):
        pass

    def ack_irq(self):
        pass

    def tick(self):
        pass
