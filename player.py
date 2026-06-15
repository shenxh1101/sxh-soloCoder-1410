import math
import pygame
from config import *
from utils import *
from bullets import WeaponSystem


class Ship:
    def __init__(self, x, y, player_idx=0, is_wingman=False):
        self.x = x
        self.y = y
        self.player_idx = player_idx
        self.is_wingman = is_wingman
        self.radius = 18 if not is_wingman else 14
        self.weapons = WeaponSystem(owner='wingman' if is_wingman else 'player')
        self.hp = PLAYER_MAX_HP if not is_wingman else int(PLAYER_MAX_HP * 0.7)
        self.max_hp = self.hp
        self.shield = PLAYER_MAX_SHIELD if not is_wingman else int(PLAYER_MAX_SHIELD * 0.5)
        self.max_shield = self.shield
        self.invincible = 0
        self.flash_timer = 0
        self.dead = False
        self.thrust_timer = 0
        self.color = CYAN if not is_wingman else GREEN
        self.secondary_color = BLUE if not is_wingman else DARK_GREEN
        self.shield_timer = 0
        self.score = 0
        self.combo = 0
        self.combo_timer = 0
        self.dodge_slowmo = 0
        self.dodge_cooldown = 0
        self.last_dodge_time = 0
        self.body_shape = 0
        self.engine_style = 0
        self.cockpit_style = 0
        self.primary_color = self.color
        self._hitbox_offset_x = 0
        self._hitbox_offset_y = 0

    def customize(self, body=0, engine=0, cockpit=0, color=None):
        self.body_shape = body % 3
        self.engine_style = engine % 3
        self.cockpit_style = cockpit % 3
        if color is not None:
            self.color = color
            self.primary_color = color

    def get_hitbox_rect(self):
        r = self.radius * 0.5
        return (self.x - r + self._hitbox_offset_x,
                self.y - r + self._hitbox_offset_y,
                r * 2, r * 2)

    def take_damage(self, amount):
        if self.invincible > 0:
            return False
        if self.shield > 0:
            absorb = min(self.shield, amount)
            self.shield -= absorb
            amount -= absorb
            self.shield_timer = 0.2
        if amount > 0:
            self.hp -= amount
            self.flash_timer = 0.15
            self.combo = 0
            self.combo_timer = 0
        self.invincible = 0.8
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
        return True

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def restore_shield(self, amount):
        self.shield = min(self.max_shield, self.shield + amount)

    def register_dodge(self):
        now = pygame.time.get_ticks()
        if now - self.last_dodge_time > 8000:
            self.dodge_slowmo = 0.8
            self.dodge_cooldown = 8.0
            self.last_dodge_time = now
            return True
        return False

    def update(self, dt, dx, dy, shooting, switch_dir=0, particles=None):
        if self.dead:
            return
        speed = WINGMAN_SPEED if self.is_wingman else SHIP_SPEED
        self.x += dx * speed * dt
        self.y += dy * speed * dt
        margin = self.radius + 5
        self.x = clamp(self.x, margin, SCREEN_WIDTH - margin)
        self.y = clamp(self.y, margin, SCREEN_HEIGHT - margin)

        if switch_dir != 0:
            self.weapons.switch_weapon(switch_dir)
        self.weapons.update(dt)

        if self.invincible > 0:
            self.invincible -= dt
        if self.flash_timer > 0:
            self.flash_timer -= dt
        if self.shield_timer > 0:
            self.shield_timer -= dt
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0
        if self.dodge_slowmo > 0:
            self.dodge_slowmo -= dt
        if self.dodge_cooldown > 0:
            self.dodge_cooldown -= dt

        if dx != 0 or dy != 0:
            self.thrust_timer += dt
            if self.thrust_timer > 0.01 and particles:
                self.thrust_timer = 0
                for i in range(2):
                    offset_x = random.uniform(-8, 8)
                    particles.thrust(self.x + offset_x, self.y + self.radius,
                                     math.pi / 2 + random.uniform(-0.3, 0.3))

        if self.shield < self.max_shield:
            self.shield += 2.0 * dt
            if self.shield > self.max_shield:
                self.shield = self.max_shield

    def start_plasma_charge(self):
        if self.dead:
            return
        self.weapons.start_charge()

    def release_plasma_charge(self, bullets_list, enemies=None):
        if self.dead:
            return []
        w = self.weapons.current_weapon
        if w == WEAPON_PLASMA:
            fired = self.weapons.release_charge(self.x, self.y, bullets_list,
                                                enemies=enemies, is_wingman=self.is_wingman)
            return fired
        return []

    def try_fire(self, bullets_list, enemies=None):
        if self.dead:
            return []
        w = self.weapons.current_weapon
        if w == WEAPON_PLASMA:
            return []
        return self.weapons.fire(self.x, self.y, bullets_list, enemies=enemies,
                                 is_wingman=self.is_wingman)

    def add_score(self, points, combo_bonus=True):
        multiplier = 1.0
        if combo_bonus and self.combo >= 5:
            multiplier = 1.0 + min(2.0, self.combo * 0.05)
            self.combo_timer = 2.5
        self.combo += 1
        self.score += int(points * multiplier)

    def draw(self, surface):
        if self.dead:
            return
        visible = True
        if self.invincible > 0:
            visible = int(pygame.time.get_ticks() / 60) % 2 == 0
        if not visible:
            return
        self._draw_ship(surface)
        if self.flash_timer > 0:
            self._draw_flash(surface)
        if self.shield > 0 or self.shield_timer > 0:
            self._draw_shield(surface)

    def _draw_ship(self, surface):
        x, y = int(self.x), int(self.y)
        r = self.radius
        c = self.color
        c2 = self.secondary_color
        cp = WHITE

        if self.body_shape == 0:
            points = [
                (x, y - r),
                (x + r * 0.7, y),
                (x + r * 0.5, y + r * 0.6),
                (x - r * 0.5, y + r * 0.6),
                (x - r * 0.7, y),
            ]
        elif self.body_shape == 1:
            points = [
                (x, y - r * 1.1),
                (x + r * 0.9, y - r * 0.2),
                (x + r * 0.7, y + r * 0.7),
                (x, y + r * 0.5),
                (x - r * 0.7, y + r * 0.7),
                (x - r * 0.9, y - r * 0.2),
            ]
        else:
            points = [
                (x, y - r * 1.1),
                (x + r * 0.5, y - r * 0.6),
                (x + r, y + r * 0.3),
                (x + r * 0.5, y + r * 0.8),
                (x - r * 0.5, y + r * 0.8),
                (x - r, y + r * 0.3),
                (x - r * 0.5, y - r * 0.6),
            ]
        pygame.draw.polygon(surface, c2, points)
        pygame.draw.polygon(surface, c, points, 2)

        if self.engine_style == 0:
            pygame.draw.rect(surface, c2,
                             (x - r * 0.6, y + r * 0.5, r * 1.2, r * 0.35))
            pygame.draw.rect(surface, c,
                             (x - r * 0.6, y + r * 0.5, r * 1.2, r * 0.35), 1)
        elif self.engine_style == 1:
            pygame.draw.rect(surface, c2,
                             (x - r * 0.8, y + r * 0.4, r * 0.45, r * 0.4))
            pygame.draw.rect(surface, c2,
                             (x + r * 0.35, y + r * 0.4, r * 0.45, r * 0.4))
        else:
            for i, sx in enumerate([-0.65, 0, 0.65]):
                pygame.draw.rect(surface, c2,
                                 (x + r * sx - r * 0.15, y + r * 0.45,
                                  r * 0.3, r * 0.4))

        if self.cockpit_style == 0:
            pygame.draw.ellipse(surface, cp,
                                (x - r * 0.25, y - r * 0.5, r * 0.5, r * 0.6))
        elif self.cockpit_style == 1:
            pts = [(x, y - r * 0.7), (x + r * 0.3, y - r * 0.1),
                   (x - r * 0.3, y - r * 0.1)]
            pygame.draw.polygon(surface, cp, pts)
        else:
            pygame.draw.rect(surface, cp,
                             (x - r * 0.2, y - r * 0.6, r * 0.4, r * 0.5),
                             border_radius=2)

        w = self.weapons.current_weapon
        wc = WEAPON_COLORS[w]
        if w == WEAPON_LASER:
            pygame.draw.rect(surface, wc, (x - r * 0.15, y - r * 1.0, r * 0.3, r * 0.4))
        elif w == WEAPON_SPREAD:
            for sx in [-0.4, 0, 0.4]:
                pygame.draw.rect(surface, wc,
                                 (x + r * sx - 2, y - r * 0.9, 4, r * 0.35))
        elif w == WEAPON_MISSILE:
            for sx in [-0.5, 0.5]:
                pygame.draw.rect(surface, wc,
                                 (x + r * sx - 3, y - r * 0.7, 6, r * 0.3))
        elif w == WEAPON_PLASMA:
            charge = self.weapons.plasma_charge
            charging = self.weapons.is_charging_plasma
            cr = int(r * 0.22 + charge * r * 0.55)
            cx, cy = x, int(y - r * 0.75)
            if charging and charge > 0:
                pulses = 3
                for pi in range(pulses):
                    phase = (pi / pulses + pygame.time.get_ticks() * 0.003) % 1.0
                    al = int(120 * (1.0 - phase) * min(1.0, charge * 2))
                    pr = int(cr + 6 + phase * (12 + charge * 18))
                    pulse_surf = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
                    pygame.draw.circle(pulse_surf, (255, 100, 255, al), (pr, pr), pr, 2 + int(charge * 2))
                    surface.blit(pulse_surf, (cx - pr, cy - pr))
                if charge > 0.4:
                    for _ in range(3):
                        ax = cx + random.uniform(-cr - 4, cr + 4)
                        ay = cy + random.uniform(-cr - 4, cr + 4)
                        a_color = (255, random.randint(80, 220), 255)
                        pygame.draw.circle(surface, a_color, (int(ax), int(ay)), 1 + int(charge * 2))
            cc1 = (255, int(80 + charge * 175), 255)
            cc2 = (255, int(180 + charge * 75), 255)
            if charge < 0.15:
                cc1 = (160, 80, 160)
            pygame.draw.circle(surface, cc1, (cx, cy), cr + 4)
            pygame.draw.circle(surface, cc2, (cx, cy), max(1, cr))
            pygame.draw.circle(surface, WHITE, (cx, cy), max(1, int(cr * 0.55)))

    def _draw_flash(self, surface):
        x, y = int(self.x), int(self.y)
        r = int(self.radius * 1.5)
        flash_surface = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        alpha = int(128 * (self.flash_timer / 0.15))
        pygame.draw.circle(flash_surface, (255, 255, 255, alpha), (r, r), r)
        surface.blit(flash_surface, (x - r, y - r))

    def _draw_shield(self, surface):
        x, y = int(self.x), int(self.y)
        r = int(self.radius * 1.4)
        ratio = self.shield / self.max_shield
        shield_surface = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        alpha = int(60 + 60 * ratio)
        pulse = 1.0
        if self.shield_timer > 0:
            pulse = 1.0 + 0.3 * (self.shield_timer / 0.2)
        dr = int(r * pulse)
        pygame.draw.circle(shield_surface, (100, 200, 255, alpha), (r, r), dr, 3)
        pygame.draw.circle(shield_surface, (100, 200, 255, alpha // 3), (r, r), dr)
        surface.blit(shield_surface, (x - r, y - r))


class Wingman(Ship):
    def __init__(self, x, y, leader):
        super().__init__(x, y, player_idx=1, is_wingman=True)
        self.leader = leader
        self.formation_offset = (-60, 30)
        self.target_x = x
        self.target_y = y

    def set_formation(self, side='left'):
        if side == 'left':
            self.formation_offset = (-60, 30)
        else:
            self.formation_offset = (60, 30)

    def update(self, dt, dx, dy, shooting, switch_dir=0, particles=None, follow_leader=True):
        if self.dead:
            return
        if follow_leader and self.leader and not self.leader.dead:
            self.target_x = self.leader.x + self.formation_offset[0]
            self.target_y = self.leader.y + self.formation_offset[1]
            to_x = self.target_x - self.x
            to_y = self.target_y - self.y
            d = math.sqrt(to_x * to_x + to_y * to_y)
            if d > 2:
                ndx = to_x / d * min(1.0, d / 30.0)
                ndy = to_y / d * min(1.0, d / 30.0)
                dx = ndx if abs(dx) < abs(ndx) else dx
                dy = ndy if abs(dy) < abs(ndy) else dy
        super().update(dt, dx, dy, shooting, switch_dir, particles)
