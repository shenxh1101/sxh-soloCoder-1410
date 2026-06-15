import math
import random
import pygame
from config import *
from utils import *
from enemies import (Enemy, ENEMY_DRONE, ENEMY_KAMIKAZE, ENEMY_HEAVY,
                     ENEMY_SHIELDED, ENEMY_STEALTH, ENEMY_TURRET,
                     ENEMY_INTERCEPTOR, ENEMY_MOTHERSHIP, ENEMY_COUNT)
from boss import Boss


class WaveManager:
    def __init__(self):
        self.wave = 0
        self.score_for_next_wave = 1000
        self.spawn_timer = 0
        self.wave_spawned = 0
        self.wave_total = 0
        self.enemies_in_wave = 0
        self.difficulty = 1.0
        self.base_difficulty = 1.0
        self.is_boss_wave = False
        self.boss_spawned = False
        self.boss = None
        self.player_performance = 1.0
        self.combo_factor = 1.0
        self.time_factor = 1.0
        self.damage_taken = 0
        self.damage_taken_timer = 0
        self.wave_start_time = 0
        self.between_wave_timer = 0
        self.state = 'preparing'
        self.state_timer = 0
        self.spawn_queue = []
        self.current_spawn_interval = 1.5
        self.combo_samples = []

    def reset(self):
        self.wave = 0
        self.score_for_next_wave = 1000
        self.spawn_timer = 0
        self.wave_spawned = 0
        self.wave_total = 0
        self.enemies_in_wave = 0
        self.difficulty = 1.0
        self.base_difficulty = 1.0
        self.is_boss_wave = False
        self.boss_spawned = False
        self.boss = None
        self.player_performance = 1.0
        self.combo_factor = 1.0
        self.time_factor = 1.0
        self.damage_taken = 0
        self.state = 'preparing'
        self.state_timer = 2.0
        self.spawn_queue = []
        self.combo_samples = []

    def start_next_wave(self):
        self.wave += 1
        self.wave_spawned = 0
        self.wave_start_time = pygame.time.get_ticks()
        self.damage_taken = 0
        self.between_wave_timer = 0

        self.is_boss_wave = (self.wave % WAVE_BOSS_INTERVAL == 0)
        self.boss_spawned = False

        self._update_difficulty()

        if self.is_boss_wave:
            self.wave_total = 1
            self.enemies_in_wave = 1
            self.state = 'boss_intro'
            self.state_timer = 3.0
        else:
            self.wave_total = self._calculate_wave_size()
            self.enemies_in_wave = self.wave_total
            self._build_spawn_queue()
            self.current_spawn_interval = max(0.5, 1.5 - self.wave * 0.03)
            self.state = 'spawning'
            self.state_timer = 0

    def _calculate_wave_size(self):
        base = 10 + self.wave * 2
        base = int(base * self.player_performance)
        return min(60, base)

    def _build_spawn_queue(self):
        self.spawn_queue = []
        available = self._available_enemy_types()
        remaining = self.wave_total

        while remaining > 0:
            weights = self._get_enemy_weights(available)
            total_w = sum(weights.values())
            r = random.uniform(0, total_w)
            cum = 0
            chosen = ENEMY_DRONE
            for kind, w in weights.items():
                cum += w
                if r <= cum:
                    chosen = kind
                    break
            self.spawn_queue.append(chosen)
            remaining -= 1

        random.shuffle(self.spawn_queue)

        for group_size in range(3, min(7, len(self.spawn_queue)), 2):
            if random.random() < 0.3 and len(self.spawn_queue) >= group_size:
                idx = random.randint(0, len(self.spawn_queue) - group_size)
                self.spawn_queue[idx:idx + group_size] = ['group:' + str(group_size)] + self.spawn_queue[idx:idx + group_size]

    def _available_enemy_types(self):
        types = [ENEMY_DRONE]
        if self.wave >= 2:
            types.append(ENEMY_KAMIKAZE)
        if self.wave >= 3:
            types.append(ENEMY_INTERCEPTOR)
        if self.wave >= 4:
            types.append(ENEMY_HEAVY)
        if self.wave >= 6:
            types.append(ENEMY_SHIELDED)
        if self.wave >= 7:
            types.append(ENEMY_STEALTH)
        if self.wave >= 9:
            types.append(ENEMY_TURRET)
        if self.wave >= 12:
            types.append(ENEMY_MOTHERSHIP)
        return types

    def _get_enemy_weights(self, available):
        w = {}
        wave_scale = (self.wave - 1) * 0.08 + 1
        for kind in available:
            if kind == ENEMY_DRONE:
                w[kind] = max(10, 30 - self.wave * 1.5)
            elif kind == ENEMY_KAMIKAZE:
                w[kind] = 8 + self.wave * 0.3
            elif kind == ENEMY_HEAVY:
                w[kind] = 4 + self.wave * 0.4
            elif kind == ENEMY_SHIELDED:
                w[kind] = 3 + self.wave * 0.3
            elif kind == ENEMY_STEALTH:
                w[kind] = 3 + self.wave * 0.25
            elif kind == ENEMY_TURRET:
                w[kind] = 2 + self.wave * 0.2
            elif kind == ENEMY_INTERCEPTOR:
                w[kind] = 5 + self.wave * 0.35
            elif kind == ENEMY_MOTHERSHIP:
                w[kind] = 1 + self.wave * 0.1
            else:
                w[kind] = 5
            w[kind] *= wave_scale
        return w

    def _update_difficulty(self):
        target = 1.0 + (self.wave - 1) * 0.12
        target *= self.player_performance
        target = min(5.0, target)
        self.base_difficulty = target
        self.difficulty = self.base_difficulty

    def update_performance(self, player_hp_ratio, max_combo, avg_combo, wave_time_sec):
        hp_factor = 0.5 + player_hp_ratio * 0.8
        combo_factor = min(2.0, 0.8 + avg_combo * 0.05)
        time_factor = max(0.7, min(1.3, 30.0 / max(10, wave_time_sec)))
        damage_penalty = max(0.6, 1.0 - self.damage_taken * 0.002)

        self.player_performance = (hp_factor * 0.3 +
                                   combo_factor * 0.3 +
                                   time_factor * 0.2 +
                                   damage_penalty * 0.2)

        if max_combo >= 30:
            self.player_performance *= 1.15
        elif max_combo >= 15:
            self.player_performance *= 1.05

        self.player_performance = clamp(self.player_performance, 0.6, 1.6)
        self.difficulty = self.base_difficulty * self.player_performance

    def register_damage(self, amount):
        self.damage_taken += amount

    def register_combo(self, combo_value):
        if combo_value > 0:
            self.combo_samples.append(combo_value)
            if len(self.combo_samples) > 500:
                self.combo_samples = self.combo_samples[-500:]

    def get_avg_combo(self):
        if not self.combo_samples:
            return 0
        return sum(self.combo_samples) / len(self.combo_samples)

    def update(self, dt, enemies_list, particles=None):
        self.spawn_timer -= dt
        self.state_timer -= dt

        if self.state == 'preparing':
            if self.state_timer <= 0:
                self.start_next_wave()
        elif self.state == 'boss_intro':
            if self.state_timer <= 0:
                if not self.boss_spawned:
                    self.boss = Boss(self.wave, self.difficulty)
                    self.boss_spawned = True
                self.state = 'boss_fight'
        elif self.state == 'boss_fight':
            if self.boss and self.boss.dead:
                self.state = 'wave_clear'
                self.state_timer = 3.0
        elif self.state == 'spawning':
            if self.spawn_timer <= 0 and self.wave_spawned < self.wave_total:
                self._spawn_next(enemies_list, particles)
                self.spawn_timer = self.current_spawn_interval * random.uniform(0.7, 1.3)
            if self.wave_spawned >= self.wave_total:
                self.state = 'clearing'
        elif self.state == 'clearing':
            alive = sum(1 for e in enemies_list if not e.dead)
            if alive == 0:
                self.state = 'wave_clear'
                self.state_timer = 3.0
        elif self.state == 'wave_clear':
            if self.state_timer <= 0:
                self.state = 'preparing'
                self.state_timer = 1.5

        if self.boss:
            self.boss.update(dt, self._get_bullet_list_hack(), enemies_list,
                            None, None, particles)

    def _get_bullet_list_hack(self):
        return []

    def _spawn_next(self, enemies_list, particles):
        if not self.spawn_queue:
            self.wave_spawned = self.wave_total
            return

        item = self.spawn_queue.pop(0)
        if isinstance(item, str) and item.startswith('group:'):
            size = int(item.split(':')[1])
            group_kinds = []
            for _ in range(size):
                if self.spawn_queue:
                    group_kinds.append(self.spawn_queue.pop(0))
                    self.wave_spawned += 1
            self._spawn_group(enemies_list, group_kinds, particles)
        else:
            self._spawn_single(enemies_list, item, particles)
            self.wave_spawned += 1

    def _spawn_single(self, enemies_list, kind, particles):
        x = random.uniform(60, SCREEN_WIDTH - 60)
        y = -40
        e = Enemy(kind, x, y, self.difficulty)
        enemies_list.append(e)

    def _spawn_group(self, enemies_list, kinds, particles):
        if not kinds:
            return
        n = len(kinds)
        start_x = random.uniform(60, SCREEN_WIDTH - 60 - n * 50)
        formation = random.choice(['line', 'v', 'diagonal'])
        for i, kind in enumerate(kinds):
            if formation == 'line':
                x = start_x + i * 50
                y = -40
            elif formation == 'v':
                offset = abs(i - n // 2) * 30
                x = start_x + i * 50
                y = -40 - offset
            else:
                x = start_x + i * 50
                y = -40 - i * 20
            e = Enemy(kind, x, y, self.difficulty)
            e.target_y = random.uniform(100, SCREEN_HEIGHT * 0.5)
            enemies_list.append(e)

    def is_active(self):
        return self.state not in ['preparing', 'wave_clear']

    def get_wave_info(self):
        return {
            'wave': self.wave,
            'state': self.state,
            'difficulty': self.difficulty,
            'is_boss': self.is_boss_wave,
            'progress': 1.0 if self.wave_total == 0 else self.wave_spawned / self.wave_total,
            'enemies_remaining': self.enemies_in_wave
        }

    def check_game_over(self, player, wingman=None):
        if player.dead:
            if wingman is None or wingman.dead:
                return True
        return False
