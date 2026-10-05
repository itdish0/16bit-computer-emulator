
import numpy as np


class Window:
    def __init__(self, width, height):
        self._screen = np.zeros(width*height, dtype=np.uint16)
        self._buffer = np.zeros(width*height, dtype=np.uint16)
        self._screen_view_8 = self._screen.view(dtype=np.uint8)
        self._buffer_view_8 = self._buffer.view(dtype=np.uint8)
        self._screen_view_2d = self._screen.reshape((width, height))
        self._buffer_view_2d = self._buffer.reshape((width, height))
        self.bit_mode = 8
        self.palette_16 = np.zeros(256, dtype=np.uint16)
        self.palette_24 = np.zeros((256, 3), dtype=np.uint8)

        self._width = width
        self._height = height

        self.blit_w = 0
        self.blit_h = 0
        self.blit_x = 0
        self.blit_y = 0
        self.blit_addr = 0x0000
        self.palette_idx = 0x00
        self.color = 0x0000
        self.transparent_color = 0x0000

        self._blit_w_left = 0
        self._blit_h_left = 0
        self._curr_blit_w = 0
        self._curr_blit_x = 0
        self._curr_blit_y = 0
        self._curr_blit_addr = 0x0000
        self._curr_palette_idx = 0x00
        self._curr_color = 0x0000
        self._curr_transparent_color = 0x0000

        self.active = False
        self.dirty = False


    def set_palette_single(self, idx, c):
        self.palette_16[idx] = c

        r = (c & 0xF800) >> 11
        g = (c & 0x07E0) >> 5
        b = (c & 0x001F)

        self.palette_24[idx] = (
            (r * 255) // 31,
            (g * 255) // 63,
            (b * 255) // 31
        )

    def get_palette_single(self, idx):
        return self.palette_16[idx]

    def set_pixel_buffer(self):
        self._buffer_view_2d[self.blit_x, self.blit_y] = self.color

    def get_pixel_buffer(self):
        return self._buffer_view_2d[self.blit_x, self.blit_y]

    def get_pixel_screen(self):
        return self._screen_view_2d[self.blit_x, self.blit_y]

    def get_drawable(self):
        return self.palette_24[self._screen_view_2d]

    def blit_done(self):
        return self._blit_h_left == 0

    def start_blit(self, mode):
        self._blit_w_left = self.blit_w
        self._blit_h_left = self.blit_h
        self._curr_blit_w = self.blit_w
        self._curr_blit_x = self.blit_x
        self._curr_blit_y = self.blit_y
        self._curr_color = self.color
        self._curr_transparent_color = self.transparent_color
        self._curr_blit_addr = self.blit_addr
        self.mode = mode
        self.active = True

    def blit_buffer_write(self, b):
        match self.bit_mode:
            case 1:
                return
            case 2:
                return
            case 4:
                return
            case 8:
                if (self._curr_blit_x < self._width
                        and self._curr_blit_y < self._height
                        and b != self._curr_transparent_color & 0xFF):
                    self._buffer_view_2d[self._curr_blit_x, self._curr_blit_y] = b
                self._curr_blit_x += 1
                self._blit_w_left -= 1
                if self._blit_w_left == 0:
                    self._curr_blit_x -= self._curr_blit_w
                    self._blit_w_left = self._curr_blit_w
                    self._curr_blit_y += 1
                    self._blit_h_left -= 1

            case 16:
                return

    def blit_buffer_read(self):
        match self.bit_mode:
            case 1:
                return 0
            case 2:
                return 0
            case 4:
                return 0
            case 8:
                if self._curr_blit_x < self._width and self._curr_blit_y < self._height:
                    b = self._buffer_view_2d[self._curr_blit_x, self._curr_blit_y]
                self._curr_blit_x += 1
                self._blit_w_left -= 1
                if self._blit_w_left == 0:
                    self._curr_blit_x -= self._curr_blit_w
                    self._blit_w_left = self._curr_blit_w
                    self._curr_blit_y += 1
                    self._blit_h_left -= 1
                return b
            case 16:
                return 0

    def blit_buffer_read(self):
        match self.bit_mode:
            case 1:
                return 0
            case 2:
                return 0
            case 4:
                return 0
            case 8:
                if self._curr_blit_x < self._width and self._curr_blit_y < self._height:
                    b = self._screen_view_2d[self._curr_blit_x, self._curr_blit_y]
                self._curr_blit_x += 1
                self._blit_w_left -= 1
                if self._blit_w_left == 0:
                    self._curr_blit_x -= self._curr_blit_w
                    self._blit_w_left = self._curr_blit_w
                    self._curr_blit_y += 1
                    self._blit_h_left -= 1
                return b
            case 16:
                return 0

    def clear_buffer(self, color):
        self._buffer.fill(color)

    def show_buffer(self):
        np.copyto(self._screen, self._buffer)