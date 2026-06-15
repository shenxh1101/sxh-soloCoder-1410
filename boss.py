import math
import random
import pygame
from config import *
from utils import *
from bullets import Bullet
from enemies import Enemy, ENEMY_KAMIKAZE, ENEMY_DRONE

BOSS_PHASES = 3


class Boss:
    def __init__(self, wave_num, difficulty=1.0):
        self.boss_level = (wave_num // WAVE_BOSS_INTERVAL)
        self.x = SCREEN_WIDTH // 2
        self.y = -150
        self.radius = 80 + self.boss_level * 5
        self.difficulty = difficulty * (1.0 + self.boss_level * 0.3)
        self.max_hp = int(1500 * self.difficulty)
        self.hp = self.max_hp
        self.phase = 0
        self.phase_thresholds = [self.max_hp * 0.66, self.max_hp * 0.33]
        self.dead = False
        self.vx = 0
        self.vy = 0
        self.anim_timer = 0
        self.fire_timer = 0
        self.phase_timer = 0
        self.entering = True
        self.attack_pattern = 0
        self.pattern_timer = 0
        self.weak_points = self._generate_weak_points()
        self.weak_point_exposed = [False, False, False]
        self.weak_point_timer = 0
        self.damage_multiplier = 1.0
        self.core_shield = True
        self.minion_timer = 0
        self.score_value = int(10000 * (1 + self.boss_level * 0.5))
        self.contact_damage = 80
        self.charge_target = None
        self.charging = False
        self.charge_speed = 0
        self.special_attack_timer = 0
        self.rage_mode = False
        self.shake_intensity = 0
        self._update_counter = 0
        self._last_fire_phase = -1
        self._phase_lock = False
        self._phase_lock_timer = 0

    def _generate_weak_points(self):
        pts = []
        for i in range(3):
            angle = (i / 3) * math.pi * 2 - math.pi / 2
            pts.append({
                'angle': angle,
                'offset': self.radius * 0.7,
                'hp': int(200 * self.difficulty),
                'max_hp': int(200 * self.difficulty),
                'destroyed': False
            })
        return pts

    def get_weak_point_pos(self, idx):
        wp = self.weak_points[idx]
        return (self.x + math.cos(wp['angle']) * wp['offset'],
                self.y + math.sin(wp['angle']) * wp['offset'])

    def take_damage(self, amount, hit_x, hit_y):
        if self.dead:
            return 0, False, -1
        actual_damage = amount
        hit_weak = -1
        for i in range(3):
            if self.weak_point_exposed[i] and not self.weak_points[i]['destroyed']:
                wx, wy = self.get_weak_point_pos(i)
                if distance(hit_x, hit_y, wx, wy) < 32:
                    self.weak_points[i]['hp'] -= amount * 3
                    hit_weak = i
                    actual_damage = amount * 3
                    if self.weak_points[i]['hp'] <= 0:
                        self.weak_points[i]['destroyed'] = True
                        self.damage_multiplier = 1.5 + i * 0.25
                        all_destroyed = True
                        for w2 in self.weak_points:
                            if not w2['destroyed']:
                                all_destroyed = False
                                break
                        if all_destroyed:
                            self.core_shield = False
                            self.damage_multiplier = 2.5
                    break
        if hit_weak < 0:
            if self.core_shield:
                actual_damage = int(actual_damage * 0.15)
            else:
                actual_damage = int(actual_damage * self.damage_multiplier)

        self.hp -= actual_damage
        self.shake_intensity = max(self.shake_intensity, 8 if hit_weak >= 0 else 4)

        try:
            old_phase = self.phase
            for i in range(len(self.phase_thresholds) - 1, -1, -1):
                if self.hp <= self.phase_thresholds[i] and self.phase <= i:
                    self.phase = i + 1
            if self.phase != old_phase:
                self._on_phase_change()
        except Exception:
            pass

        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            return self.score_value, True, hit_weak
        return 0, True, hit_weak

    def _on_phase_change(self):
        self.attack_pattern = 0
        self.phase_timer = 0
        self.pattern_timer = 0
        self.fire_timer = 0.25
        self.special_attack_timer = 2.5 + self.phase
        self.charging = False
        self._phase_lock = False
        self._phase_lock_timer = 0.35
        self.rage_mode = self.phase >= 2
        n_exposed = 1 + self.phase
        candidates = [i for i in range(3) if not self.weak_points[i]['destroyed']]
        for i in range(3):
            self.weak_point_exposed[i] = False
        if candidates:
            import random as rnd
            rnd.shuffle(candidates)
            for i in candidates[:n_exposed]:
                self.weak_point_exposed[i] = True
        self.weak_point_timer = 4.0 + random.uniform(0, 1.0)
        if self.phase >= 2:
            self.weak_point_timer *= 0.75
        self.shake_intensity = max(self.shake_intensity, 18)

    def update(self, dt, bullets_list, enemies_list, player, wingman=None, particles=None):
        if self.dead:
            return
        self._update_counter += 1
        self.anim_timer += dt
        self.phase_timer += dt
        self.pattern_timer += dt
        self.fire_timer -= dt
        self.minion_timer -= dt
        self.special_attack_timer -= dt
        self.weak_point_timer -= dt
        self.shake_intensity = max(0, self.shake_intensity - dt * 30)
        if self._phase_lock_timer > 0:
            self._phase_lock_timer -= dt
            if self._phase_lock_timer <= 0:
                self._phase_lock = False

        if self.entering:
            self.vy = 70
            if self.y >= 150:
                self.y = 150
                self.entering = False
                self.vy = 0
                self._on_phase_change()
        else:
            self._ai_update(dt, bullets_list, enemies_list, player, wingman, particles)

        if self.weak_point_timer <= 0 and not self.entering:
            n_exposed = 1 + self.phase
            candidates = [i for i in range(3) if not self.weak_points[i]['destroyed']]
            for i in range(3):
                self.weak_point_exposed[i] = False
            if candidates:
                random.shuffle(candidates)
                for i in candidates[:n_exposed]:
                    self.weak_point_exposed[i] = True
            self.weak_point_timer = 3.5 + random.uniform(-0.5, 0.8)
            if self.phase >= 2:
                self.weak_point_timer *= 0.75

        if self.minion_timer <= 0 and not self.entering:
            n = 1 + self.phase
            for i in range(n):
                angle = (i / max(1, n)) * math.pi * 2 + random.uniform(-0.15, 0.15)
                ex = self.x + math.cos(angle) * 130
                ey = self.y + math.sin(angle) * 130
                kind = ENEMY_KAMIKAZE if self.phase >= 1 else ENEMY_DRONE
                try:
                    e = Enemy(kind, ex, ey, self.difficulty * 0.75)
                    e.entering = False
                    e.target_y = random.uniform(250, SCREEN_HEIGHT * 0.65)
                    enemies_list.append(e)
                except Exception:
                    pass
            self.minion_timer = max(5.5, 9.0 - self.phase * 1.5)

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.x = clamp(self.x, self.radius + 40, SCREEN_WIDTH - self.radius - 40)
        self.y = clamp(self.y, 90, int(SCREEN_HEIGHT * 0.42))

    def _ai_update(self, dt, bullets_list, enemies_list, player, wingman, particles):
        base_speed = 50 + self.phase * 15
        if self.attack_pattern == 0:
            self.vx = math.sin(self.anim_timer * 0.7) * (base_speed + 25)
            self.vy = math.cos(self.anim_timer * 0.4) * base_speed * 0.35
        elif self.attack_pattern == 1:
            self.vx = math.sin(self.anim_timer * 1.0) * base_speed * 1.3
            self.vy = math.sin(self.anim_timer * 0.6) * base_speed * 0.2
        elif self.attack_pattern == 2:
            if self.charging:
                if self.charge_target:
                    angle = angle_between(self.x, self.y,
                                          self.charge_target[0], self.charge_target[1])
                    self.vx = math.cos(angle) * self.charge_speed
                    self.vy = math.sin(angle) * self.charge_speed
                    self.charge_speed = min(520, self.charge_speed + dt * 600)
                    if (self.y > SCREEN_HEIGHT * 0.72 or
                            distance(self.x, self.y,
                                     self.charge_target[0], self.charge_target[1]) < 40):
                        self.charging = False
                        if particles:
                            particles.explosion(self.x, self.y, count=80, size=6)
                        self.shake_intensity = 20
                else:
                    self.charging = False
            else:
                self.vx *= 0.96
                self.vy *= 0.96
        else:
            self.vx = math.sin(self.anim_timer * 0.25) * base_speed * 0.5
            self.vy = math.sin(self.anim_timer * 1.2) * base_speed * 0.6

        pattern_duration = 4.8 - self.phase * 0.4
        if self.pattern_timer >= pattern_duration:
            self.pattern_timer = 0
            self.attack_pattern = (self.attack_pattern + 1) % 4
            if self.attack_pattern == 2 and self.phase >= 1:
                targets = []
                if player and not player.dead:
                    targets.append((player.x, player.y))
                if wingman and not wingman.dead:
                    targets.append((wingman.x, wingman.y))
                if targets and random.random() < 0.55:
                    self.charge_target = random.choice(targets)
                    self.charging = True
                    self.charge_speed = 80
                else:
                    self.charging = False
                    self.attack_pattern = (self.attack_pattern + 1) % 4
            else:
                self.charging = False

        fire_happened = False
        if self.fire_timer <= 0 and not self.charging:
            self._fire_pattern(bullets_list, player, wingman)
            fire_happened = True
            rate = 1.05 - self.phase * 0.15
            self.fire_timer = rate * random.uniform(0.85, 1.2)

        if not fire_happened and self.special_attack_timer <= 0 and self.phase >= 1 and not self.charging:
            did_special = self._special_attack(bullets_list, player, wingman)
            if did_special:
                self.special_attack_timer = 7.0 - self.phase * 0.8

    def _fire_pattern(self, bullets_list, player, wingman):
        targets = []
        if player and not player.dead:
            targets.append((player.x, player.y))
        if wingman and not wingman.dead:
            targets.append((wingman.x, wingman.y))
        target = targets[0] if targets else (SCREEN_WIDTH // 2, SCREEN_HEIGHT)

        if self.attack_pattern == 0 or self.phase == 0:
            n = 8 + self.phase * 3
            for i in range(n):
                angle = (i / n) * math.pi * 2 + self.anim_timer * 0.35
                speed = 200 + self.phase * 25
                b = Bullet(self.x, self.y,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           int(12 * self.difficulty), RED, 'enemy',
                           radius=5, kind='enemy_big', life=5.5)
                bullets_list.append(b)

        elif self.attack_pattern == 1:
            for tx, ty in targets[:1]:
                for burst in range(2):
                    angle = angle_between(self.x, self.y, tx, ty) + random.uniform(-0.08, 0.08)
                    speed = 320 + self.phase * 30
                    b = Bullet(self.x, self.y,
                               math.cos(angle) * speed,
                               math.sin(angle) * speed,
                               int(18 * self.difficulty), ORANGE, 'enemy',
                               radius=5, kind='missile', life=5.0)
                    bullets_list.append(b)

        elif self.attack_pattern == 3:
            n = 5 + self.phase * 2
            for i in range(n):
                base_angle = math.pi / 2
                spread = 0.9
                angle = base_angle + (i - n / 2) * spread / n
                angle += math.sin(self.anim_timer * 2.5 + i * 0.7) * 0.08
                speed = 260
                b = Bullet(self.x, self.y + self.radius * 0.5,
                           math.cos(angle) * speed,
                           math.sin(angle) * speed,
                           int(14 * self.difficulty), PURPLE, 'enemy',
                           radius=4, kind='normal', life=5.5)
                bullets_list.append(b)

    def _special_attack(self, bullets_list, player, wingman):
        if self._phase_lock:
            return False
        if self.phase == 1:
            for wave in range(3):
                n = 10 + wave * 3
                for i in range(n):
                    angle = (i / n) * math.pi * 2 + wave * 0.22
                    speed = 180 + wave * 35
                    b = Bullet(self.x, self.y,
                               math.cos(angle) * speed,
                               math.sin(angle) * speed,
                               int(10 * self.difficulty), DARK_RED, 'enemy',
                               radius=5, kind='enemy_big', life=7.0)
                    bullets_list.append(b)
            self._phase_lock = True
            self._phase_lock_timer = 0.4
            return True
        elif self.phase >= 2:
            targets = []
            if player and not player.dead:
                targets.append(player)
            if wingman and not wingman.dead:
                targets.append(wingman)
            for t in targets:
                for i in range(4):
                    angle = angle_between(self.x, self.y, t.x, t.y)
                    angle += random.uniform(-0.15, 0.15)
                    speed = 230 + i * 20
                    b = Bullet(self.x + random.uniform(-25, 25),
                               self.y + random.uniform(-25, 25),
                               math.cos(angle) * speed,
                               math.sin(angle) * speed,
                               int(22 * self.difficulty), PINK, 'enemy',
                               radius=7, kind='missile', life=5.5, target=t)
                    bullets_list.append(b)
            self._phase_lock = True
            self._phase_lock_timer = 0.5
            return True
        return False

    def draw(self, surface):
        if self.dead:
            return
        x, y = int(self.x), int(self.y)
        if self.shake_intensity > 0:
            x += int(random.uniform(-self.shake_intensity, self.shake_intensity))
            y += int(random.uniform(-self.shake_intensity, self.shake_intensity))
        r = int(self.radius)
        self._draw_body(surface, x, y, r)
        self._draw_weak_points(surface, x, y)
        self._draw_hp_bar(surface)

    def _draw_body(self, surface, x, y, r):
        base_color = (120, 40, 60) if self.rage_mode else (80, 50, 100)
        outline_color = RED if self.rage_mode else PURPLE
        accent = ORANGE if self.rage_mode else CYAN

        if self.phase == 0:
            shape = [
                (x - r, y),
                (x - r * 0.7, y - r * 0.8),
                (x, y - r),
                (x + r * 0.7, y - r * 0.8),
                (x + r, y),
                (x + r * 0.7, y + r * 0.5),
                (x, y + r * 0.7),
                (x - r * 0.7, y + r * 0.5),
            ]
        elif self.phase == 1:
            shape = [
                (x - r * 1.1, y + r * 0.2),
                (x - r * 0.9, y - r * 0.9),
                (x - r * 0.3, y - r * 1.1),
                (x + r * 0.3, y - r * 1.1),
                (x + r * 0.9, y - r * 0.9),
                (x + r * 1.1, y + r * 0.2),
                (x + r * 0.7, y + r * 0.7),
                (x, y + r * 0.9),
                (x - r * 0.7, y + r * 0.7),
            ]
        else:
            spikes = 8
            shape = []
            for i in range(spikes * 2):
                angle = (i / (spikes * 2)) * math.pi * 2
                dist = r if i % 2 == 0 else r * 0.7
                dist += math.sin(self.anim_timer * 2 + i) * 5
                shape.append((x + math.cos(angle) * dist,
                              y + math.sin(angle) * dist))

        pygame.draw.polygon(surface, base_color, shape)
        pygame.draw.polygon(surface, outline_color, shape, 3)

        core_r = int(r * 0.35 + math.sin(self.anim_timer * 3) * 3)
        core_c = accent if not self.core_shield else DARK_GRAY
        pygame.draw.circle(surface, core_c, (x, y), core_r + 4)
        pygame.draw.circle(surface, WHITE, (x, y), max(3, core_r - 4))

        for i in range(4):
            angle = (i / 4) * math.pi * 2 + self.anim_timer
            dx = math.cos(angle) * r * 0.55
            dy = math.sin(angle) * r * 0.55
            pygame.draw.circle(surface, outline_color,
                               (int(x + dx), int(y + dy)), 5)

        for i, (sx, sy) in enumerate([(-r * 0.7, r * 0.2), (r * 0.7, r * 0.2)]):
            ex = int(x + sx)
            ey = int(y + sy + math.sin(self.anim_timer * 5 + i) * 3)
            engine_c = accent if self.charging else outline_color
            pygame.draw.circle(surface, engine_c, (ex, ey), 8)
            pygame.draw.circle(surface, YELLOW, (ex, ey), 4)

    def _draw_weak_points(self, surface, x, y):
        for i in range(3):
            wx, wy = self.get_weak_point_pos(i)
            wx, wy = int(wx), int(wy)
            wp = self.weak_points[i]
            if wp['destroyed']:
                pygame.draw.circle(surface, DARK_GRAY, (wx, wy), 12)
                pygame.draw.circle(surface, BLACK, (wx, wy), 8)
                continue
            exposed = self.weak_point_exposed[i]
            color = (YELLOW if exposed else DARK_GRAY)
            size = 14 if exposed else 10
            if exposed:
                pulse = 1 + 0.2 * math.sin(self.anim_timer * 8)
                pygame.draw.circle(surface, ORANGE, (wx, wy), int(size * pulse * 1.4))
            pygame.draw.circle(surface, color, (wx, wy), size)
            pygame.draw.circle(surface, WHITE, (wx, wy), max(3, size - 5))
            if exposed and wp['hp'] < wp['max_hp']:
                bw, bh = 28, 4
                bx, by = wx - bw // 2, wy - size - 8
                pygame.draw.rect(surface, DARK_GRAY, (bx, by, bw, bh))
                ratio = wp['hp'] / wp['max_hp']
                c = GREEN if ratio > 0.5 else (YELLOW if ratio > 0.25 else RED)
                pygame.draw.rect(surface, c, (bx, by, int(bw * ratio), bh))

    def _draw_hp_bar(self, surface):
        bar_w = SCREEN_WIDTH - 200
        bar_h = 18
        x, y = 100, 50
        pygame.draw.rect(surface, BLACK, (x - 3, y - 3, bar_w + 6, bar_h + 6))
        pygame.draw.rect(surface, DARK_GRAY, (x, y, bar_w, bar_h))
        ratio = self.hp / self.max_hp
        phase_c = [CYAN, ORANGE, RED][min(self.phase, 2)]
        pygame.draw.rect(surface, phase_c, (x, y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(surface, WHITE, (x, y, bar_w, bar_h), 2)

        label = f"BOSS Lv.{self.boss_level + 1}  |  PHASE {self.phase + 1}/{BOSS_PHASES}"
        if self.rage_mode:
            label += "  [RAGE]"
        draw_text_outline(surface, label, SCREEN_WIDTH // 2, y - 5, 16, WHITE, BLACK, center=True)

        for i in range(BOSS_PHASES - 1):
            tx = x + int(bar_w * (1 - (i + 1) / BOSS_PHASES))
            pygame.draw.line(surface, WHITE, (tx, y), (tx, y + bar_h), 2)
