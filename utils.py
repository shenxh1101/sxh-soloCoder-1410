import math
import random
import pygame
from config import *


def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def lerp(a, b, t):
    return a + (b - a) * t


def distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def angle_between(x1, y1, x2, y2):
    return math.atan2(y2 - y1, x2 - x1)


def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def random_range(min_val, max_val):
    return random.uniform(min_val, max_val)


def random_color():
    return random.choice(COLORS)


def rect_collide(r1, r2):
    return (r1[0] < r2[0] + r2[2] and
            r1[0] + r1[2] > r2[0] and
            r1[1] < r2[1] + r2[3] and
            r1[1] + r1[3] > r2[1])


def circle_rect_collide(cx, cy, cr, rx, ry, rw, rh):
    closest_x = clamp(cx, rx, rx + rw)
    closest_y = clamp(cy, ry, ry + rh)
    return distance(cx, cy, closest_x, closest_y) < cr


def circle_collide(x1, y1, r1, x2, y2, r2):
    return distance(x1, y1, x2, y2) < r1 + r2


def draw_text(surface, text, x, y, size=20, color=WHITE, font_name=None, center=False):
    if font_name is None:
        font = pygame.font.SysFont("couriernew, consolas, monospace", size, bold=True)
    else:
        font = pygame.font.Font(font_name, size)
    text_surface = font.render(text, True, color)
    if center:
        rect = text_surface.get_rect(center=(x, y))
        surface.blit(text_surface, rect)
    else:
        surface.blit(text_surface, (x, y))
    return text_surface.get_size()


def draw_text_outline(surface, text, x, y, size=20, color=WHITE, outline_color=BLACK, font_name=None, center=False):
    if font_name is None:
        font = pygame.font.SysFont("couriernew, consolas, monospace", size, bold=True)
    else:
        font = pygame.font.Font(font_name, size)
    outline = font.render(text, True, outline_color)
    text_surface = font.render(text, True, color)
    if center:
        rect = text_surface.get_rect(center=(x, y))
        ox, oy = rect.topleft
    else:
        ox, oy = x, y
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            if dx != 0 or dy != 0:
                surface.blit(outline, (ox + dx, oy + dy))
    surface.blit(text_surface, (ox, oy))
    return text_surface.get_size()


class Timer:
    def __init__(self):
        self.events = {}

    def add(self, name, duration):
        self.events[name] = pygame.time.get_ticks() + duration

    def check(self, name):
        if name not in self.events:
            return True
        return pygame.time.get_ticks() >= self.events[name]

    def remaining(self, name):
        if name not in self.events:
            return 0
        return max(0, self.events[name] - pygame.time.get_ticks())

    def clear(self, name):
        if name in self.events:
            del self.events[name]
