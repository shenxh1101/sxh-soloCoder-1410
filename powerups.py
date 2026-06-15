import math
import random
import pygame
from config import *
from utils import *


POWERUP_WEAPON = 0
POWERUP_HEAL = 1
POWERUP_SHIELD = 2
POWERUP_UPGRADE = 3
POWERUP_BOMB = 4

POWERUP_TYPES = [POWERUP_WEAPON, POWERUP_HEAL, POWERUP_SHIELD, POWERUP_UPGRADE, POWERUP_BOMB]
POWERUP_COLORS = [YELLOW, GREEN, CYAN, PURPLE, RED]
POWERUP_NAMES = ["WEAPON", "HEAL", "SHIELD", "UPGRADE", "BOMB"]


class PowerUp:
    def __init__(self, x, y, kind=None):
        self.x = x
        self.y = y
        self.vy = 120
        self.radius = 14
        self.dead = False
        if kind is None:
            weights = [0.3, 0.25, 0.2, 0.15, 0.1]
            kind = random.choices(POWERUP_TYPES, weights=weights, k=1)[0]
        self.kind = kind
        self.color = POWERUP_COLORS[kind]
        self.angle = 0
        self.bob_timer = random.uniform(0, math.pi * 2)
        self.life = 15.0
        self.flash_timer = 0

    def update(self, dt):
        self.y += self.vy * dt
        self.angle += dt * 2.0
        self.bob_timer += dt * 3.0
        self.life -= dt
        if self.life < 3:
            self.flash_timer += dt
        if self.life <= 0:
            self.dead = True
        if self.y > SCREEN_HEIGHT + 40:
            self.dead = True

    def draw(self, surface):
        visible = True
        if self.life < 3:
            visible = int(self.flash_timer * 8) % 2 == 0
        if not visible:
            return
        x, y = int(self.x), int(self.y + math.sin(self.bob_timer) * 4)
        r = self.radius

        s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        cx, cy = r * 2, r * 2

        for i in range(3):
            alpha = 80 - i * 20
            rr = r + 6 + i * 3
            pygame.draw.circle(s, (*self.color[:3], alpha), (cx, cy), int(rr), 2)

        pygame.draw.circle(s, self.color, (cx, cy), r)
        pygame.draw.circle(s, WHITE, (cx, cy), r, 2)

        inner_color = tuple(max(0, c - 60) for c in self.color[:3])
        pygame.draw.circle(s, inner_color, (cx, cy), r - 4)

        name = POWERUP_NAMES[self.kind]
        if self.kind == POWERUP_WEAPON:
            pygame.draw.polygon(s, WHITE, [
                (cx, cy - r * 0.6), (cx + r * 0.4, cy + r * 0.4),
                (cx, cy + r * 0.1), (cx - r * 0.4, cy + r * 0.4)
            ])
        elif self.kind == POWERUP_HEAL:
            hw = 3
            pygame.draw.rect(s, WHITE, (cx - hw, cy - r * 0.5, hw * 2, r))
            pygame.draw.rect(s, WHITE, (cx - r * 0.5, cy - hw, r, hw * 2))
        elif self.kind == POWERUP_SHIELD:
            pygame.draw.arc(s, WHITE, (cx - r * 0.6, cy - r * 0.6, r * 1.2, r * 1.2),
                            math.radians(30), math.radians(150), 3)
            pygame.draw.line(s, WHITE, (cx - r * 0.55, cy - r * 0.1),
                             (cx - r * 0.1, cy + r * 0.5), 3)
            pygame.draw.line(s, WHITE, (cx + r * 0.55, cy - r * 0.1),
                             (cx + r * 0.1, cy + r * 0.5), 3)
        elif self.kind == POWERUP_UPGRADE:
            arrow_pts = [
                (cx, cy - r * 0.6), (cx + r * 0.35, cy),
                (cx + r * 0.15, cy), (cx + r * 0.15, cy + r * 0.5),
                (cx - r * 0.15, cy + r * 0.5), (cx - r * 0.15, cy),
                (cx - r * 0.35, cy)
            ]
            pygame.draw.polygon(s, WHITE, arrow_pts)
        elif self.kind == POWERUP_BOMB:
            pygame.draw.circle(s, WHITE, (cx, cy), int(r * 0.4))
            pygame.draw.rect(s, WHITE, (cx - 1, cy - r * 0.7, 2, r * 0.3))
            pygame.draw.circle(s, ORANGE, (cx, cy - int(r * 0.75)), 3)

        rotated = pygame.transform.rotate(s, math.degrees(self.angle) % 15 - 7.5)
        surface.blit(rotated, (x - rotated.get_width() // 2, y - rotated.get_height() // 2))

    def apply(self, ship, wingman=None, game=None):
        if self.kind == POWERUP_WEAPON:
            ship.weapons.switch_next()
            if wingman and not wingman.dead:
                wingman.weapons.switch_next()
        elif self.kind == POWERUP_HEAL:
            ship.heal(35)
            if wingman and not wingman.dead:
                wingman.heal(25)
        elif self.kind == POWERUP_SHIELD:
            ship.restore_shield(30)
            if wingman and not wingman.dead:
                wingman.restore_shield(20)
        elif self.kind == POWERUP_UPGRADE:
            w = ship.weapons.current_weapon
            ship.weapons.upgrade_weapon(w)
            if wingman and not wingman.dead:
                wingman.weapons.upgrade_weapon(w)
        elif self.kind == POWERUP_BOMB:
            if game:
                for e in game.enemies:
                    if not e.dead:
                        e.take_damage(50)
                        if e.dead:
                            game.particles.explosion(e.x, e.y, count=30, size=4)
                            game.score += e.score_value
                            game.player.score += e.score_value
                if game.wave_mgr.boss and not game.wave_mgr.boss.dead:
                    game.wave_mgr.boss.take_damage(100, game.wave_mgr.boss.x, game.wave_mgr.boss.y)
                game.screen_shake = max(game.screen_shake, 25)
                for _ in range(5):
                    rx = random.randint(100, SCREEN_WIDTH - 100)
                    ry = random.randint(100, SCREEN_HEIGHT - 100)
                    game.particles.big_explosion(rx, ry)
        return True
