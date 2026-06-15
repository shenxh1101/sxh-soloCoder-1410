import math
import random
import pygame
from config import *
from utils import *
from bullets import Bullet

ENEMY_DRONE = 0
ENEMY_KAMIKAZE = 1
ENEMY_HEAVY = 2
ENEMY_SHIELDED = 3
ENEMY_STEALTH = 4
ENEMY_TURRET = 5
ENEMY_INTERCEPTOR = 6
ENEMY_MOTHERSHIP = 7

ENEMY_COUNT = 8


class Enemy:
    def __init__(self, kind, x, y, difficulty=1.0):
        self.kind = kind
        self.x = x
        self.y = y
        self.dead = False
        self.vx = 0
        self.vy = 0
        self.angle = math.pi / 2
        self.fire_timer = random.uniform(0.5, 2.0)
        self.phase_timer = 0
        self.anim_timer = 0
        self.difficulty = difficulty
        self.shield_hp = 0
        self.max_shield = 0
        self.stealth_alpha = 255
        self.stealth_timer = random.uniform(2, 5)
        self.revealed = False
        self.attack_pattern = 0
        self.target_y = random.uniform(100, SCREEN_HEIGHT * 0.5)
        self.entering = True
        self.spawn_shield = False
        self.turret_angle = 0
        self.score_value = 100
        self.damage = 20
        self.contact_damage = 30
        self._configure()

    def _configure(self):
        d = self.difficulty
        if self.kind == ENEMY_DRONE:
            self.radius = 14
            self.hp = int(25 * d)
            self.max_hp = self.hp
            self.color = RED
            self.score_value = int(100 * d)
            self.damage = 8
            self.contact_damage = 20
            self.speed = 120 + d * 30
            self.fire_rate = 1.5 - min(0.8, d * 0.15)
        elif self.kind == ENEMY_KAMIKAZE:
            self.radius = 12
            self.hp = int(15 * d)
            self.max_hp = self.hp
            self.color = ORANGE
            self.score_value = int(150 * d)
            self.damage = 0
            self.contact_damage = 50
            self.speed = 200 + d * 50
            self.fire_rate = 999
        elif self.kind == ENEMY_HEAVY:
            self.radius = 24
            self.hp = int(100 * d)
            self.max_hp = self.hp
            self.color = DARK_RED
            self.score_value = int(300 * d)
            self.damage = 15
            self.contact_damage = 40
            self.speed = 60 + d * 15
            self.fire_rate = 1.2 - min(0.6, d * 0.1)
        elif self.kind == ENEMY_SHIELDED:
            self.radius = 22
            self.hp = int(60 * d)
            self.max_hp = self.hp
            self.max_shield = int(80 * d)
            self.shield_hp = self.max_shield
            self.color = BLUE
            self.score_value = int(350 * d)
            self.damage = 12
            self.contact_damage = 35
            self.speed = 80 + d * 20
            self.fire_rate = 1.8 - min(0.8, d * 0.15)
            self.spawn_shield = True
        elif self.kind == ENEMY_STEALTH:
            self.radius = 16
            self.hp = int(40 * d)
            self.max_hp = self.hp
            self.color = PURPLE
            self.score_value = int(400 * d)
            self.damage = 18
            self.contact_damage = 30
            self.speed = 150 + d * 30
            self.fire_rate = 1.0 - min(0.4, d * 0.1)
            self.stealth_alpha = 60
        elif self.kind == ENEMY_TURRET:
            self.radius = 26
            self.hp = int(150 * d)
            self.max_hp = self.hp
            self.color = GRAY
            self.score_value = int(450 * d)
            self.damage = 20
            self.contact_damage = 45
            self.speed = 40
            self.fire_rate = 0.8 - min(0.3, d * 0.08)
        elif self.kind == ENEMY_INTERCEPTOR:
            self.radius = 18
            self.hp = int(50 * d)
            self.max_hp = self.hp
            self.color = CYAN
            self.score_value = int(250 * d)
            self.damage = 10
            self.contact_damage = 35
            self.speed = 180 + d * 40
            self.fire_rate = 1.0 - min(0.5, d * 0.1)
        elif self.kind == ENEMY_MOTHERSHIP:
            self.radius = 45
            self.hp = int(500 * d)
            self.max_hp = self.hp
            self.color = DARK_GRAY
            self.score_value = int(2000 * d)
            self.damage = 12
            self.contact_damage = 60
            self.speed = 30 + d * 10
            self.fire_rate = 0.5 - min(0.2, d * 0.05)
            self.target_y = 120

    def take_damage(self, amount):
        if self.kind == ENEMY_STEALTH and self.stealth_alpha < 100:
            amount = int(amount * 0.3)
            self.revealed = True
            self.stealth_timer = 3.0
        if self.shield_hp > 0:
            absorbed = min(self.shield_hp, amount)
            self.shield_hp -= absorbed
            amount -= absorbed
            if amount <= 0:
                return 0, True
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            return self.score_value, True
        return 0, True

    def update(self, dt, bullets_list, player, wingman=None, particles=None):
        if self.dead:
            return
        self.anim_timer += dt
        self.phase_timer += dt
        self.fire_timer -= dt

        if self.kind == ENEMY_STEALTH:
            self.stealth_timer -= dt
            if self.revealed:
                self.stealth_alpha = min(255, self.stealth_alpha + 500 * dt)
                if self.stealth_timer <= 0:
                    self.revealed = False
            else:
                self.stealth_alpha = max(40, self.stealth_alpha - 300 * dt)

        targets = []
        if player and not player.dead:
            targets.append(player)
        if wingman and not wingman.dead:
            targets.append(wingman)
        target = targets[0] if targets else None
        for t in targets[1:]:
            if distance(self.x, self.y, t.x, t.y) < distance(self.x, self.y, target.x, target.y):
                target = t

        if self.kind == ENEMY_DRONE:
            self._update_drone(dt, target)
        elif self.kind == ENEMY_KAMIKAZE:
            self._update_kamikaze(dt, target, particles)
        elif self.kind == ENEMY_HEAVY:
            self._update_heavy(dt, target)
        elif self.kind == ENEMY_SHIELDED:
            self._update_shielded(dt, target)
        elif self.kind == ENEMY_STEALTH:
            self._update_stealth(dt, target)
        elif self.kind == ENEMY_TURRET:
            self._update_turret(dt, target)
        elif self.kind == ENEMY_INTERCEPTOR:
            self._update_interceptor(dt, target)
        elif self.kind == ENEMY_MOTHERSHIP:
            self._update_mothership(dt, targets)

        if self.fire_timer <= 0 and self.damage > 0:
            self._fire(bullets_list, target, targets)
            self.fire_timer = self.fire_rate * random.uniform(0.8, 1.2)

        self.x += self.vx * dt
        self.y += self.vy * dt

        if self.y > SCREEN_HEIGHT + 80 or self.x < -100 or self.x > SCREEN_WIDTH + 100:
            if not self.entering or self.y > SCREEN_HEIGHT + 200:
                self.dead = True

    def _update_drone(self, dt, target):
        if self.entering:
            self.vy = self.speed
            self.vx = math.sin(self.anim_timer * 3) * 80
            if self.y >= self.target_y:
                self.entering = False
        else:
            self.vy = 20 + math.sin(self.anim_timer * 2) * 15
            self.vx = math.sin(self.anim_timer * 1.5 + self.x * 0.01) * 120
            if target:
                dx = target.x - self.x
                self.vx += clamp(dx, -30, 30) * dt * 5
                self.vx = clamp(self.vx, -200, 200)

    def _update_kamikaze(self, dt, target, particles):
        if target:
            angle = angle_between(self.x, self.y, target.x, target.y)
            desired_vx = math.cos(angle) * self.speed * 1.3
            desired_vy = math.sin(angle) * self.speed * 1.3
            self.vx = lerp(self.vx, desired_vx, 2.5 * dt)
            self.vy = lerp(self.vy, desired_vy, 2.5 * dt)
            if particles and self.anim_timer % 0.05 < dt:
                particles.spawn(self.x, self.y,
                                -self.vx * 0.1 + random.uniform(-20, 20),
                                -self.vy * 0.1 + random.uniform(-20, 20),
                                0.3, 3, random.choice([ORANGE, YELLOW, RED]),
                                friction=0.9)
        else:
            self.vy = self.speed

    def _update_heavy(self, dt, target):
        if self.entering:
            self.vy = self.speed
            if self.y >= self.target_y:
                self.entering = False
        else:
            self.vy = 10 + math.sin(self.anim_timer) * 10
            if target:
                dx = target.x - self.x
                self.vx = clamp(dx * 0.8, -80, 80)
            else:
                self.vx = 0

    def _update_shielded(self, dt, target):
        if self.entering:
            self.vy = self.speed
            if self.y >= self.target_y:
                self.entering = False
        else:
            self.vy = math.sin(self.anim_timer * 0.8) * 25
            if target:
                dx = target.x - self.x
                self.vx = clamp(dx * 0.5, -100, 100)
            else:
                self.vx = 0

    def _update_stealth(self, dt, target):
        if self.entering:
            self.vy = self.speed * 0.8
            if self.y >= self.target_y:
                self.entering = False
        else:
            self.vy = math.sin(self.anim_timer * 2.5) * 50
            if target:
                dx = target.x - self.x
                self.vx = clamp(dx * 1.2, -200, 200)
            else:
                self.vx = 0

    def _update_turret(self, dt, target):
        if self.entering:
            self.vy = self.speed
            if self.y >= self.target_y:
                self.entering = False
                self.vy = 0
        else:
            self.vy = 0
            self.vx = math.sin(self.anim_timer * 0.5) * 40
            if target:
                self.turret_angle = angle_between(self.x, self.y, target.x, target.y)

    def _update_interceptor(self, dt, target):
        if self.entering:
            self.vy = self.speed
            if self.y >= self.target_y:
                self.entering = False
                self.attack_pattern = random.randint(0, 2)
        else:
            if self.attack_pattern == 0:
                self.vy = -self.speed * 0.4 if self.y < 250 else self.speed * 0.4
                self.vx = 0
            elif self.attack_pattern == 1:
                angle = angle_between(self.x, self.y, target.x, target.y) if target else math.pi / 2
                self.vx = math.cos(angle) * self.speed * 0.7
                self.vy = math.sin(angle) * self.speed * 0.7
            else:
                self.vy = self.speed * 0.3
                self.vx = math.sin(self.anim_timer * 4) * self.speed

    def _update_mothership(self, dt, targets):
        if self.entering:
            self.vy = self.speed
            if self.y >= self.target_y:
                self.entering = False
                self.vy = 0
        else:
            self.vy = math.sin(self.anim_timer * 0.3) * 15
            self.vx = math.sin(self.anim_timer * 0.5) * 60

    def _fire(self, bullets_list, target, all_targets):
        if self.kind in [ENEMY_DRONE, ENEMY_HEAVY, ENEMY_SHIELDED, ENEMY_STEALTH]:
            if target:
                angle = angle_between(self.x, self.y, target.x, target.y)
                speed = 350 + self.difficulty * 30
                b = Bullet(self.x, self.y + self.radius,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           self.damage, RED, 'enemy',
                           radius=4, kind='normal', life=4.0)
                bullets_list.append(b)
        elif self.kind == ENEMY_HEAVY:
            for da in [-0.15, 0, 0.15]:
                if target:
                    angle = angle_between(self.x, self.y, target.x, target.y) + da
                    speed = 300
                    b = Bullet(self.x, self.y + self.radius,
                               math.cos(angle) * speed,
                               math.sin(angle) * speed,
                               self.damage, RED, 'enemy',
                               radius=5, kind='normal', life=4.0)
                    bullets_list.append(b)
        elif self.kind == ENEMY_SHIELDED:
            for i in range(3):
                angle = angle_between(self.x, self.y, target.x, target.y) if target else math.pi / 2
                angle += (i - 1) * 0.3
                speed = 280
                b = Bullet(self.x, self.y + self.radius,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           self.damage, BLUE, 'enemy',
                           radius=4, kind='normal', life=4.0)
                bullets_list.append(b)
        elif self.kind == ENEMY_STEALTH:
            if target:
                angle = angle_between(self.x, self.y, target.x, target.y)
                speed = 420
                b = Bullet(self.x, self.y,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           self.damage, PURPLE, 'enemy',
                           radius=3, kind='normal', life=3.0)
                bullets_list.append(b)
        elif self.kind == ENEMY_TURRET:
            for i in range(4):
                angle = self.turret_angle + (i - 1.5) * 0.1
                speed = 320
                b = Bullet(self.x, self.y,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           self.damage, GRAY, 'enemy',
                           radius=5, kind='enemy_big', life=5.0)
                bullets_list.append(b)
        elif self.kind == ENEMY_INTERCEPTOR:
            if target:
                angle = angle_between(self.x, self.y, target.x, target.y)
                speed = 380
                for i in range(2):
                    offset = 12 if i == 0 else -12
                    b = Bullet(self.x + offset, self.y,
                               math.cos(angle) * speed,
                               math.sin(angle) * speed,
                               self.damage, CYAN, 'enemy',
                               radius=3, kind='normal', life=3.5)
                    bullets_list.append(b)
        elif self.kind == ENEMY_MOTHERSHIP:
            for i in range(6):
                angle = math.pi / 2 + (i - 2.5) * 0.25
                speed = 280
                b = Bullet(self.x, self.y + self.radius * 0.7,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           self.damage, RED, 'enemy',
                           radius=6, kind='enemy_big', life=5.0)
                bullets_list.append(b)
            if self.phase_timer > 3 and all_targets:
                self.phase_timer = 0
                for t in all_targets:
                    if t and not t.dead:
                        angle = angle_between(self.x, self.y, t.x, t.y)
                        b = Bullet(self.x, self.y,
                                   math.cos(angle) * 200,
                                   math.sin(angle) * 200,
                                   self.damage * 2, DARK_RED, 'enemy',
                                   radius=8, kind='missile', life=5.0, target=t)
                        bullets_list.append(b)

    def draw(self, surface):
        if self.dead:
            return
        x, y = int(self.x), int(self.y)

        if self.kind == ENEMY_STEALTH:
            temp_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            alpha = int(self.stealth_alpha)
            self._draw_body(temp_surface, x, y, alpha)
            surface.blit(temp_surface, (0, 0))
        else:
            self._draw_body(surface, x, y, 255)

        if self.shield_hp > 0:
            self._draw_shield(surface, x, y)

        if self.hp < self.max_hp and self.kind != ENEMY_STEALTH:
            self._draw_hp_bar(surface)

    def _draw_body(self, surface, x, y, alpha):
        r = self.radius
        if self.kind == ENEMY_DRONE:
            c = self._alpha_color(RED, alpha)
            c2 = self._alpha_color(DARK_RED, alpha)
            pts = [(x, y + r), (x - r * 0.8, y - r * 0.2),
                   (x - r * 0.4, y - r), (x + r * 0.4, y - r),
                   (x + r * 0.8, y - r * 0.2)]
            pygame.draw.polygon(surface, c2, pts)
            pygame.draw.polygon(surface, c, pts, 2)
            pygame.draw.circle(surface, self._alpha_color(YELLOW, alpha),
                               (x, y - r * 0.2), int(r * 0.3))
        elif self.kind == ENEMY_KAMIKAZE:
            c = self._alpha_color(ORANGE, alpha)
            glow = 1 + 0.3 * math.sin(self.anim_timer * 10)
            pts = [(x, y + r * 1.2 * glow), (x - r, y - r * 0.5),
                   (x, y), (x + r, y - r * 0.5)]
            pygame.draw.polygon(surface, c, pts)
            pygame.draw.circle(surface, self._alpha_color(YELLOW, alpha),
                               (x, y - r * 0.3), int(r * 0.4))
        elif self.kind == ENEMY_HEAVY:
            c = self._alpha_color(DARK_RED, alpha)
            c2 = self._alpha_color(RED, alpha)
            pts = [(x, y + r), (x - r, y), (x - r * 0.8, y - r * 0.8),
                   (x + r * 0.8, y - r * 0.8), (x + r, y)]
            pygame.draw.polygon(surface, c, pts)
            pygame.draw.polygon(surface, c2, pts, 3)
            pygame.draw.rect(surface, c2,
                             (x - r * 0.3, y - r * 0.9, r * 0.6, r * 0.5))
            for sx in [-r * 0.6, r * 0.6]:
                pygame.draw.circle(surface, c2,
                                   (int(x + sx), int(y - r * 0.2)), 4)
        elif self.kind == ENEMY_SHIELDED:
            c = self._alpha_color(BLUE, alpha)
            c2 = self._alpha_color(CYAN, alpha)
            pygame.draw.ellipse(surface, c,
                                (x - r, y - r * 0.7, r * 2, r * 1.4))
            pygame.draw.ellipse(surface, c2,
                                (x - r, y - r * 0.7, r * 2, r * 1.4), 2)
            pygame.draw.ellipse(surface, c2,
                                (x - r * 0.5, y - r * 0.4, r, r * 0.5))
        elif self.kind == ENEMY_STEALTH:
            c = self._alpha_color(PURPLE, alpha)
            c2 = self._alpha_color(PINK, alpha)
            pts = [(x, y - r), (x + r, y), (x + r * 0.6, y + r * 0.8),
                   (x, y + r * 0.5), (x - r * 0.6, y + r * 0.8),
                   (x - r, y)]
            pygame.draw.polygon(surface, c, pts)
            pygame.draw.polygon(surface, c2, pts, 2)
            if self.revealed:
                pygame.draw.circle(surface, c2, (x, y - r * 0.3), 6)
        elif self.kind == ENEMY_TURRET:
            c = self._alpha_color(GRAY, alpha)
            c2 = self._alpha_color(WHITE, alpha)
            pygame.draw.circle(surface, c, (x, y), r)
            pygame.draw.circle(surface, c2, (x, y), r, 3)
            tx = x + math.cos(self.turret_angle) * r
            ty = y + math.sin(self.turret_angle) * r
            bx = x + math.cos(self.turret_angle) * (r + 20)
            by = y + math.sin(self.turret_angle) * (r + 20)
            pygame.draw.line(surface, self._alpha_color(DARK_GRAY, alpha),
                             (x, y), (int(bx), int(by)), 8)
            pygame.draw.line(surface, c2, (x, y), (int(bx), int(by)), 3)
        elif self.kind == ENEMY_INTERCEPTOR:
            c = self._alpha_color(CYAN, alpha)
            c2 = self._alpha_color(BLUE, alpha)
            pts = [(x, y - r), (x + r * 1.1, y + r * 0.3),
                   (x + r * 0.6, y + r * 0.8), (x, y + r * 0.3),
                   (x - r * 0.6, y + r * 0.8), (x - r * 1.1, y + r * 0.3)]
            pygame.draw.polygon(surface, c2, pts)
            pygame.draw.polygon(surface, c, pts, 2)
            pygame.draw.circle(surface, c, (x, y - r * 0.3), int(r * 0.3))
        elif self.kind == ENEMY_MOTHERSHIP:
            c = self._alpha_color(DARK_GRAY, alpha)
            c2 = self._alpha_color(RED, alpha)
            c3 = self._alpha_color(GRAY, alpha)
            w = r * 2.5
            h = r * 1.2
            pts = [(x - w * 0.5, y), (x - w * 0.3, y - h),
                   (x + w * 0.3, y - h), (x + w * 0.5, y),
                   (x + w * 0.3, y + h * 0.6), (x - w * 0.3, y + h * 0.6)]
            pygame.draw.polygon(surface, c, pts)
            pygame.draw.polygon(surface, c2, pts, 3)
            for i in range(5):
                lx = int(x - w * 0.25 + i * w * 0.125)
                ly = int(y - h * 0.6)
                pygame.draw.circle(surface, c3, (lx, ly), 5)
            pygame.draw.ellipse(surface, c2,
                                (x - r * 0.5, y - r * 0.3, r, r * 0.6), 2)
            for sx in [-1, 1]:
                ex = int(x + sx * w * 0.45)
                ey = int(y + r * 0.2)
                pygame.draw.circle(surface, self._alpha_color(YELLOW, alpha),
                                   (ex, ey), 6)

    def _alpha_color(self, color, alpha):
        if alpha >= 255:
            return color
        return (color[0], color[1], color[2], alpha)

    def _draw_shield(self, surface, x, y):
        r = int(self.radius * 1.6)
        ratio = self.shield_hp / self.max_shield
        shield_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        alpha = int(40 + 60 * ratio)
        pulse = 1.0 + 0.1 * math.sin(self.anim_timer * 5)
        dr = int(r * pulse)
        pygame.draw.circle(shield_surf, (80, 160, 255, alpha), (r, r), dr, 3)
        surface.blit(shield_surf, (x - r, y - r))

    def _draw_hp_bar(self, surface):
        bar_w = self.radius * 2
        bar_h = 4
        x = int(self.x - bar_w / 2)
        y = int(self.y - self.radius - 12)
        pygame.draw.rect(surface, DARK_GRAY, (x, y, bar_w, bar_h))
        ratio = self.hp / self.max_hp
        c = GREEN if ratio > 0.5 else (YELLOW if ratio > 0.25 else RED)
        pygame.draw.rect(surface, c, (x, y, int(bar_w * ratio), bar_h))
