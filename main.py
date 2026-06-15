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
    BOSS_SUMMARY = 9
    BOSS_REWARD = 10


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

        self._replay_explosions = []
        self._replay_hits = []
        self._playing_explosions = []
        self._playing_hits = []

        self.boss_stats = None
        self.boss_reward_data = None

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
        self._replay_explosions.clear()
        self._replay_hits.clear()

        self.boss_stats = None
        self.boss_reward_data = None

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
            self._playing_explosions.clear()
            self._playing_hits.clear()
            self.screen_shake = 0
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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._change_state(GameState.REPLAYS)
                    self.replays_list = self.recorder.list_replays()
                elif event.key == pygame.K_SPACE:
                    self.replay_player.toggle_pause()
                elif event.key == pygame.K_TAB:
                    self.replay_player.cycle_speed()
                elif event.key == pygame.K_LEFT:
                    self.replay_player.step_frame(-10)
                elif event.key == pygame.K_RIGHT:
                    self.replay_player.step_frame(10)
                elif event.key == pygame.K_HOME:
                    self.replay_player.seek_key_frame('start')
                elif event.key == pygame.K_END:
                    self.replay_player.seek_key_frame('end')
                elif event.key == pygame.K_F1:
                    self.replay_player.seek_key_frame('boss_appear')
                elif event.key == pygame.K_F2:
                    self.replay_player.seek_phase(1)
                elif event.key == pygame.K_F3:
                    self.replay_player.seek_phase(2)
                elif event.key == pygame.K_F4:
                    self.replay_player.seek_key_frame('boss_defeat')
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if 100 <= my <= 145 and 100 <= mx <= SCREEN_WIDTH - 100:
                    pct = (mx - 100) / max(1, SCREEN_WIDTH - 200)
                    self.replay_player.seek_percent(clamp(pct, 0, 1))
        elif self.state == GameState.BOSS_REWARD:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.boss_reward_data and self.boss_reward_data['stage'] >= 4:
                        self._change_state(GameState.BOSS_SUMMARY)
                elif event.key == pygame.K_ESCAPE:
                    self._change_state(GameState.BOSS_SUMMARY)
        elif self.state == GameState.BOSS_SUMMARY:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE or event.key == pygame.K_ESCAPE:
                    self.boss_stats = None
                    self.boss_reward_data = None
                    self._change_state(GameState.PLAYING)

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
        elif self.state == GameState.BOSS_REWARD:
            self._update_boss_reward(self.dt)
        elif self.state == GameState.BOSS_SUMMARY:
            self._update_boss_summary(self.dt)

    def _update_game(self, dt):
        try:
            if self.wave_mgr.state == 'boss_fight' and self.boss_stats is None:
                self.boss_stats = {
                    'start_time': pygame.time.get_ticks(),
                    'end_time': 0,
                    'total_damage': 0,
                    'weapon_damage': [0, 0, 0, 0],
                    'weapon_fire_count': [0, 0, 0, 0],
                    'weak_hit_count': 0,
                    'weak_destroy_count': [0, 0, 0],
                    'weak_destroyed_before': [False, False, False],
                    'player_hit_count': 0,
                    'boss_max_hp': 0,
                }
                if self.wave_mgr.boss:
                    self.boss_stats['boss_max_hp'] = self.wave_mgr.boss.max_hp
                    for i in range(3):
                        self.boss_stats['weak_destroyed_before'][i] = self.wave_mgr.boss.weak_points[i]['destroyed']
        except Exception:
            pass

        actual_dt = dt
        if self.slowmo_timer > 0:
            actual_dt = dt * 0.25
            self.slowmo_timer -= dt

        star_speed = 1.0
        if self.slowmo_timer > 0:
            star_speed = 3.0
        try:
            self.starfield.update(actual_dt, star_speed)
        except Exception:
            pass

        dx1, dy1 = 0, 0
        shoot1 = False
        shoot1_released = False
        sw1 = 0
        try:
            dx1, dy1 = self.input.get_player_movement(0)
            shoot1 = self.input.is_shooting(0)
            sw1 = self.input.switch_weapon(0)
        except Exception:
            dx1, dy1, shoot1, sw1 = 0, 0, False, 0
        if hasattr(self.input, 'is_shooting_released'):
            try:
                shoot1_released = self.input.is_shooting_released(0)
            except Exception:
                shoot1_released = False

        prev_weapon1 = self.player.weapons.current_weapon
        prev_heat1 = self.player.weapons.overheated[prev_weapon1]

        try:
            self.player.update(actual_dt, dx1, dy1, shoot1, sw1, self.particles)
        except Exception:
            pass

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

        try:
            if not prev_heat1 and self.player.weapons.overheated[weapon_now1]:
                self.audio.play('overheat')
                self.particles.emit(self.player.x, self.player.y, 20, 120, 0.4, 2, [GRAY, DARK_GRAY])
        except Exception:
            pass

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

        try:
            self.particles.update(actual_dt)
        except Exception:
            pass

        try:
            self._update_combo_tracking()
        except Exception:
            pass

        try:
            intensity = self._calculate_music_intensity()
            self.audio.update_intensity(intensity)
        except Exception:
            pass

        try:
            if self.screen_shake > 0:
                self.screen_shake = max(0, self.screen_shake - actual_dt * 40)
        except Exception:
            pass

        try:
            self._detect_dodges()
        except Exception:
            pass

        try:
            if self.wave_mgr.check_game_over(self.player, self.wingman):
                self._on_game_over()
        except Exception:
            pass

        try:
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
                    try:
                        e_data.append({
                            'x': e.x, 'y': e.y, 'k': e.kind, 'r': e.radius,
                            'hp': e.hp / max(1, e.max_hp),
                            'shield': e.shield_hp / max(1, e.max_shield) if e.max_shield > 0 else 0,
                            'alpha': getattr(e, 'stealth_alpha', 255),
                            'color': list(e.color) if hasattr(e, 'color') and isinstance(e.color, (list, tuple)) else None,
                        })
                    except Exception:
                        continue
            frame_data['enemies'] = e_data

            b_data = []
            for b in self.bullets[:800]:
                if not b.dead:
                    try:
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
                    except Exception:
                        continue
            frame_data['bullets'] = b_data

            pu_data = []
            for p in self.powerups:
                if not p.dead:
                    try:
                        pu_data.append({'x': p.x, 'y': p.y, 'k': p.kind, 'c': list(p.color)})
                    except Exception:
                        continue
            frame_data['powerups'] = pu_data

            if boss and not boss.dead:
                try:
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
                except Exception:
                    frame_data['boss'] = None
            else:
                frame_data['boss'] = None

            try:
                frame_data['boss_info'] = {
                    'phase': boss.phase if boss and not boss.dead else -1,
                    'rage': boss.rage_mode if boss and not boss.dead else False,
                }
            except Exception:
                frame_data['boss_info'] = {'phase': -1, 'rage': False}

            frame_data['fx_shake'] = self.screen_shake
            frame_data['fx_slowmo'] = max(0.0, self.slowmo_timer)

            if hasattr(self, '_replay_explosions') and self._replay_explosions:
                frame_data['explosions'] = list(self._replay_explosions)
                self._replay_explosions.clear()
            else:
                frame_data['explosions'] = []

            if hasattr(self, '_replay_hits') and self._replay_hits:
                frame_data['hits'] = list(self._replay_hits)
                self._replay_hits.clear()
            else:
                frame_data['hits'] = []
        except Exception:
            frame_data = {'t': pygame.time.get_ticks(), 'score': self.score, 'wave': 1,
                          'wave_state': '', 'p': {'x': SCREEN_WIDTH//2, 'y': SCREEN_HEIGHT-100,
                          'hp': 100, 'shield': 0, 'weapon': 0, 'combo': 0, 'charge': 0, 'overheat': 0},
                          'enemies': [], 'bullets': [], 'powerups': [], 'boss': None,
                          'boss_info': {'phase': -1, 'rage': False},
                          'fx_shake': 0, 'fx_slowmo': 0, 'explosions': [], 'hits': []}
        try:
            self.recorder.record_frame(frame_data)
        except Exception:
            pass

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
                            hc = e.color if hasattr(e, 'color') else WHITE
                            self.particles.hit(b.x, b.y, hc)
                            self.audio.play('hit')
                            try:
                                self._replay_hits.append({
                                    'x': b.x, 'y': b.y, 'c': list(hc) if isinstance(hc, tuple) else [255, 255, 255], 's': 1
                                })
                            except Exception:
                                pass
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
                            hc2 = YELLOW if wp >= 0 else GRAY
                            self.particles.hit(b.x, b.y, hc2)
                            try:
                                self._replay_hits.append({
                                    'x': b.x, 'y': b.y,
                                    'c': list(hc2), 's': 3 if wp >= 0 else 1
                                })
                            except Exception:
                                pass
                            try:
                                if self.boss_stats is not None:
                                    wt = getattr(b, 'weapon_type', 0)
                                    self.boss_stats['total_damage'] += int(b.damage)
                                    if 0 <= wt < 4:
                                        self.boss_stats['weapon_damage'][wt] += int(b.damage)
                                        self.boss_stats['weapon_fire_count'][wt] += 1
                                    if wp >= 0:
                                        self.boss_stats['weak_hit_count'] += 1
                                        if 0 <= wp < 3 and not self.boss_stats['weak_destroyed_before'][wp] and boss.weak_points[wp]['destroyed']:
                                            self.boss_stats['weak_destroy_count'][wp] = 1
                                            self.boss_stats['weak_destroyed_before'][wp] = True
                            except Exception:
                                pass
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
                            try:
                                self._replay_hits.append({
                                    'x': b.x, 'y': b.y, 'c': list(RED), 's': 2
                                })
                            except Exception:
                                pass
                            self.wave_mgr.register_damage(b.damage)
                            try:
                                if self.boss_stats is not None and self.wave_mgr.state == 'boss_fight':
                                    self.boss_stats['player_hit_count'] += 1
                            except Exception:
                                pass
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
        big = enemy.radius >= 25
        self.particles.explosion(enemy.x, enemy.y,
                                 count=40 if enemy.radius < 20 else 70,
                                 size=4 if enemy.radius < 20 else 6)
        self.audio.play_explosion(big=big)
        self.screen_shake = max(self.screen_shake, 5 if enemy.radius < 20 else 10)

        try:
            self._replay_explosions.append({
                'x': enemy.x, 'y': enemy.y,
                'size': 2 if enemy.radius < 25 else 3,
                't': 0,
            })
        except Exception:
            pass

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
        for i in range(20):
            angle = (i / 20) * math.pi * 2 + random.uniform(-0.2, 0.2)
            dist = random.uniform(boss.radius * 0.2, boss.radius * 0.9)
            ox = math.cos(angle) * dist
            oy = math.sin(angle) * dist
            self.particles.big_explosion(boss.x + ox, boss.y + oy)
            try:
                self._replay_explosions.append({
                    'x': boss.x + ox, 'y': boss.y + oy,
                    'size': 5 if i % 4 == 0 else (4 if i % 3 == 0 else 3),
                    't': 0,
                })
            except Exception:
                pass
        for i in range(8):
            ox = random.uniform(-boss.radius * 0.5, boss.radius * 0.5)
            oy = random.uniform(-boss.radius * 0.5, boss.radius * 0.5)
            try:
                self._replay_explosions.append({
                    'x': boss.x + ox, 'y': boss.y + oy,
                    'size': 6,
                    't': 0,
                })
            except Exception:
                pass
        try:
            self._replay_explosions.append({
                'x': boss.x, 'y': boss.y, 'size': 8, 't': 0,
            })
            self._replay_explosions.append({
                'x': boss.x, 'y': boss.y, 'size': 10, 't': 0,
            })
        except Exception:
            pass
        self.audio.play('boss_defeated')
        self.screen_shake = 30

        boss_final_score = boss.score_value
        self.score += boss_final_score
        self.player.score += boss_final_score
        self.player.combo += 20
        self.player.add_score(0)

        wave_time = (pygame.time.get_ticks() - self.wave_mgr.wave_start_time) / 1000
        if self.boss_stats is not None:
            self.boss_stats['end_time'] = pygame.time.get_ticks()
            self.boss_stats['duration'] = (self.boss_stats['end_time'] - self.boss_stats['start_time']) / 1000.0
            self.boss_stats['final_score'] = boss_final_score

        self.boss_reward_data = {
            'score': boss_final_score,
            'heal': 40,
            'weapon_upgrades': 4,
            'drops': 3,
            'wave': self.wave_mgr.wave,
            'elapsed': wave_time,
            'timer': 0,
            'stage': 0,
        }

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

        self.wave_mgr.update_performance(
            self.player.hp / self.player.max_hp,
            self.max_combo,
            self.player.combo,
            wave_time
        )

        self._change_state(GameState.BOSS_REWARD)

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

        try:
            self.screen_shake = frame.get('fx_shake', 0)
        except Exception:
            self.screen_shake = 0

        try:
            for ex in frame.get('explosions', []):
                sz = ex.get('size', 2)
                life = 0.6 if sz < 5 else (1.0 if sz < 8 else 1.3)
                self._playing_explosions.append({
                    'x': ex['x'], 'y': ex['y'],
                    'size': sz,
                    'life': life, 'max': life,
                })
        except Exception:
            pass

        try:
            for ht in frame.get('hits', []):
                self._playing_hits.append({
                    'x': ht['x'], 'y': ht['y'],
                    'c': ht.get('c', [255, 255, 255]),
                    's': ht.get('s', 1),
                    'life': 0.18, 'max': 0.18,
                })
        except Exception:
            pass

        try:
            for e in self._playing_explosions:
                e['life'] -= dt
            self._playing_explosions = [e for e in self._playing_explosions if e['life'] > 0]
        except Exception:
            self._playing_explosions = []

        try:
            for h in self._playing_hits:
                h['life'] -= dt
            self._playing_hits = [h for h in self._playing_hits if h['life'] > 0]
        except Exception:
            self._playing_hits = []

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
        elif self.state == GameState.BOSS_REWARD:
            self._draw_game(0, 0)
            self._draw_boss_reward()
        elif self.state == GameState.BOSS_SUMMARY:
            self._draw_game(0, 0)
            self._draw_boss_summary()

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
        kf = self.replay_player.key_frames
        draw_text_outline(self.screen, "REPLAY PLAYBACK", SCREEN_WIDTH // 2,
                          35, 36, PURPLE, BLACK, center=True)
        time_label = self.replay_player.get_time_str()
        paused = self.replay_player.paused
        speed_label = self.replay_player.get_speed_label()
        status = "[PAUSED]  SPACE" if paused else "[PLAYING] SPACE=pause"
        draw_text(self.screen, f"{status}   |   TAB=speed {speed_label}   |   {time_label}",
                  SCREEN_WIDTH // 2, 70, 16, GRAY, center=True)

        pw = SCREEN_WIDTH - 200
        pygame.draw.rect(self.screen, DARK_GRAY, (100, 100, pw, 14), border_radius=4)
        try:
            if kf.get('boss_appear', -1) >= 0 and self.replay_player.frames:
                xp = 100 + int(pw * (kf['boss_appear'] / max(1, len(self.replay_player.frames) - 1)))
                pygame.draw.line(self.screen, CYAN, (xp, 95), (xp, 119), 2)
            for ph_num, ph_idx in kf.get('phase_change', {}).items():
                if self.replay_player.frames and ph_idx >= 0:
                    xp = 100 + int(pw * (ph_idx / max(1, len(self.replay_player.frames) - 1)))
                    pygame.draw.line(self.screen, ORANGE, (xp, 95), (xp, 119), 2)
            if kf.get('boss_defeat', -1) >= 0 and self.replay_player.frames:
                xp = 100 + int(pw * (kf['boss_defeat'] / max(1, len(self.replay_player.frames) - 1)))
                pygame.draw.line(self.screen, YELLOW, (xp, 95), (xp, 119), 3)
        except Exception:
            pass
        pygame.draw.rect(self.screen, PURPLE, (100, 100, int(pw * progress), 14), border_radius=4)
        try:
            cpx = 100 + int(pw * progress)
            pygame.draw.circle(self.screen, WHITE, (cpx, 107), 7)
        except Exception:
            pass

        draw_text(self.screen,
                  "F1=Boss Appear   F2=Phase 1   F3=Phase 2   F4=Boss Defeat   Home=Start   End=End   ←/→=±10 frames   Click bar=seek",
                  SCREEN_WIDTH // 2, 135, 14, (180, 180, 180), center=True)
        if kf.get('boss_appear', -1) >= 0:
            draw_text(self.screen, "Boss", 100 + int(pw * (kf['boss_appear'] / max(1, len(self.replay_player.frames) - 1))), 86, 12, CYAN, center=True)
        if kf.get('boss_defeat', -1) >= 0:
            draw_text(self.screen, "Defeat", 100 + int(pw * (kf['boss_defeat'] / max(1, len(self.replay_player.frames) - 1))), 86, 12, YELLOW, center=True)
        try:
            for ph_num, ph_idx in kf.get('phase_change', {}).items():
                if ph_idx >= 0 and self.replay_player.frames:
                    draw_text(self.screen, f"P{ph_num+1}",
                              100 + int(pw * (ph_idx / max(1, len(self.replay_player.frames) - 1))),
                              86, 12, ORANGE, center=True)
        except Exception:
            pass

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

        try:
            for ex in self._playing_explosions:
                t = ex['life'] / max(0.01, ex['max'])
                alpha = int(255 * max(0, t))
                sz = ex.get('size', 2)
                r0 = int(8 * sz + (1.0 - t) * 35 * sz)
                r1 = int(5 * sz + (1.0 - t) * 22 * sz)
                r2 = int(3 * sz + (1.0 - t) * 12 * sz)
                es = pygame.Surface((r0 * 2 + 20, r0 * 2 + 20), pygame.SRCALPHA)
                cx, cy = r0 + 10, r0 + 10
                if sz >= 5:
                    pygame.draw.circle(es, (255, 100, 30, int(alpha * 0.5)), (cx, cy), r0 + 8)
                    pygame.draw.circle(es, (255, 180, 60, int(alpha * 0.7)), (cx, cy), r0)
                    pygame.draw.circle(es, (255, 240, 180, int(alpha * 0.9)), (cx, cy), r1)
                    pygame.draw.circle(es, (255, 255, 255, int(alpha * 0.8)), (cx, cy), r2)
                    if t > 0.5:
                        pygame.draw.circle(es, (255, 255, 200, int(alpha * 0.4)), (cx, cy), r2 // 2)
                else:
                    pygame.draw.circle(es, (255, 180, 60, alpha), (cx, cy), r0)
                    pygame.draw.circle(es, (255, 240, 180, int(alpha * 0.9)), (cx, cy), r1)
                    pygame.draw.circle(es, (255, 255, 255, int(alpha * 0.6)), (cx, cy), max(1, r2))
                self.screen.blit(es, (int(ex['x']) - r0 - 10, int(ex['y']) - r0 - 10))
        except Exception:
            pass

        try:
            for ht in self._playing_hits:
                t = ht['life'] / max(0.01, ht['max'])
                alpha = int(255 * t)
                cs = ht.get('c', [255, 255, 255])
                s = ht.get('s', 1)
                r = int(4 + (1.0 - t) * 10 * s)
                hs = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
                pygame.draw.circle(hs, (int(cs[0]), int(cs[1]), int(cs[2]), alpha),
                                   (r + 3, r + 3), r)
                pygame.draw.circle(hs, (255, 255, 255, int(alpha * 0.9)),
                                   (r + 3, r + 3), max(1, r // 2))
                self.screen.blit(hs, (int(ht['x']) - r - 3, int(ht['y']) - r - 3))
        except Exception:
            pass

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

    def _update_boss_reward(self, dt):
        if not self.boss_reward_data:
            self._change_state(GameState.BOSS_SUMMARY)
            return
        self.boss_reward_data['timer'] += dt
        try:
            self.particles.update(dt)
        except Exception:
            pass
        try:
            self.starfield.update(dt, 1.5)
        except Exception:
            pass
        if self.screen_shake > 0:
            self.screen_shake = max(0, self.screen_shake - dt * 30)
        stages_delay = [0.3, 1.0, 1.8, 2.6, 3.5]
        t = self.boss_reward_data['timer']
        for i in range(len(stages_delay)):
            if t >= stages_delay[i] and self.boss_reward_data['stage'] < i + 1:
                self.boss_reward_data['stage'] = i + 1
                if i == 0:
                    try:
                        self.audio.play('upgrade')
                    except Exception:
                        pass
                elif i >= 4:
                    pass

    def _draw_boss_reward(self):
        if not self.boss_reward_data:
            return
        rd = self.boss_reward_data
        t = rd['timer']
        stage = rd['stage']
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 160), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        cy = 180
        title_color = YELLOW if t > 0.5 else WHITE
        draw_text_outline(self.screen, "★ BOSS DEFEATED ★", cx, cy,
                          56 if stage >= 1 else 40, title_color, BLACK, center=True)

        wave_label = f"WAVE {rd['wave']} CLEAR"
        draw_text(self.screen, wave_label, cx, cy + 65, 24, CYAN, center=True)

        duration_str = f"Battle Time: {rd['elapsed']:.1f}s"
        draw_text(self.screen, duration_str, cx, cy + 100, 18, (200, 200, 200), center=True)

        items_y = cy + 165
        if stage >= 1:
            items = [
                ("+{} SCORE".format(rd['score']), YELLOW, 0),
                ("+{} HP HEAL".format(rd['heal']), GREEN, 1),
                ("+4 WEAPON UPGRADES", CYAN, 2),
                ("+{} DROPS".format(rd['drops']), ORANGE, 3),
            ]
            for label, color, idx in items:
                if stage >= idx + 1:
                    yy = items_y + idx * 42
                    alpha = min(1.0, (t - (0.3 + idx * 0.6)) / 0.3)
                    if alpha > 0:
                        s = pygame.Surface((400, 36), pygame.SRCALPHA)
                        a = int(220 * alpha)
                        pygame.draw.rect(s, (40, 40, 70, a), (0, 0, 400, 36), border_radius=8)
                        pygame.draw.rect(s, (*color[:3], int(180 * alpha)), (0, 0, 400, 36), 2, border_radius=8)
                        self.screen.blit(s, (cx - 200, yy - 18))
                        draw_text(self.screen, label, cx, yy, 22, (*color[:3], int(255 * alpha)) if isinstance(color, tuple) and len(color) >= 3 else color, center=True)

        if stage >= 4:
            hint_y = SCREEN_HEIGHT - 100
            draw_text(self.screen, "PRESS [ENTER / SPACE] TO VIEW SUMMARY",
                      cx, hint_y, 20, WHITE, center=True)
            draw_text(self.screen, "NEXT WAVE WILL START AUTOMATICALLY",
                      cx, hint_y + 30, 14, GRAY, center=True)

    def _update_boss_summary(self, dt):
        try:
            self.particles.update(dt)
        except Exception:
            pass
        try:
            self.starfield.update(dt, 1.2)
        except Exception:
            pass

    def _draw_boss_summary(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 190), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        draw_text_outline(self.screen, "COMBAT ANALYSIS", cx, 70, 40, ORANGE, BLACK, center=True)

        stats = self.boss_stats if self.boss_stats else {}
        if not stats:
            draw_text(self.screen, "No battle data available", cx, 200, 24, GRAY, center=True)
            return

        duration = stats.get('duration', 0)
        total_dmg = stats.get('total_damage', 0)
        weak_hits = stats.get('weak_hit_count', 0)
        weak_destroyed = sum(stats.get('weak_destroy_count', [0, 0, 0]))
        player_hits = stats.get('player_hit_count', 0)
        boss_max_hp = stats.get('boss_max_hp', 1)
        dmg_ratio = min(1.0, total_dmg / max(1, boss_max_hp))

        left_col = 220
        right_col = SCREEN_WIDTH - 220
        header_y = 140
        row_h = 38

        labels_data = [
            ("Battle Duration", f"{duration:.1f}s", CYAN),
            ("Total Damage", f"{total_dmg:,}", YELLOW),
            ("% of Max HP", f"{dmg_ratio * 100:.1f}%", GREEN),
            ("Weak Point Hits", f"{weak_hits}", ORANGE),
            ("Weak Points Destroyed", f"{weak_destroyed} / 3", PINK),
            ("Player Hits Taken", f"{player_hits}", RED),
        ]

        for i, (label, val, col) in enumerate(labels_data):
            yy = header_y + i * row_h
            if i < 3:
                xx = left_col
            else:
                xx = right_col
                yy = header_y + (i - 3) * row_h
            draw_text(self.screen, label, xx, yy, 18, (180, 180, 180))
            draw_text(self.screen, val, xx, yy + 22, 24, col)

        wpn_y = header_y + 4 * row_h
        draw_text_outline(self.screen, "WEAPON DAMAGE BREAKDOWN", cx, wpn_y - 10, 22, PURPLE, BLACK, center=True)

        wpn_names = ["LASER", "SPREAD", "MISSILE", "PLASMA"]
        wpn_colors = [CYAN, YELLOW, ORANGE, PURPLE]
        wpn_dmg = stats.get('weapon_damage', [0, 0, 0, 0])
        wpn_fire = stats.get('weapon_fire_count', [0, 0, 0, 0])
        total_wpn = sum(wpn_dmg)

        bar_x = 200
        bar_w = SCREEN_WIDTH - 400
        bar_h = 22
        for i in range(4):
            yy = wpn_y + 20 + i * 45
            ratio = wpn_dmg[i] / max(1, total_wpn) if total_wpn > 0 else 0
            draw_text(self.screen, wpn_names[i], bar_x, yy + 10, 16, wpn_colors[i])
            bar_start_x = bar_x + 110
            bw = bar_w - 110
            pygame.draw.rect(self.screen, DARK_GRAY, (bar_start_x, yy, bw, bar_h), border_radius=4)
            fill_w = int(bw * ratio)
            pygame.draw.rect(self.screen, wpn_colors[i], (bar_start_x, yy, fill_w, bar_h), border_radius=4)
            dmg_label = f"{wpn_dmg[i]:,} dmg  ({wpn_fire[i]} hits)  {ratio * 100:.0f}%"
            draw_text(self.screen, dmg_label, bar_start_x + bw // 2, yy + 12, 14, WHITE, center=True)

        grade = "S" if dmg_ratio > 0.95 and player_hits <= 3 and weak_destroyed >= 3 else (
                "A" if dmg_ratio > 0.8 and player_hits <= 6 else (
                "B" if dmg_ratio > 0.6 else (
                "C" if dmg_ratio > 0.4 else "D")))
        grade_colors = {"S": PINK, "A": YELLOW, "B": GREEN, "C": CYAN, "D": GRAY}
        draw_text_outline(self.screen, f"GRADE: {grade}", cx, wpn_y + 220,
                          72, grade_colors.get(grade, WHITE), BLACK, center=True)

        hint_y = SCREEN_HEIGHT - 60
        draw_text(self.screen, "PRESS [ENTER / SPACE / ESC] TO CONTINUE TO NEXT WAVE",
                  cx, hint_y, 18, WHITE, center=True)


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
