import math
import random
import pygame
from config import *
from utils import *


class Bullet:
    def __init__(self, x, y, vx, vy, damage, color, owner, radius=4, kind='normal', life=3.0, target=None):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.color = color
        self.owner = owner
        self.radius = radius
        self.kind = kind
        self.life = life
        self.max_life = life
        self.target = target
        self.dead = False
        self.trail_timer = 0
        self.angle = math.atan2(vy, vx)

    def update(self, dt, particles=None, enemies=None, player=None):
        if self.kind == 'missile' and self.target is not None and not getattr(self.target, 'dead', True):
            desired_angle = angle_between(self.x, self.y, self.target.x, self.target.y)
            current_angle = math.atan2(self.vy, self.vx)
            diff = normalize_angle(desired_angle - current_angle)
            turn_speed = 4.5 * dt
            if abs(diff) < turn_speed:
                current_angle = desired_angle
            else:
                current_angle += math.copysign(turn_speed, diff)
            speed = math.sqrt(self.vx ** 2 + self.vy ** 2)
            self.vx = math.cos(current_angle) * speed
            self.vy = math.sin(current_angle) * speed
            self.angle = current_angle
        elif self.kind == 'missile':
            if enemies:
                best = None
                best_dist = 500
                for e in enemies:
                    if e.dead:
                        continue
                    d = distance(self.x, self.y, e.x, e.y)
                    if d < best_dist:
                        best_dist = d
                        best = e
                if best:
                    self.target = best

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

        if particles is not None:
            self.trail_timer += dt
            if self.trail_timer > 0.01:
                self.trail_timer = 0
                if self.kind == 'missile':
                    particles.spawn(self.x, self.y,
                                    -self.vx * 0.1 + random.uniform(-20, 20),
                                    -self.vy * 0.1 + random.uniform(-20, 20),
                                    0.4, 3, random.choice([ORANGE, YELLOW, WHITE]), friction=0.9)
                elif self.kind == 'plasma':
                    for _ in range(2):
                        particles.spawn(self.x + random.uniform(-3, 3),
                                        self.y + random.uniform(-3, 3),
                                        random.uniform(-30, 30), random.uniform(-30, 30),
                                        0.3, 2, self.color, friction=0.9)

        if (self.x < -50 or self.x > SCREEN_WIDTH + 50 or
                self.y < -50 or self.y > SCREEN_HEIGHT + 50 or
                self.life <= 0):
            self.dead = True

    def draw(self, surface):
        t = self.life / self.max_life
        if self.kind == 'plasma':
            r = int(self.radius * (1.0 + 0.3 * math.sin(pygame.time.get_ticks() * 0.01)))
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), r + 6)
            pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), r)
        elif self.kind == 'missile':
            angle = math.atan2(self.vy, self.vx)
            points = []
            for a, dist in [(0, self.radius * 3), (2.5, self.radius * 1.5),
                            (math.pi, self.radius * 1.5), (-2.5, self.radius * 1.5)]:
                px = self.x + math.cos(angle + a) * dist
                py = self.y + math.sin(angle + a) * dist
                points.append((int(px), int(py)))
            pygame.draw.polygon(surface, self.color, points)
            pygame.draw.polygon(surface, WHITE, points, 1)
        elif self.kind == 'enemy_big':
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius + 2)
            pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), self.radius)
        elif self.kind == 'laser':
            angle = math.atan2(self.vy, self.vx)
            length = self.radius * 4
            x2 = self.x - math.cos(angle) * length
            y2 = self.y - math.sin(angle) * length
            pygame.draw.line(surface, self.color, (int(x2), int(y2)),
                             (int(self.x), int(self.y)), self.radius + 2)
            pygame.draw.line(surface, WHITE, (int(x2), int(y2)),
                             (int(self.x), int(self.y)), max(1, self.radius - 1))
        else:
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
            pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), max(1, self.radius - 2))


