import pygame
from config import *


class InputManager:
    def __init__(self):
        self.keys = set()
        self.keys_pressed = set()
        self.keys_released = set()
        self.mouse_pos = (0, 0)
        self.mouse_buttons = [False, False, False]
        self.mouse_pressed = [False, False, False]
        self.joysticks = []
        self.joy_buttons = {}
        self.joy_axes = {}
        self._init_joysticks()

    def _init_joysticks(self):
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            self.joysticks.append(joy)
            self.joy_buttons[i] = set()
            self.joy_axes[i] = [0.0] * joy.get_numaxes()

    def update_begin(self):
        self.keys_pressed.clear()
        self.keys_released.clear()
        for i in range(3):
            self.mouse_pressed[i] = False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key not in self.keys:
                self.keys_pressed.add(event.key)
            self.keys.add(event.key)
        elif event.type == pygame.KEYUP:
            if event.key in self.keys:
                self.keys_released.add(event.key)
            self.keys.discard(event.key)
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN:
            btn = event.button - 1
            if 0 <= btn < 3:
                self.mouse_pressed[btn] = True
                self.mouse_buttons[btn] = True
        elif event.type == pygame.MOUSEBUTTONUP:
            btn = event.button - 1
            if 0 <= btn < 3:
                self.mouse_buttons[btn] = False
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.joy in self.joy_buttons:
                self.joy_buttons[event.joy].add(event.button)
        elif event.type == pygame.JOYBUTTONUP:
            if event.joy in self.joy_buttons:
                self.joy_buttons[event.joy].discard(event.button)
        elif event.type == pygame.JOYAXISMOTION:
            if event.joy in self.joy_axes and event.axis < len(self.joy_axes[event.joy]):
                self.joy_axes[event.joy][event.axis] = event.value
        elif event.type == pygame.JOYDEVICEADDED:
            if event.device_index < pygame.joystick.get_count():
                joy = pygame.joystick.Joystick(event.device_index)
                joy.init()
                self.joysticks.append(joy)
                self.joy_buttons[event.device_index] = set()
                self.joy_axes[event.device_index] = [0.0] * joy.get_numaxes()

    def is_key(self, key):
        return key in self.keys

    def is_key_down(self, key):
        return key in self.keys_pressed

    def is_key_up(self, key):
        return key in self.keys_released

    def get_mouse_pos(self):
        return self.mouse_pos

    def is_mouse(self, button):
        if 0 <= button < 3:
            return self.mouse_buttons[button]
        return False

    def is_mouse_down(self, button):
        if 0 <= button < 3:
            return self.mouse_pressed[button]
        return False

    def get_joy_axis(self, joy_idx, axis):
        if joy_idx in self.joy_axes and axis < len(self.joy_axes[joy_idx]):
            val = self.joy_axes[joy_idx][axis]
            return val if abs(val) > 0.15 else 0.0
        return 0.0

    def is_joy_button(self, joy_idx, button):
        if joy_idx in self.joy_buttons:
            return button in self.joy_buttons[joy_idx]
        return False

    def get_player_movement(self, player_idx=0):
        dx, dy = 0.0, 0.0
        if player_idx == 0:
            if self.is_key(pygame.K_LEFT) or self.is_key(pygame.K_a):
                dx -= 1.0
            if self.is_key(pygame.K_RIGHT) or self.is_key(pygame.K_d):
                dx += 1.0
            if self.is_key(pygame.K_UP) or self.is_key(pygame.K_w):
                dy -= 1.0
            if self.is_key(pygame.K_DOWN) or self.is_key(pygame.K_s):
                dy += 1.0
            if self.joysticks:
                dx += self.get_joy_axis(0, 0)
                dy += self.get_joy_axis(0, 1)
        else:
            if self.is_key(pygame.K_j):
                dx -= 1.0
            if self.is_key(pygame.K_l):
                dx += 1.0
            if self.is_key(pygame.K_i):
                dy -= 1.0
            if self.is_key(pygame.K_k):
                dy += 1.0
            if len(self.joysticks) > 1:
                dx += self.get_joy_axis(1, 0)
                dy += self.get_joy_axis(1, 1)
            elif self.joysticks and player_idx == 1:
                dx += self.get_joy_axis(0, 2) if len(self.joy_axes[0]) > 2 else 0
                dy += self.get_joy_axis(0, 3) if len(self.joy_axes[0]) > 3 else 0
        length = math.sqrt(dx * dx + dy * dy)
        if length > 1.0:
            dx /= length
            dy /= length
        return dx, dy

    def is_shooting(self, player_idx=0):
        if player_idx == 0:
            result = self.is_key(pygame.K_SPACE) or self.is_mouse(0)
            if self.joysticks:
                result = result or self.is_joy_button(0, 0) or self.is_joy_button(0, 7)
            return result
        else:
            result = self.is_key(pygame.K_RCTRL) or self.is_key(pygame.K_RETURN)
            if len(self.joysticks) > 1:
                result = result or self.is_joy_button(1, 0)
            elif self.joysticks and player_idx == 1:
                result = result or self.is_joy_button(0, 2)
            return result

    def switch_weapon(self, player_idx=0):
        if player_idx == 0:
            if self.is_key_down(pygame.K_q) or self.is_key_down(pygame.K_e):
                return -1 if self.is_key_down(pygame.K_q) else 1
            if self.joysticks:
                if self.is_joy_button(0, 4):
                    return -1
                if self.is_joy_button(0, 5):
                    return 1
        else:
            if self.is_key_down(pygame.K_u) or self.is_key_down(pygame.K_o):
                return -1 if self.is_key_down(pygame.K_u) else 1
        return 0

    def is_pause(self):
        return self.is_key_down(pygame.K_ESCAPE) or self.is_key_down(pygame.K_p)

    def is_any_key(self):
        return len(self.keys_pressed) > 0 or any(self.mouse_pressed)


import math
