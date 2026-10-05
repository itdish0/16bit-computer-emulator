
import pygame
import numpy as np

from pygame.locals import (
    KEYDOWN, KEYUP, MOUSEMOTION, MOUSEBUTTONDOWN, MOUSEBUTTONUP, QUIT,
    K_UP, K_DOWN, K_LEFT, K_RIGHT, K_LSHIFT, K_RSHIFT, K_LCTRL, K_LALT,
    K_RETURN
)

class ScreenInterface:
    def __init__(self, scale_factor=4, title="Screen"):
        pygame.init()
        self.master_surface = pygame.display.set_mode(
            (256*scale_factor, 192*scale_factor)
        )
        self.internal_surface = pygame.Surface((256, 192))
        pygame.display.set_caption(title)

        self.input_port = None
        self.screen_port = None

    def draw_array(self, array, x, y):
        raw_surface = pygame.surfarray.make_surface(array)
        self.internal_surface.blit(raw_surface, (x, y))

    def update(self):
        scaled_frame = pygame.transform.scale(
            self.internal_surface, self.master_surface.get_size()
        )

        self.master_surface.blit(scaled_frame, (0, 0))
        pygame.display.flip()

    def clear(self, color=(0, 0, 0)):
        self.internal_surface.fill(color)

    KEY_MAP = {
        K_UP: 0x01,
        K_DOWN: 0x02,
        K_LEFT: 0x03,
        K_RIGHT: 0x04,
        K_LSHIFT: 0x05,
        K_RSHIFT: 0x06,
        K_LCTRL: 0x07,
        K_LALT: 0x10,
        K_RETURN: 0x0A
    }

    def pump_events(self):
        """
        Drains the host OS event queue and routes data to virtual hardware.
        Returns False if the host OS requested a window close.
        """
        for event in pygame.event.get():
            if event.type == QUIT:
                return False

            elif event.type in (KEYDOWN, KEYUP):
                self._route_keyboard(event)

            elif event.type == MOUSEMOTION:
                self.input_port.update_axes(event.rel[0], event.rel[1])

            elif event.type in (MOUSEBUTTONDOWN, MOUSEBUTTONUP):
                self.input_port.update_buttons(pygame.mouse.get_pressed())

        self.screen_port.vblank()

        return True

    def _route_keyboard(self, event):
        key_id = 0
        if event.key in self.KEY_MAP:
            key_id = self.KEY_MAP[event.key]
        elif event.key < 128:
            key_id = event.key
        else:
            return

        if event.type == pygame.KEYUP:
            key_id |= 0x80

        self.input_port.push_byte(key_id)

    def shutdown(self):
        pygame.quit()