class WeaponSystem:
    def __init__(self, owner='player'):
        self.owner = owner
        self.current_weapon = WEAPON_LASER
        self.levels = [1, 1, 1, 1]
        self.overheat = [0, 0, 0, 0]
        self.overheated = [False, False, False, False]
        self.fire_timer = 0
        self.plasma_charge = 0
        self.is_charging_plasma = False

    def switch_weapon(self, direction):
        self.current_weapon = (self.current_weapon + direction) % 4

    def set_weapon(self, idx):
        if 0 <= idx < 4:
            self.current_weapon = idx

    def switch_next(self):
        self.current_weapon = (self.current_weapon + 1) % 4

    def upgrade_weapon(self, idx):
        if 0 <= idx < 4 and self.levels[idx] < 3:
            self.levels[idx] += 1

    def get_level(self, idx=None):
        if idx is None:
            idx = self.current_weapon
        return self.levels[idx]

    def start_plasma_charge(self):
        if self.current_weapon == WEAPON_PLASMA and not self.overheated[WEAPON_PLASMA]:
            self.is_charging_plasma = True

    def get_heat_ratio(self, idx=None):
        if idx is None:
            idx = self.current_weapon
        return self.overheat[idx] / OVERHEAT_MAX

    def update(self, dt):
        for i in range(4):
            if self.overheated[i]:
                self.overheat[i] -= OVERHEAT_COOLDOWN * dt * 1.5
                if self.overheat[i] <= 0:
                    self.overheat[i] = 0
                    self.overheated[i] = False
            elif self.overheat[i] > 0:
                self.overheat[i] -= OVERHEAT_COOLDOWN * dt
                if self.overheat[i] < 0:
                    self.overheat[i] = 0
        if self.current_weapon == WEAPON_PLASMA:
            if self.is_charging_plasma and not self.overheated[WEAPON_PLASMA]:
                self.plasma_charge = min(1.0, self.plasma_charge + dt * 1.5)
                self.overheat[WEAPON_PLASMA] = min(OVERHEAT_MAX,
                                                    self.overheat[WEAPON_PLASMA] + dt * 18)
                if self.overheat[WEAPON_PLASMA] >= OVERHEAT_MAX:
                    self.overheat[WEAPON_PLASMA] = OVERHEAT_MAX
                    self.overheated[WEAPON_PLASMA] = True
                    self.is_charging_plasma = False
                    self.plasma_charge = 0
            elif not self.is_charging_plasma:
                self.plasma_charge = max(0, self.plasma_charge - dt * 2.5)
        else:
            self.plasma_charge = max(0, self.plasma_charge - dt * 2.5)
            self.is_charging_plasma = False
        self.fire_timer -= dt

    def start_charge(self):
        if self.current_weapon == WEAPON_PLASMA and not self.overheated[WEAPON_PLASMA]:
            self.is_charging_plasma = True

    def release_charge(self, x, y, bullets_list, enemies=None, is_wingman=False):
        fired = []
        if self.current_weapon == WEAPON_PLASMA:
            charge = self.plasma_charge
            self.is_charging_plasma = False
            if charge < 0.1:
                self.plasma_charge = 0
                return fired
            lvl = self.levels[WEAPON_PLASMA]
            base_dmg = 1 if is_wingman else 1
            self.fire_timer = 0.2 + charge * 0.4
            self._add_heat(8 + int(charge * 35), WEAPON_PLASMA)
            self.plasma_charge = 0
            speed = 520 + charge * 200
            dmg_mult = 0.5 + charge * 1.8
            dmg = int((30 + lvl * 22) * dmg_mult) * base_dmg
            radius = int(5 + lvl * 3 + charge * 16)
            count = 1
            if lvl >= 3:
                count = 3 if charge > 0.8 else (2 if charge > 0.5 else 1)
            elif lvl >= 2:
                count = 2 if charge > 0.7 else 1
            if count == 1:
                b = Bullet(x, y - 20, 0, -speed, dmg,
                           (255, 80 + int(charge * 175), 255), 'player',
                           radius=radius, kind='plasma', life=3.0)
                b.plasma_charge_level = charge
                bullets_list.append(b)
                fired.append(b)
            else:
                offsets = [-14, 0, 14] if count == 3 else [-10, 10]
                for ox in offsets:
                    b = Bullet(x + ox, y - 20, ox * 6, -speed, dmg,
                               (255, 80 + int(charge * 175), 255), 'player',
                               radius=radius, kind='plasma', life=3.0)
                    b.plasma_charge_level = charge
                    bullets_list.append(b)
                    fired.append(b)
        return fired

    def get_charge_ratio(self):
        if self.current_weapon == WEAPON_PLASMA:
            return self.plasma_charge
        return 0

    def _add_heat(self, amount, idx=None):
        if idx is None:
            idx = self.current_weapon
        self.overheat[idx] += amount
        if self.overheat[idx] >= OVERHEAT_MAX:
            self.overheat[idx] = OVERHEAT_MAX
            self.overheated[idx] = True

    def can_fire(self):
        if self.overheated[self.current_weapon]:
            return False
        if self.current_weapon == WEAPON_PLASMA:
            return self.plasma_charge >= 0.3 or self.fire_timer <= 0
        return self.fire_timer <= 0

    def fire(self, x, y, bullets_list, target_y=None, enemies=None, is_wingman=False):
        if not self.can_fire():
            return []
        fired = []
        w = self.current_weapon
        lvl = self.levels[w]
        base_dmg = 1 if is_wingman else 1

        if w == WEAPON_LASER:
            self.fire_timer = 0.10 - lvl * 0.02
            self._add_heat(5 + lvl * 2)
            speed = 900
            dmg = (10 + lvl * 5) * base_dmg
            count = lvl
            spacing = 18
            if count == 1:
                positions = [x]
            elif count == 2:
                positions = [x - spacing / 2, x + spacing / 2]
            else:
                positions = [x - spacing, x, x + spacing]
            for px in positions:
                b = Bullet(px, y - 15, 0, -speed, dmg, CYAN, 'player',
                           radius=3 + lvl, kind='laser', life=2.0)
                bullets_list.append(b)
                fired.append(b)

        elif w == WEAPON_SPREAD:
            self.fire_timer = 0.25 - lvl * 0.04
            self._add_heat(8 + lvl * 3)
            speed = 700
            dmg = (6 + lvl * 3) * base_dmg
            pellet_count = {1: 5, 2: 7, 3: 9}[lvl]
            spread_angle = {1: 0.6, 2: 0.7, 3: 0.8}[lvl]
            for i in range(pellet_count):
                t = 0 if pellet_count == 1 else i / (pellet_count - 1)
                angle = -math.pi / 2 + lerp(-spread_angle, spread_angle, t)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
                b = Bullet(x, y - 10, vx, vy, dmg, YELLOW, 'player',
                           radius=3, kind='normal', life=1.2)
                bullets_list.append(b)
                fired.append(b)

        elif w == WEAPON_MISSILE:
            self.fire_timer = {1: 0.55, 2: 0.40, 3: 0.30}[lvl]
            self._add_heat(12 + lvl * 4)
            dmg = (25 + lvl * 15) * base_dmg
            count = lvl
            positions = []
            if count == 1:
                positions = [(x, y)]
            elif count == 2:
                positions = [(x - 20, y - 5), (x + 20, y - 5)]
            else:
                positions = [(x - 25, y), (x, y - 15), (x + 25, y)]
            for px, py in positions:
                target = None
                if enemies:
                    best = None
                    best_dist = 600
                    for e in enemies:
                        if e.dead:
                            continue
                        d = distance(px, py, e.x, e.y)
                        if d < best_dist:
                            best_dist = d
                            best = e
                    target = best
                angle = -math.pi / 2 + random.uniform(-0.2, 0.2)
                speed = 350
                b = Bullet(px, py - 10,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           dmg, ORANGE, 'player',
                           radius=5, kind='missile', life=4.0, target=target)
                bullets_list.append(b)
                fired.append(b)

        elif w == WEAPON_PLASMA:
            charge = max(0.3, self.plasma_charge)
            self.fire_timer = 0.3
            self._add_heat(15 + int(charge * 20))
            self.plasma_charge = 0
            self.is_charging_plasma = False
            speed = 600
            dmg = int((30 + lvl * 20) * charge) * base_dmg
            radius = int(6 + lvl * 3 + charge * 10)
            count = lvl if lvl > 1 else 1
            if count == 1:
                b = Bullet(x, y - 20, 0, -speed, dmg, PURPLE, 'player',
                           radius=radius, kind='plasma', life=2.5)
                bullets_list.append(b)
                fired.append(b)
            else:
                for dx in [-12, 12] if count == 2 else [-20, 0, 20]:
                    b = Bullet(x + dx, y - 20, dx * 5, -speed, dmg, PURPLE, 'player',
                               radius=radius, kind='plasma', life=2.5)
                    bullets_list.append(b)
                    fired.append(b)

        return fired
