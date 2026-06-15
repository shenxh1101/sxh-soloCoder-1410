import math
import random
import pygame
from config import *
from utils import *


class ParticlePool:
    def __init__(self, max_size=MAX_PARTICLES):
        self.max_size = max_size
        self.x = [0.0] * max_size
        self.y = [0.0] * max_size
        self.vx = [0.0] * max_size
        self.vy = [0.0] * max_size
        self.life = [0.0] * max_size
        self.max_life = [0.0] * max_size
        self.size = [0.0] * max_size
        self.color = [(0, 0, 0)] * max_size
        self.gravity = [0.0] * max_size
        self.friction = [0.0] * max_size
        self.active = [False] * max_size
        self.shrink = [True] * max_size
        self.count = 0

    def spawn(self, x, y, vx, vy, life, size, color, gravity=0, friction=1.0, shrink=True):
        if self.count >= self.max_size:
            return
        for i in range(self.max_size):
            if not self.active[i]:
                self.x[i] = x
                self.y[i] = y
                self.vx[i] = vx
                self.vy[i] = vy
                self.life[i] = life
                self.max_life[i] = life
                self.size[i] = size
                self.color[i] = color
                self.gravity[i] = gravity
                self.friction[i] = friction
                self.shrink[i] = shrink
                self.active[i] = True
                self.count += 1
                return

    def emit(self, x, y, count, speed, life, size, colors, gravity=0, friction=1.0, spread=math.pi * 2, angle=0, shrink=True):
        for _ in range(count):
            a = angle + random.uniform(-spread / 2, spread / 2)
            s = random.uniform(speed * 0.5, speed)
            vx = math.cos(a) * s
            vy = math.sin(a) * s
            c = random.choice(colors) if isinstance(colors, list) else colors
            self.spawn(x, y, vx, vy, life * random.uniform(0.7, 1.3), size * random.uniform(0.7, 1.3), c, gravity, friction, shrink)

    def explosion(self, x, y, count=50, size=4, colors=None):
        if colors is None:
            colors = [ORANGE, YELLOW, RED, WHITE]
        self.emit(x, y, count, 400, 0.8, size, colors, friction=0.95, spread=math.pi * 2)
        self.emit(x, y, count // 2, 200, 1.2, size * 2, [DARK_GRAY, GRAY], friction=0.9, spread=math.pi * 2)

    def big_explosion(self, x, y):
        for _ in range(8):
            offset_x = random.uniform(-40, 40)
            offset_y = random.uniform(-40, 40)
            self.explosion(x + offset_x, y + offset_y, count=80, size=6)

    def thrust(self, x, y, angle):
        self.spawn(x + math.cos(angle) * 5, y + math.sin(angle) * 5,
                   math.cos(angle) * -150 + random.uniform(-30, 30),
                   math.sin(angle) * -150 + random.uniform(-30, 30),
                   0.3, random.uniform(2, 4), random.choice([CYAN, BLUE, WHITE]), friction=0.9)

    def hit(self, x, y, color=WHITE):
        self.emit(x, y, 8, 250, 0.4, 3, [color, WHITE], friction=0.9)

    def trail(self, x, y, color):
        self.spawn(x, y, random.uniform(-20, 20), random.uniform(-20, 20),
                   0.5, 2, color, friction=0.92)

    def update(self, dt):
        for i in range(self.max_size):
            if self.active[i]:
                self.vx[i] *= self.friction[i]
                self.vy[i] *= self.friction[i]
                self.vy[i] += self.gravity[i] * dt
                self.x[i] += self.vx[i] * dt
                self.y[i] += self.vy[i] * dt
                self.life[i] -= dt
                if self.life[i] <= 0:
                    self.active[i] = False
                    self.count -= 1

    def draw(self, surface):
        for i in range(self.max_size):
            if self.active[i]:
                t = self.life[i] / self.max_life[i]
                if self.shrink[i]:
                    s = int(self.size[i] * t)
                else:
                    s = int(self.size[i])
                if s < 1:
                    s = 1
                c = self.color[i]
                if t < 0.3:
                    c = (int(c[0] * t * 3), int(c[1] * t * 3), int(c[2] * t * 3))
                pygame.draw.circle(surface, c, (int(self.x[i]), int(self.y[i])), s)

    def clear(self):
        for i in range(self.max_size):
            self.active[i] = False
        self.count = 0


class StarField:
    def __init__(self, layers=3, count_per_layer=150):
        self.layers = []
        colors = [DARK_GRAY, GRAY, WHITE]
        speeds = [40, 100, 200]
        sizes = [1, 1, 2]
        for l in range(layers):
            stars = []
            for _ in range(count_per_layer):
                stars.append({
                    'x': random.uniform(0, SCREEN_WIDTH),
                    'y': random.uniform(0, SCREEN_HEIGHT),
                    'size': sizes[l],
                    'color': colors[l],
                    'speed': speeds[l]
                })
            self.layers.append(stars)

    def update(self, dt, speed_multiplier=1.0):
        for layer in self.layers:
            for star in layer:
                star['y'] += star['speed'] * dt * speed_multiplier
                if star['y'] > SCREEN_HEIGHT:
                    star['y'] = -5
                    star['x'] = random.uniform(0, SCREEN_WIDTH)

    def draw(self, surface):
        for layer in self.layers:
            for star in layer:
                pygame.draw.rect(surface, star['color'],
                                 (int(star['x']), int(star['y']),
                                  star['size'], star['size']))

    def draw_lines(self, surface, warp_mode=False):
        for layer in self.layers:
            for star in layer:
                if warp_mode:
                    length = 15 * layer.index(layer) + 10
                    pygame.draw.line(surface, layer[0]['color'],
                                     (int(star['x']), int(star['y'])),
                                     (int(star['x']), int(star['y']) - length))
                else:
                    pygame.draw.rect(surface, star['color'],
                                     (int(star['x']), int(star['y']),
                                      star['size'], star['size']))
