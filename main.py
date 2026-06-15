import math
import random
import sys
import os
import time
import pygame

from config import *
from utils import *
from input_manager import InputManager
from particles import ParticlePool, StarField
from bullets import Bullet, WeaponSystem
from player import Ship, Wingman
from enemies import (Enemy, ENEMY_DRONE, ENEMY_KAMIKAZE, ENEMY_HEAVY,
                     ENEMY_SHIELDED, ENEMY_STEALTH, ENEMY_TURRET,
                     ENEMY_INTERCEPTOR, ENEMY_MOTHERSHIP)
from boss import Boss
from wave_manager import WaveManager
from audio import ProceduralAudio
from save_system import HighScoreManager, ReplayRecorder, ReplayPlayer
from powerups import PowerUp
from ui import (MainMenu, HUD, GameOverScreen, PauseMenu,
                LeaderboardScreen, SettingsScreen, ShipCustomize, ReplayScreen)


class GameState:
    MENU = 0
    PLAYING = 1
    GAMEOVER = 2
    PAUSED = 3
    LEADERBOARD = 4
    SETTINGS = 5
    CUSTOMIZE = 6
    REPLAYS = 7
    REPLAY_PLAYING = 8


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.dt = 0
        self.state = GameState.MENU
        self.prev_state = GameState.MENU
        self.game_start_time = 0

        this_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(this_dir)

        self.input = InputManager()
        self.particles = ParticlePool(MAX_PARTICLES)
        self.starfield = StarField()
        self.audio = ProceduralAudio()
        self.audio.init_sounds()
        self.highscores = HighScoreManager()
        self.recorder = ReplayRecorder()
        self.replay_player = ReplayPlayer()

        self.ship_config = (0, 0, 0, CYAN)
        self.coop_mode = False

        self.player = None
        self.wingman = None
        self.bullets = []
        self.enemies = []
        self.powerups = []
        self.wave_mgr = WaveManager()
        self.score = 0
        self.max_combo = 0

        self.score_saved = False
        self.is_new_highscore = False

        self.screen_shake = 0

        self.slowmo_timer = 0

        self._dodge_bullet_history = {}

        self._init_ui()

    def _init_ui(self):
        self.main_menu = MainMenu(
            on_start=lambda: self._start_game(False),
            on_leaderboard=lambda: self._change_state(GameState.LEADERBOARD),
            on_replays=lambda: self._change_state(GameState.REPLAYS),
            on_settings=lambda: self._change_state(GameState.SETTINGS),
            on_customize=lambda: self._change_state(GameState.CUSTOMIZE),
            on_coop=lambda: self._start_game(True)
        )
        self.hud = HUD()

        self.gameover_screen = GameOverScreen(
            on_restart=lambda: self._start_game(self.coop_mode),
            on_menu=lambda: self._change_state(GameState.MENU),
            on_save_score=self._on_save_score
        )

        self.pause_menu = PauseMenu(
            on_resume=lambda: self._change_state(GameState.PLAYING),
            on_quit=lambda: self._on_quit_to_menu(),
            on_settings=lambda: self._change_state(GameState.SETTINGS)
        )

        self.leaderboard = LeaderboardScreen(
            on_back=lambda: self._change_state(self.prev_state)
        )

        self.settings = SettingsScreen(
            on_back=lambda: self._change_state(self.prev_state),
            get_volumes=lambda: {'sfx': self.audio.sfx_volume, 'music': self.audio.music_volume},
            set_sfx=lambda v: self.audio.set_sfx_volume(v),
            set_music=lambda v: self.audio.set_music_volume(v)
        )

        self.customize = ShipCustomize(
            on_back=lambda: self._change_state(GameState.MENU),
            on_confirm=self._on_customize_confirm
        )

        self.replay_screen = ReplayScreen(
            on_back=lambda: self._change_state(GameState.MENU),
            on_play=self._on_play_replay,
            on_delete=self._on_delete_replay
        )
        self.replays_list = self.recorder.list_replays()

    def _change_state(self, new_state):
        if new_state in [GameState.LEADERBOARD, GameState.SETTINGS,
                         GameState.CUSTOMIZE, GameState.REPLAYS]:
            self.prev_state = self.state
            if self.state == GameState.PAUSED:
                self.prev_state = GameState.PLAYING
        self.state = new_state
        if new_state == GameState.MENU:
            self.audio.stop_music()
            self.audio.start_music()

    def _start_game(self, coop):
        self.coop_mode = coop
        self.score = 0
        self.max_combo = 0

        self.bullets.clear()
        self.enemies.clear()
        self.powerups.clear()
        self.particles.clear()

        self.wave_mgr.reset()

        self.player = Ship(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120)
        body, engine, cockpit, color = self.ship_config
        self.player.customize(body, engine, cockpit, color)

        self.wingman = None
        if coop:
            self.wingman = Wingman(SCREEN_WIDTH // 2 - 60, SCREEN_HEIGHT - 80, self.player)
            self.wingman.set_formation('left')
            self.wingman.customize(1, 2, 1, GREEN)

        self.screen_shake = 0

        self.slowmo_timer = 0
        self.score_saved = False
        self.is_new_highscore = False
        self._dodge_bullet_history.clear()

        self.game_start_time = pygame.time.get_ticks()
        self._change_state(GameState.PLAYING)

        self.audio.start_music()
        self.recorder.start({
            'score': 0, 'wave': 0, 'coop': coop,
            'ship_config': self.ship_config
        })

    def _on_save_score(self):
        self.gameover_screen.start_save_input()

    def _on_quit_to_menu(self):
        self._end_game_early()
        self._change_state(GameState.MENU)

    def _end_game_early(self):
        self.recorder.stop({
            'score': self.score,
            'wave': self.wave_mgr.wave,
            'max_combo': self.max_combo,
            'duration': (pygame.time.get_ticks() - self.game_start_time) / 1000
        })
        self.recorder.save()
        self.audio.stop_music()

    def _on_customize_confirm(self):
        self.ship_config = self.customize.get_config()
        self._change_state(GameState.MENU)

    def _on_play_replay(self, filepath):
        if self.replay_player.load(filepath, self.recorder):
            self._change_state(GameState.REPLAY_PLAYING)

    def _on_delete_replay(self, filename):
        self.recorder.delete(filename)
        self.replays_list = self.recorder.list_replays()

    def _actual_save_score(self, name):
        duration = (pygame.time.get_ticks() - self.game_start_time) / 1000
        rank = self.highscores.add_score(name, self.score, self.wave_mgr.wave,
                                          self.max_combo, duration, self.coop_mode)
        self.is_new_highscore = rank <= 10
        self.score_saved = True

    def run(self):
        self.audio.start_music()
        while self.running:
            self.dt = min(self.clock.tick(FPS) / 1000.0, 1.0 / FPS * 3)
            self.input.update_begin()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                self.input.handle_event(event)
                self._handle_state_event(event)

            self._update()
            self._draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def _handle_state_event(self, event):
        if self.state == GameState.MENU:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self._start_game(False)
                return
            self.main_menu.handle_event(event)
        elif self.state == GameState.PLAYING:
            if event.type == pygame.KEYDOWN and event.key in [pygame.K_ESCAPE, pygame.K_p]:
                self._change_state(GameState.PAUSED)
        elif self.state == GameState.PAUSED:
            if event.type == pygame.KEYDOWN and event.key in [pygame.K_ESCAPE, pygame.K_p]:
                self._change_state(GameState.PLAYING)
            self.pause_menu.handle_event(event)
        elif self.state == GameState.GAMEOVER:
            result = self.gameover_screen.handle_event(event)
            if isinstance(result, tuple) and result[0] == 'save':
                self._actual_save_score(result[1])
                self.replays_list = self.recorder.list_replays()
        elif self.state == GameState.LEADERBOARD:
            self.leaderboard.handle_event(event)
        elif self.state == GameState.SETTINGS:
            self.settings.handle_event(event)
        elif self.state == GameState.CUSTOMIZE:
            self.customize.handle_event(event)
        elif self.state == GameState.REPLAYS:
            self.replay_screen.handle_event(event, self.replays_list)
        elif self.state == GameState.REPLAY_PLAYING:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._change_state(GameState.REPLAYS)
                self.replays_list = self.recorder.list_replays()

    def _update(self):
        if self.state == GameState.MENU:
            self.main_menu.update(self.dt, self.input.get_mouse_pos())
            self.starfield.update(self.dt, 1.0)
        elif self.state == GameState.PLAYING:
            self._update_game(self.dt)
        elif self.state == GameState.PAUSED:
            self.pause_menu.update(self.input.get_mouse_pos())
        elif self.state == GameState.GAMEOVER:
            self.gameover_screen.update(self.dt, self.input.get_mouse_pos(),
                                        self.score, self.wave_mgr.wave, self.max_combo)
            self.particles.update(self.dt)
            self.starfield.update(self.dt)
        elif self.state == GameState.LEADERBOARD:
            self.leaderboard.update(self.input.get_mouse_pos())
        elif self.state == GameState.SETTINGS:
            self.settings.update(self.input.get_mouse_pos())
        elif self.state == GameState.CUSTOMIZE:
            self.customize.update(self.input.get_mouse_pos())
        elif self.state == GameState.REPLAYS:
            self.replay_screen.update(self.input.get_mouse_pos(), self.replays_list)
        elif self.state == GameState.REPLAY_PLAYING:
            self._update_replay(self.dt)

    def _update_game(self, dt):
        actual_dt = dt
        if self.slowmo_timer > 0:
            actual_dt = dt * 0.25
            self.slowmo_timer -= dt

        star_speed = 1.0
        if self.slowmo_timer > 0:
            star_speed = 3.0
        self.starfield.update(actual_dt, star_speed)

        dx1, dy1 = self.input.get_player_movement(0)
        shoot1 = self.input.is_shooting(0)
        shoot1_released = False
        if hasattr(self.input, 'is_shooting_released'):
            try:
                shoot1_released = self.input.is_shooting_released(0)
            except Exception:
                shoot1_released = False
        sw1 = self.input.switch_weapon(0)

        prev_weapon1 = self.player.weapons.current_weapon
        prev_heat1 = self.player.weapons.overheated[prev_weapon1]

        self.player.update(actual_dt, dx1, dy1, shoot1, sw1, self.particles)

        weapon_now1 = self.player.weapons.current_weapon
        try:
            if weapon_now1 == WEAPON_PLASMA:
                if shoot1 and not prev_heat1 and not self.player.weapons.overheated[WEAPON_PLASMA]:
                    self.player.start_plasma_charge()
                    charge = self.player.weapons.plasma_charge
                    if charge > 0.15 and random.random() < 0.5:
                        sp = 1.0
                        cx, cy = self.player.x, self.player.y - self.player.radius * 0.75
                        self.particles.spawn(
                            cx + random.uniform(-6, 6), cy + random.uniform(-6, 6),
                            random.uniform(-40, 40) * sp, random.uniform(-40, 40) * sp,
                            0.25, 2 + charge * 2,
                            (255, random.randint(100, 220), 255), friction=0.92
                        )
                if shoot1_released:
                    fired = self.player.release_plasma_charge(self.bullets, self.enemies)
                    if fired:
                        self.audio.play('plasma_fire')
                        ch = fired[0].plasma_charge_level if hasattr(fired[0], 'plasma_charge_level') else 0.5
                        self.screen_shake = max(self.screen_shake, 5 + ch * 15)
                        for f in fired:
                            self.particles.emit(f.x, f.y, 15 + int(ch * 20),
                                                200 + ch * 200, 0.4 + ch * 0.3,
                                                3 + int(ch * 3),
                                                [(255, 120, 255), (255, 200, 255), WHITE],
                                                friction=0.9)
            else:
                if shoot1:
                    fired = self.player.try_fire(self.bullets, self.enemies)
                    if fired:
                        self.audio.play_fire(self.player.weapons.current_weapon)
        except Exception as _e:
            pass

        if not prev_heat1 and self.player.weapons.overheated[weapon_now1]:
            self.audio.play('overheat')
            self.particles.emit(self.player.x, self.player.y, 20, 120, 0.4, 2, [GRAY, DARK_GRAY])

        wingman_fired = False
        if self.wingman and not self.wingman.dead:
            try:
                dx2, dy2 = self.input.get_player_movement(1)
                shoot2 = self.input.is_shooting(1)
                shoot2_released = False
                if hasattr(self.input, 'is_shooting_released'):
                    try:
                        shoot2_released = self.input.is_shooting_released(1)
                    except Exception:
                        shoot2_released = False
                sw2 = self.input.switch_weapon(1)
                any_input2 = (dx2 != 0 or dy2 != 0 or shoot2 or sw2 != 0)
                self.wingman.update(actual_dt, dx2, dy2, shoot2, sw2,
                                    self.particles, follow_leader=not any_input2)

                w_weapon = self.wingman.weapons.current_weapon
                if w_weapon == WEAPON_PLASMA:
                    if shoot2 and not self.wingman.weapons.overheated[WEAPON_PLASMA]:
                        self.wingman.start_plasma_charge()
                    if shoot2_released:
                        fired2 = self.wingman.release_plasma_charge(self.bullets, self.enemies)
                        if fired2:
                            wingman_fired = True
                            self.audio.play('plasma_fire')
                else:
                    if shoot2:
                        fired2 = self.wingman.try_fire(self.bullets, self.enemies)
                        if fired2:
                            wingman_fired = True
                            self.audio.play_fire(self.wingman.weapons.current_weapon)
                if wingman_fired:
                    pass
            except Exception as _e:
                pass

        hp_ratio = 1.0
        if self.player and not self.player.dead:
            hp_ratio = self.player.hp / max(1, self.player.max_hp)
        current_combo = self.player.combo if self.player else 0
        self.wave_mgr.update(actual_dt, self.enemies, self.particles,
                             player_hp_ratio=hp_ratio, current_combo=current_combo)
        boss = self.wave_mgr.boss
        if boss and not boss.dead:
            try:
                boss.update(actual_dt, self.bullets, self.enemies,
                           self.player, self.wingman, self.particles)
            except Exception as _e:
                pass

        for e in self.enemies:
            try:
                e.update(actual_dt, self.bullets, self.player, self.wingman, self.particles)
            except Exception as _e:
                continue

        for b in self.bullets:
            try:
                b.update(actual_dt, self.particles, self.enemies, self.player)
            except Exception as _e:
                continue

        for p in self.powerups:
            try:
                p.update(actual_dt)
            except Exception as _e:
                continue

        try:
            self._handle_collisions()
        except Exception as _e:
            pass

        try:
            self.bullets = [b for b in self.bullets if not b.dead]
            if len(self.bullets) > MAX_BULLETS:
                self.bullets = self.bullets[-MAX_BULLETS:]
        except Exception:
            self.bullets = []
        try:
            dead_enemies = []
            for e in self.enemies:
                if e.dead:
                    dead_enemies.append(e)
            for e in dead_enemies:
                self.enemies.remove(e)
            if len(self.enemies) > MAX_ENEMIES:
                for e in self.enemies[:-MAX_ENEMIES]:
                    e.dead = True
                self.enemies = self.enemies[-MAX_ENEMIES:]
        except Exception:
            pass
        try:
            self.powerups = [p for p in self.powerups if not p.dead]
        except Exception:
            self.powerups = []

        self.particles.update(actual_dt)

        try:
            self._update_combo_tracking()
        except Exception:
            pass

        try:
            intensity = self._calculate_music_intensity()
            self.audio.update_intensity(intensity)
        except Exception:
            pass

        if self.screen_shake > 0:
            self.screen_shake = max(0, self.screen_shake - actual_dt * 40)

        self._detect_dodges()

        if self.wave_mgr.check_game_over(self.player, self.wingman):
            self._on_game_over()

        frame_data = {
            't': pygame.time.get_ticks(),
            'score': self.score,
            'wave': self.wave_mgr.wave,
            'wave_state': self.wave_mgr.state,
            'p': {'x': self.player.x, 'y': self.player.y, 'hp': self.player.hp,
                  'shield': self.player.shield, 'weapon': self.player.weapons.current_weapon,
                  'combo': self.player.combo, 'charge': self.player.weapons.get_charge_ratio(),
                  'overheat': self.player.weapons.get_heat_ratio()},
        }
        if self.wingman:
            frame_data['w'] = {'x': self.wingman.x, 'y': self.wingman.y,
                               'hp': self.wingman.hp, 'dead': self.wingman.dead,
                               'weapon': self.wingman.weapons.current_weapon,
                               'charge': self.wingman.weapons.get_charge_ratio()}

        e_data = []
        for e in self.enemies[:200]:
            if not e.dead:
                e_data.append({
                    'x': e.x, 'y': e.y, 'k': e.kind, 'r': e.radius,
                    'hp': e.hp / max(1, e.max_hp),
                    'shield': e.shield_hp / max(1, e.max_shield) if e.max_shield > 0 else 0,
                    'alpha': getattr(e, 'stealth_alpha', 255),
                    'color': list(e.color) if hasattr(e, 'color') and isinstance(e.color, (list, tuple)) else None,
                })
        frame_data['enemies'] = e_data

        b_data = []
        for b in self.bullets[:800]:
            if not b.dead:
                owner_tag = 0 if b.owner == 'player' else 1
                kind_tag = 0
                if b.kind == 'plasma':
                    kind_tag = 1
                elif b.kind == 'missile':
                    kind_tag = 2
                elif b.kind == 'laser':
                    kind_tag = 3
                elif b.kind == 'enemy_big':
                    kind_tag = 4
                b_data.append({
                    'x': b.x, 'y': b.y, 'r': b.radius, 'o': owner_tag,
                    'k': kind_tag, 'col': list(b.color) if isinstance(b.color, tuple) else [255, 255, 255],
                    'ch': getattr(b, 'plasma_charge_level', 0),
                })
        frame_data['bullets'] = b_data

        pu_data = []
        for p in self.powerups:
            if not p.dead:
                pu_data.append({'x': p.x, 'y': p.y, 'k': p.kind, 'c': list(p.color)})
        frame_data['powerups'] = pu_data

        if boss and not boss.dead:
            frame_data['boss'] = {
                'x': boss.x, 'y': boss.y, 'r': boss.radius,
                'hp': boss.hp / max(1, boss.max_hp),
                'phase': boss.phase, 'rage': boss.rage_mode,
                'shake': boss.shake_intensity,
                'weak': [{'e': boss.weak_point_exposed[i],
                          'd': boss.weak_points[i]['destroyed'],
                          'hp': boss.weak_points[i]['hp'] / max(1, boss.weak_points[i]['max_hp']),
                          'x': boss.x + math.cos(boss.weak_points[i]['angle']) * boss.weak_points[i]['offset'],
                          'y': boss.y + math.sin(boss.weak_points[i]['angle']) * boss.weak_points[i]['offset']}
                         for i in range(3)]
            }
        else:
            frame_data['boss'] = None

        frame_data['boss_info'] = {
            'phase': boss.phase if boss and not boss.dead else -1,
            'rage': boss.rage_mode if boss and not boss.dead else False,
        }

        frame_data['fx_shake'] = self.screen_shake
        frame_data['fx_slowmo'] = max(0.0, self.slowmo_timer)
        self.recorder.record_frame(frame_data)

    def _handle_collisions(self):
        hit_rects = [self.player.get_hitbox_rect()]
        if self.wingman and not self.wingman.dead:
            hit_rects.append(self.wingman.get_hitbox_rect())
        players = [self.player]
        if self.wingman:
            players.append(self.wingman)

        for b in self.bullets:
            if b.dead:
                continue
            if b.owner == 'player':
                for e in self.enemies:
                    if e.dead:
                        continue
                    if circle_collide(b.x, b.y, b.radius, e.x, e.y, e.radius):
                        sc, hit = e.take_damage(b.damage)
                        if hit:
                            self.particles.hit(b.x, b.y, e.color if hasattr(e, 'color') else WHITE)
                            self.audio.play('hit')
                        if e.dead:
                            self._on_enemy_killed(e, sc)
                        b.dead = True
                        break
                if not b.dead and self.wave_mgr.boss and not self.wave_mgr.boss.dead:
                    boss = self.wave_mgr.boss
                    if circle_collide(b.x, b.y, b.radius, boss.x, boss.y, boss.radius):
                        sc, hit, wp = boss.take_damage(b.damage, b.x, b.y)
                        if wp >= 0:
                            self.screen_shake = max(self.screen_shake, 8)
                            self.particles.emit(b.x, b.y, 20, 350, 0.6, 4,
                                               [YELLOW, ORANGE, WHITE], friction=0.9)
                            self.audio.play('hit')
                        if hit:
                            self.particles.hit(b.x, b.y, YELLOW if wp >= 0 else GRAY)
                        if boss.dead:
                            self._on_boss_killed(boss, sc)
                        b.dead = True
            elif b.owner == 'enemy':
                for i, p in enumerate(players):
                    if p.dead:
                        continue
                    hr = p.get_hitbox_rect()
                    if circle_rect_collide(b.x, b.y, b.radius, *hr):
                        if p.take_damage(b.damage):
                            self.audio.play('player_hit')
                            self.screen_shake = max(self.screen_shake, 10)
                            self.particles.hit(b.x, b.y, RED)
                            self.wave_mgr.register_damage(b.damage)
                        b.dead = True
                        break

        for e in self.enemies:
            if e.dead:
                continue
            for i, p in enumerate(players):
                if p.dead:
                    continue
                if circle_collide(e.x, e.y, e.radius, p.x, p.y, p.radius * 0.9):
                    if p.take_damage(e.contact_damage):
                        self.audio.play('player_hit')
                        self.screen_shake = max(self.screen_shake, 15)
                        self.wave_mgr.register_damage(e.contact_damage)
                    if e.kind == ENEMY_KAMIKAZE:
                        self.particles.explosion(e.x, e.y, count=40, size=5)
                        self.audio.play_explosion(big=False)
                        e.dead = True
                        sc = e.score_value
                        self._on_enemy_killed(e, sc)
                    break

        if self.wave_mgr.boss and not self.wave_mgr.boss.dead:
            boss = self.wave_mgr.boss
            for p in players:
                if p.dead:
                    continue
                if circle_collide(boss.x, boss.y, boss.radius, p.x, p.y, p.radius * 0.9):
                    if p.take_damage(boss.contact_damage):
                        self.audio.play('player_hit')
                        self.screen_shake = max(self.screen_shake, 20)
                        self.wave_mgr.register_damage(boss.contact_damage)

        for pu in self.powerups:
            if pu.dead:
                continue
            for p in players:
                if p.dead:
                    continue
                if circle_collide(pu.x, pu.y, pu.radius, p.x, p.y, p.radius + 5):
                    pu.apply(p, self.wingman, self)
                    self.audio.play('upgrade')
                    self.particles.emit(pu.x, pu.y, 25, 200, 0.5, 3, [pu.color, WHITE], friction=0.92)
                    pu.dead = True
                    break

    def _on_enemy_killed(self, enemy, score_val):
        if not score_val:
            score_val = enemy.score_value
        self.particles.explosion(enemy.x, enemy.y,
                                 count=40 if enemy.radius < 20 else 70,
                                 size=4 if enemy.radius < 20 else 6)
        self.audio.play_explosion(big=enemy.radius >= 25)
        self.screen_shake = max(self.screen_shake, 5 if enemy.radius < 20 else 10)

        try:
            self.wave_mgr.register_kill()
        except Exception:
            pass

        self.player.add_score(score_val, combo_bonus=True)
        self.score = self.player.score
        if self.wingman and not self.wingman.dead:
            self.wingman.add_score(score_val // 2, combo_bonus=True)

        if self.player.combo > self.max_combo:
            self.max_combo = self.player.combo

        if self.player.combo > 0 and self.player.combo % 10 == 0:
            self.hud.trigger_combo_popup(self.player.combo)
            self.audio.play_combo(self.player.combo)

        if self.wingman and not self.wingman.dead:
            self.score = self.player.score + self.wingman.score

        if random.random() < 0.10:
            self._maybe_drop_upgrade(enemy.x, enemy.y)

    def _on_boss_killed(self, boss, score_val):
        for _ in range(12):
            ox = random.uniform(-boss.radius, boss.radius)
            oy = random.uniform(-boss.radius, boss.radius)
            self.particles.big_explosion(boss.x + ox, boss.y + oy)
        self.audio.play('boss_defeated')
        self.screen_shake = 30
        self.score += score_val
        self.player.score += score_val
        self.player.combo += 20
        self.player.add_score(0)

        for wi in range(4):
            self.player.weapons.upgrade_weapon(wi)
            if self.wingman:
                self.wingman.weapons.upgrade_weapon(wi)
        self.player.heal(40)
        if self.wingman:
            self.wingman.heal(40)
        self.audio.play('upgrade')

        for _ in range(3):
            rx = boss.x + random.uniform(-80, 80)
            ry = boss.y + random.uniform(-40, 40)
            self._maybe_drop_upgrade(rx, ry, force_drop=True)

        wave_time = (pygame.time.get_ticks() - self.wave_mgr.wave_start_time) / 1000
        self.wave_mgr.update_performance(
            self.player.hp / self.player.max_hp,
            self.max_combo,
            self.player.combo,
            wave_time
        )

    def _maybe_drop_upgrade(self, x, y, force_drop=False):
        if force_drop or random.random() < 0.6:
            self.powerups.append(PowerUp(x, y))

    def _update_combo_tracking(self):
        self.wave_mgr.register_combo(self.player.combo)

    def _calculate_music_intensity(self):
        intensity = 0.3
        if self.wave_mgr.state == 'boss_fight':
            intensity = 1.0
        elif self.wave_mgr.state in ['spawning', 'clearing']:
            intensity = 0.5 + (len(self.enemies) / max(1, MAX_ENEMIES)) * 0.3
            intensity += min(0.2, self.player.combo / 100)
        return clamp(intensity, 0, 1)

    def _detect_dodges(self):
        if self.player.dead:
            return
        if self.player.dodge_cooldown > 0:
            return

        dodge_threshold = 32
        very_close_threshold = 22
        bullets_near = 0

        current_ids = set()
        for b in self.bullets:
            if b.dead or b.owner != 'enemy':
                continue
            d = distance(b.x, b.y, self.player.x, self.player.y)
            bid = id(b)
            current_ids.add(bid)
            if d < dodge_threshold:
                if bid in self._dodge_bullet_history:
                    prev_d = self._dodge_bullet_history[bid]
                    if prev_d > very_close_threshold and d <= very_close_threshold:
                        bullets_near += 1
            self._dodge_bullet_history[bid] = d

        expired = [k for k in self._dodge_bullet_history if k not in current_ids]
        for k in expired:
            del self._dodge_bullet_history[k]

        if len(self._dodge_bullet_history) > 2000:
            self._dodge_bullet_history.clear()

        if bullets_near >= 2:
            if self.player.register_dodge():
                self.slowmo_timer = 0.8
                self.audio.play('dodge')
                self.hud.trigger_combo_popup("DODGE!")
                self.player.combo += 3
                self.particles.emit(self.player.x, self.player.y, 40, 250, 0.7, 3,
                                   [CYAN, WHITE, BLUE], friction=0.9)

    def _on_game_over(self):
        if self.state != GameState.GAMEOVER:
            duration = (pygame.time.get_ticks() - self.game_start_time) / 1000
            self.recorder.stop({
                'score': self.score,
                'wave': self.wave_mgr.wave,
                'max_combo': self.max_combo,
                'duration': duration
            })
            self.recorder.save()
            self.audio.stop_music()
            self.audio.play('game_over')
            self.is_new_highscore = self.highscores.is_high_score(self.score)
            self._change_state(GameState.GAMEOVER)

    def _update_replay(self, dt):
        frame = self.replay_player.next_frame()
        if frame is None:
            self._change_state(GameState.REPLAYS)
            return
        self.score = frame.get('score', 0)
        self.starfield.update(dt)
        self.particles.update(dt)

    def _draw(self):
        self.screen.fill(BLACK)

        shake_x, shake_y = 0, 0
        if self.screen_shake > 0:
            shake_x = random.randint(-int(self.screen_shake), int(self.screen_shake))
            shake_y = random.randint(-int(self.screen_shake), int(self.screen_shake))

        if self.state == GameState.MENU:
            self.main_menu.draw(self.screen)
        elif self.state == GameState.PLAYING:
            self._draw_game(shake_x, shake_y)
        elif self.state == GameState.PAUSED:
            self._draw_game(0, 0)
            self.pause_menu.draw(self.screen)
        elif self.state == GameState.GAMEOVER:
            self._draw_game(0, 0)
            duration = (pygame.time.get_ticks() - self.game_start_time) / 1000
            self.gameover_screen.draw(self.screen, self.score, self.wave_mgr.wave,
                                       self.max_combo, duration, self.is_new_highscore)
        elif self.state == GameState.LEADERBOARD:
            self.leaderboard.draw(self.screen, self.highscores.get_top(10))
        elif self.state == GameState.SETTINGS:
            self.settings.draw(self.screen)
        elif self.state == GameState.CUSTOMIZE:
            self.customize.draw(self.screen, self._draw_ship_preview)
        elif self.state == GameState.REPLAYS:
            self.replay_screen.draw(self.screen, self.replays_list)
        elif self.state == GameState.REPLAY_PLAYING:
            self._draw_replay()

        if self.slowmo_timer > 0:
            dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(dark, (20, 40, 80, 40), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
            self.screen.blit(dark, (0, 0))

    def _draw_game(self, sx, sy):
        view = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        view.fill(BLACK)

        self.starfield.draw(view)

        for b in self.bullets:
            b.draw(view)
        for e in self.enemies:
            e.draw(view)
        if self.wave_mgr.boss:
            self.wave_mgr.boss.draw(view)

        for pu in self.powerups:
            pu.draw(view)

        self.particles.draw(view)

        if self.player:
            self.player.draw(view)
        if self.wingman:
            self.wingman.draw(view)

        self.hud.update(self.dt)
        self.hud.draw(view, self.player, self.wingman,
                       self.wave_mgr.get_wave_info(), self.score)

        if self.state == GameState.PLAYING and self.wave_mgr.state == 'boss_intro':
            if not hasattr(self, '_boss_snd_played'):
                self._boss_snd_played = True
                self.audio.play('boss_appear')
        elif self.wave_mgr.state == 'spawning' and not hasattr(self, '_wave_snd_played'):
            self._wave_snd_played = True
            self.audio.play('wave_start')

        if self.wave_mgr.state not in ['boss_intro', 'spawning']:
            if hasattr(self, '_boss_snd_played'):
                del self._boss_snd_played
            if hasattr(self, '_wave_snd_played'):
                del self._wave_snd_played

        self.screen.blit(view, (sx, sy))

        if self.slowmo_timer > 0:
            vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            a = int(80 * min(1, self.slowmo_timer / 0.8))
            pygame.draw.circle(vignette, (0, 0, 0, 0),
                               (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
                               SCREEN_HEIGHT // 2)
            for r in range(SCREEN_HEIGHT // 2, max(SCREEN_WIDTH, SCREEN_HEIGHT), 20):
                pygame.draw.circle(vignette, (0, 50, 100, a),
                                   (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), r, 20)
            self.screen.blit(vignette, (0, 0))

    def _draw_replay(self):
        self.starfield.draw(self.screen)
        progress = self.replay_player.get_progress()
        draw_text_outline(self.screen, "REPLAY PLAYBACK", SCREEN_WIDTH // 2,
                          60, 42, PURPLE, BLACK, center=True)
        draw_text(self.screen, "Progress: %d%%   (ESC to exit)" % int(progress * 100),
                  SCREEN_WIDTH // 2, 110, 18, GRAY, center=True)
        pw = SCREEN_WIDTH - 200
        pygame.draw.rect(self.screen, DARK_GRAY, (100, 130, pw, 8), border_radius=4)
        pygame.draw.rect(self.screen, PURPLE, (100, 130, int(pw * progress), 8), border_radius=4)

        fid = max(0, min(self.replay_player.frame_idx - 1, len(self.replay_player.frames) - 1))
        frame = self.replay_player.frames[fid] if self.replay_player.frames else None
        if not frame:
            return

        shake_x = shake_y = 0
        sm = frame.get('fx_shake', 0)
        if sm > 0:
            shake_x = random.randint(-int(sm), int(sm))
            shake_y = random.randint(-int(sm), int(sm))

        view = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        for pu in frame.get('powerups', []):
            try:
                x, y = int(pu['x']), int(pu['y'])
                c = tuple(pu['c']) if 'c' in pu else YELLOW
                r = 12
                pygame.draw.circle(view, c, (x, y), r)
                pygame.draw.circle(view, WHITE, (x, y), r, 2)
            except Exception:
                pass

        for bd in frame.get('bullets', []):
            try:
                x, y = int(bd['x']), int(bd['y'])
                r = max(1, int(bd['r']))
                col = tuple(bd['col']) if 'col' in bd else WHITE
                o = bd.get('o', 0)
                k = bd.get('k', 0)
                if k == 1:
                    ch = bd.get('ch', 0)
                    glow = 4 + int(ch * 6)
                    pygame.draw.circle(view, col, (x, y), r + glow)
                    pygame.draw.circle(view, WHITE, (x, y), max(1, r))
                elif k == 2:
                    pygame.draw.circle(view, col, (x, y), r + 1)
                    pygame.draw.circle(view, WHITE, (x, y), max(1, r - 1))
                elif k == 3:
                    pygame.draw.line(view, col, (x - r * 2, y), (x + r * 2, y), r + 1)
                    pygame.draw.line(view, WHITE, (x - r * 2, y), (x + r * 2, y), max(1, r - 1))
                elif k == 4:
                    pygame.draw.circle(view, col, (x, y), r + 2)
                    pygame.draw.circle(view, WHITE, (x, y), max(1, r))
                else:
                    if o == 0:
                        pygame.draw.circle(view, col, (x, y), r)
                        pygame.draw.circle(view, WHITE, (x, y), max(1, r - 1))
                    else:
                        pygame.draw.circle(view, col, (x, y), r)
            except Exception:
                continue

        for ed in frame.get('enemies', []):
            try:
                x, y = int(ed['x']), int(ed['y'])
                r = max(3, int(ed.get('r', 12)))
                k = ed.get('k', 0)
                colors = [RED, ORANGE, DARK_RED, BLUE, PURPLE, GRAY, CYAN, DARK_GRAY]
                base_c = colors[k] if k < len(colors) else RED
                alpha = ed.get('alpha', 255)
                if alpha < 255:
                    es = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
                    aa = max(20, int(alpha))
                    temp_c = (base_c[0], base_c[1], base_c[2], aa)
                    cx = cy = r * 2
                    pygame.draw.circle(es, temp_c, (cx, cy), r)
                    pygame.draw.circle(es, (255, 255, 255, aa), (cx, cy), r, 2)
                    view.blit(es, (x - r * 2, y - r * 2))
                else:
                    if k == 0:
                        pts = [(x, y + r), (x - int(r * 0.8), y - int(r * 0.2)),
                               (x - int(r * 0.4), y - r), (x + int(r * 0.4), y - r),
                               (x + int(r * 0.8), y - int(r * 0.2))]
                        pygame.draw.polygon(view, base_c, pts, 2)
                    elif k == 1:
                        pts = [(x, y + int(r * 1.2)), (x - r, y - int(r * 0.5)),
                               (x, y), (x + r, y - int(r * 0.5))]
                        pygame.draw.polygon(view, base_c, pts)
                    elif k == 2:
                        pts = [(x, y + r), (x - r, y), (x - int(r * 0.8), y - int(r * 0.8)),
                               (x + int(r * 0.8), y - int(r * 0.8)), (x + r, y)]
                        pygame.draw.polygon(view, base_c, pts, 2)
                    elif k == 3:
                        pygame.draw.ellipse(view, base_c,
                                            (x - r, y - int(r * 0.7), r * 2, int(r * 1.4)), 2)
                    elif k == 4:
                        pts = [(x, y - r), (x + r, y), (x + int(r * 0.6), y + int(r * 0.8)),
                               (x, y + int(r * 0.5)), (x - int(r * 0.6), y + int(r * 0.8)),
                               (x - r, y)]
                        pygame.draw.polygon(view, base_c, pts, 2)
                    elif k == 7:
                        w = r * 2.2
                        h = r * 1.1
                        pts = [(x - int(w * 0.5), y), (x - int(w * 0.3), y - int(h)),
                               (x + int(w * 0.3), y - int(h)), (x + int(w * 0.5), y),
                               (x + int(w * 0.3), y + int(h * 0.6)),
                               (x - int(w * 0.3), y + int(h * 0.6))]
                        pygame.draw.polygon(view, base_c, pts, 2)
                    else:
                        pygame.draw.circle(view, base_c, (x, y), r, 2)

                hp_ratio = ed.get('hp', 1.0)
                if hp_ratio < 0.98:
                    bw = r * 2
                    by = y - r - 8
                    pygame.draw.rect(view, DARK_GRAY, (x - r, by, bw, 3))
                    c2 = GREEN if hp_ratio > 0.5 else (YELLOW if hp_ratio > 0.25 else RED)
                    pygame.draw.rect(view, c2, (x - r, by, int(bw * hp_ratio), 3))

                sh = ed.get('shield', 0)
                if sh > 0.02:
                    sr = int(r * 1.5)
                    pygame.draw.circle(view, CYAN, (x, y), sr, 2)
            except Exception:
                continue

        boss_d = frame.get('boss')
        if boss_d:
            try:
                bx, by = int(boss_d['x']), int(boss_d['y'])
                br = max(40, int(boss_d.get('r', 80)))
                ph = boss_d.get('phase', 0)
                rage = boss_d.get('rage', False)
                base_color = (120, 40, 60) if rage else (80, 50, 100)
                outline_color = RED if rage else PURPLE
                accent = ORANGE if rage else CYAN

                if ph == 0:
                    shape = [
                        (bx - br, by), (bx - int(br * 0.7), by - int(br * 0.8)),
                        (bx, by - br), (bx + int(br * 0.7), by - int(br * 0.8)),
                        (bx + br, by), (bx + int(br * 0.7), by + int(br * 0.5)),
                        (bx, by + int(br * 0.7)), (bx - int(br * 0.7), by + int(br * 0.5)),
                    ]
                elif ph == 1:
                    shape = [
                        (bx - int(br * 1.1), by + int(br * 0.2)),
                        (bx - int(br * 0.9), by - int(br * 0.9)),
                        (bx - int(br * 0.3), by - int(br * 1.1)),
                        (bx + int(br * 0.3), by - int(br * 1.1)),
                        (bx + int(br * 0.9), by - int(br * 0.9)),
                        (bx + int(br * 1.1), by + int(br * 0.2)),
                        (bx + int(br * 0.7), by + int(br * 0.7)),
                        (bx, by + int(br * 0.9)),
                        (bx - int(br * 0.7), by + int(br * 0.7)),
                    ]
                else:
                    spikes = 8
                    shape = []
                    for i in range(spikes * 2):
                        a = (i / (spikes * 2)) * math.pi * 2
                        d = br if i % 2 == 0 else int(br * 0.7)
                        shape.append((bx + math.cos(a) * d, by + math.sin(a) * d))

                pygame.draw.polygon(view, base_color, shape)
                pygame.draw.polygon(view, outline_color, shape, 3)

                core_r = int(br * 0.35)
                core_c = accent if not boss_d.get('hp', 1) < 0.99 else DARK_GRAY
                pygame.draw.circle(view, core_c, (bx, by), core_r + 4)
                pygame.draw.circle(view, WHITE, (bx, by), max(3, core_r - 4))

                for wi, wd in enumerate(boss_d.get('weak', [])):
                    wx, wy = int(wd['x']), int(wd['y'])
                    if wd['d']:
                        pygame.draw.circle(view, DARK_GRAY, (wx, wy), 10)
                        continue
                    if wd['e']:
                        pygame.draw.circle(view, ORANGE, (wx, wy), 18)
                    pygame.draw.circle(view, YELLOW if wd['e'] else GRAY, (wx, wy), 12)
                    pygame.draw.circle(view, WHITE, (wx, wy), 6)
            except Exception:
                pass

        p_d = frame.get('p', {})
        px, py = int(p_d.get('x', 0)), int(p_d.get('y', 0))
        if px and py:
            s = 18
            ch = p_d.get('charge', 0)
            wp = p_d.get('weapon', 0)
            pygame.draw.polygon(view, CYAN, [
                (px, py - s), (px + int(s * 0.7), py),
                (px + int(s * 0.5), py + int(s * 0.6)),
                (px - int(s * 0.5), py + int(s * 0.6)),
                (px - int(s * 0.7), py)
            ], 2)
            if wp == WEAPON_PLASMA and ch > 0.1:
                cr = int(5 + ch * 12)
                pygame.draw.circle(view, PURPLE, (px, py - int(s * 0.9)), cr + 3)
                pygame.draw.circle(view, WHITE, (px, py - int(s * 0.9)), max(1, cr - 1))

            hp = p_d.get('hp', 100) / max(1, PLAYER_MAX_HP if 'PLAYER_MAX_HP' in globals() else 100)
            pygame.draw.rect(view, DARK_GRAY, (px - 24, py + s + 4, 48, 4))
            hc = GREEN if hp > 0.5 else (YELLOW if hp > 0.25 else RED)
            pygame.draw.rect(view, hc, (px - 24, py + s + 4, int(48 * hp), 4))

        w_d = frame.get('w')
        if w_d and not w_d.get('dead', True):
            wx, wy = int(w_d.get('x', 0)), int(w_d.get('y', 0))
            if wx and wy:
                pygame.draw.polygon(view, GREEN, [
                    (wx, wy - 14), (wx + 10, wy),
                    (wx + 7, wy + 8), (wx - 7, wy + 8),
                    (wx - 10, wy)
                ], 2)

        self.screen.blit(view, (shake_x, shake_y))

        slowmo = frame.get('fx_slowmo', 0)
        if slowmo and slowmo > 0:
            vig = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            a = int(50 * min(1.0, slowmo / 0.8))
            for rad in range(SCREEN_HEIGHT // 2, max(SCREEN_WIDTH, SCREEN_HEIGHT), 30):
                pygame.draw.circle(vig, (0, 50, 100, a),
                                   (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), rad, 30)
            self.screen.blit(vig, (0, 0))

        draw_text(self.screen, f"SCORE: {frame.get('score', 0):,}",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80, 24, WHITE, center=True)
        wv = frame.get('wave', 0)
        ws = frame.get('wave_state', '')
        label = f"WAVE: {wv}"
        if ws == 'boss_fight' or frame.get('boss'):
            label += "   [BOSS]"
        draw_text(self.screen, label, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50, 20, CYAN, center=True)
        cmb = p_d.get('combo', 0) if p_d else 0
        if cmb >= 5:
            draw_text(self.screen, f"COMBO x{cmb}", 120, 170,
                      22, YELLOW if cmb < 25 else (ORANGE if cmb < 50 else PINK))

    def _draw_ship_preview(self, surface, cx, cy, body, engine, cockpit, color):
        x, y = cx, cy
        r = 40
        c = color
        if body == 0:
            points = [
                (x, y - r), (x + r * 0.7, y), (x + r * 0.5, y + r * 0.6),
                (x - r * 0.5, y + r * 0.6), (x - r * 0.7, y),
            ]
        elif body == 1:
            points = [
                (x, y - r * 1.1), (x + r * 0.9, y - r * 0.2),
                (x + r * 0.7, y + r * 0.7), (x, y + r * 0.5),
                (x - r * 0.7, y + r * 0.7), (x - r * 0.9, y - r * 0.2),
            ]
        else:
            points = [
                (x, y - r * 1.1), (x + r * 0.5, y - r * 0.6),
                (x + r, y + r * 0.3), (x + r * 0.5, y + r * 0.8),
                (x - r * 0.5, y + r * 0.8), (x - r, y + r * 0.3),
                (x - r * 0.5, y - r * 0.6),
            ]
        sec = (max(0, c[0] - 80), max(0, c[1] - 80), max(0, c[2] - 80))
        pygame.draw.polygon(surface, sec, points)
        pygame.draw.polygon(surface, c, points, 3)
        if engine == 0:
            pygame.draw.rect(surface, sec,
                             (x - r * 0.6, y + r * 0.5, r * 1.2, r * 0.35))
            pygame.draw.rect(surface, c,
                             (x - r * 0.6, y + r * 0.5, r * 1.2, r * 0.35), 2)
        elif engine == 1:
            pygame.draw.rect(surface, sec,
                             (x - r * 0.8, y + r * 0.4, r * 0.45, r * 0.4))
            pygame.draw.rect(surface, sec,
                             (x + r * 0.35, y + r * 0.4, r * 0.45, r * 0.4))
        else:
            for sx in [-0.65, 0, 0.65]:
                pygame.draw.rect(surface, sec,
                                 (x + r * sx - r * 0.15, y + r * 0.45,
                                  r * 0.3, r * 0.4))
        if cockpit == 0:
            pygame.draw.ellipse(surface, WHITE,
                                (x - r * 0.25, y - r * 0.5, r * 0.5, r * 0.6))
        elif cockpit == 1:
            pts = [(x, y - r * 0.7), (x + r * 0.3, y - r * 0.1),
                   (x - r * 0.3, y - r * 0.1)]
            pygame.draw.polygon(surface, WHITE, pts)
        else:
            pygame.draw.rect(surface, WHITE,
                             (x - r * 0.2, y - r * 0.6, r * 0.4, r * 0.5),
                             border_radius=3)


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
