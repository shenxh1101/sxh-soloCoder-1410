import math
import random
import pygame
from config import *
from utils import *


class Button:
    def __init__(self, x, y, w, h, text, callback=None, color=DARK_GRAY,
                 hover_color=GRAY, text_color=WHITE, font_size=24, center=True):
        self.x = x - w // 2 if center else x
        self.y = y - h // 2 if center else y
        self.w = w
        self.h = h
        self.text = text
        self.callback = callback
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.font_size = font_size
        self.hovered = False
        self.clicked = False
        self.enabled = True

    def handle_event(self, event):
        if not self.enabled:
            return False
        mx, my = pygame.mouse.get_pos()
        self.hovered = self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.hovered:
            self.clicked = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.hovered and self.clicked:
            self.clicked = False
            if self.callback:
                self.callback()
            return True
        if event.type == pygame.MOUSEBUTTONUP:
            self.clicked = False
        return False

    def update(self, mouse_pos):
        mx, my = mouse_pos
        self.hovered = self.enabled and self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h

    def draw(self, surface):
        c = self.hover_color if (self.hovered or self.clicked) and self.enabled else self.color
        if not self.enabled:
            c = (40, 40, 40)
        border_c = WHITE if self.hovered and self.enabled else (100, 100, 100)
        pygame.draw.rect(surface, c, (self.x, self.y, self.w, self.h), border_radius=6)
        pygame.draw.rect(surface, border_c, (self.x, self.y, self.w, self.h), 2, border_radius=6)
        tc = self.text_color if self.enabled else (150, 150, 150)
        draw_text(surface, self.text, self.x + self.w // 2, self.y + self.h // 2,
                  self.font_size, tc, center=True)

    def set_enabled(self, enabled):
        self.enabled = enabled


class MainMenu:
    def __init__(self, on_start, on_leaderboard, on_replays, on_settings, on_customize, on_coop):
        self.buttons = []
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2 - 30
        spacing = 75
        self.buttons.append(Button(cx, cy - spacing * 2, 320, 60, "SINGLE PLAYER", on_start, font_size=26))
        self.buttons.append(Button(cx, cy - spacing, 320, 60, "CO-OP MODE", on_coop, color=(40, 80, 60), hover_color=(60, 120, 90), font_size=26))
        self.buttons.append(Button(cx, cy, 320, 60, "CUSTOMIZE SHIP", on_customize, font_size=26))
        self.buttons.append(Button(cx, cy + spacing, 320, 60, "LEADERBOARD", on_leaderboard, font_size=26))
        self.buttons.append(Button(cx, cy + spacing * 2, 320, 60, "REPLAYS", on_replays, font_size=26))
        self.buttons.append(Button(cx, cy + spacing * 3, 320, 60, "SETTINGS", on_settings, font_size=26))

        self.title_timer = 0
        self.stars = []
        for _ in range(150):
            self.stars.append({
                'x': random.uniform(0, SCREEN_WIDTH),
                'y': random.uniform(0, SCREEN_HEIGHT),
                's': random.randint(1, 3),
                'v': random.uniform(30, 120)
            })

    def handle_event(self, event):
        for b in self.buttons:
            if b.handle_event(event):
                return True
        return False

    def update(self, dt, mouse_pos):
        self.title_timer += dt
        for b in self.buttons:
            b.update(mouse_pos)
        for s in self.stars:
            s['y'] += s['v'] * dt
            if s['y'] > SCREEN_HEIGHT:
                s['y'] = -5
                s['x'] = random.uniform(0, SCREEN_WIDTH)

    def draw(self, surface):
        for s in self.stars:
            c = (180, 180, 220) if s['s'] > 2 else (100, 100, 140) if s['s'] > 1 else (60, 60, 90)
            pygame.draw.rect(surface, c, (int(s['x']), int(s['y']), s['s'], s['s']))

        title_y = 120 + math.sin(self.title_timer * 2) * 8
        draw_text_outline(surface, "RETRO SPACE", SCREEN_WIDTH // 2, title_y, 72, CYAN, BLACK, center=True)
        draw_text_outline(surface, "BLASTER", SCREEN_WIDTH // 2, title_y + 70, 64, YELLOW, BLACK, center=True)

        for b in self.buttons:
            b.draw(surface)

        draw_text(surface, "WASD / Arrows: Move  |  Space: Fire  |  Q/E: Switch Weapon  |  ESC: Pause",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60, 16, GRAY, center=True)
        draw_text(surface, "v1.0  |  Press ENTER or Click Start",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30, 14, DARK_GRAY, center=True)


class HUD:
    def __init__(self):
        self.flash = 0
        self.combo_popup_timer = 0
        self.combo_popup_value = 0

    def trigger_combo_popup(self, combo):
        self.combo_popup_timer = 1.2
        self.combo_popup_value = combo

    def update(self, dt):
        if self.flash > 0:
            self.flash -= dt
        if self.combo_popup_timer > 0:
            self.combo_popup_timer -= dt

    def draw(self, surface, player, wingman=None, wave_info=None, score=0):
        self._draw_player_bar(surface, 20, 20, player, 0)
        if wingman and not wingman.dead:
            self._draw_player_bar(surface, SCREEN_WIDTH - 20 - 320, 20, wingman, 1)

        self._draw_score_wave(surface, score, wave_info)

        is_str_popup = isinstance(self.combo_popup_value, str)
        show_popup = False
        if is_str_popup and self.combo_popup_timer > 0:
            show_popup = True
        elif not is_str_popup and self.combo_popup_timer > 0 and self.combo_popup_value >= 10:
            show_popup = True

        if show_popup:
            t = self.combo_popup_timer
            alpha = 1.0 if t > 0.5 else t * 2
            y_off = (1.0 - t) * 40
            if is_str_popup:
                size = 56
                c = CYAN
                draw_text_outline(surface, str(self.combo_popup_value),
                                  SCREEN_WIDTH // 2, 180 - y_off, size, c, BLACK, center=True)
            else:
                size = 48
                if self.combo_popup_value >= 50:
                    size = 64
                    c = PINK
                elif self.combo_popup_value >= 25:
                    size = 56
                    c = ORANGE
                else:
                    c = YELLOW
                draw_text_outline(surface, f"x{self.combo_popup_value} COMBO!",
                                  SCREEN_WIDTH // 2, 180 - y_off, size, c, BLACK, center=True)
                if self.combo_popup_value >= 10:
                    draw_text(surface, "+%d%% BONUS" % int(min(200, self.combo_popup_value * 5)),
                              SCREEN_WIDTH // 2, 180 - y_off + size, 20, GREEN, center=True)

        if player.dodge_slowmo > 0:
            t = player.dodge_slowmo
            draw_text_outline(surface, "DODGE!", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 80,
                              64, CYAN, BLACK, center=True)
            draw_text(surface, "PERFECT EVADE", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30,
                      28, WHITE, center=True)

        if player.weapons.overheated[player.weapons.current_weapon]:
            draw_text(surface, "OVERHEAT!", SCREEN_WIDTH // 2, 320, 32, RED, center=True)

    def _draw_player_bar(self, surface, x, y, p, idx=0):
        w, h = 320, 70
        color = CYAN if idx == 0 else GREEN
        color2 = BLUE if idx == 0 else DARK_GREEN

        pygame.draw.rect(surface, (10, 10, 20, 200), (x, y, w, h), border_radius=8)
        pygame.draw.rect(surface, color, (x, y, w, h), 2, border_radius=8)

        label = "P1" if idx == 0 else "P2"
        draw_text(surface, label, x + 12, y + 10, 16, color)

        hp_ratio = p.hp / p.max_hp
        bar_w = w - 110
        bar_h = 14
        bx, by = x + 80, y + 10
        pygame.draw.rect(surface, DARK_GRAY, (bx, by, bar_w, bar_h), border_radius=3)
        hp_c = RED if hp_ratio < 0.25 else (YELLOW if hp_ratio < 0.5 else GREEN)
        pygame.draw.rect(surface, hp_c, (bx, by, int(bar_w * hp_ratio), bar_h), border_radius=3)
        pygame.draw.rect(surface, WHITE, (bx, by, bar_w, bar_h), 1, border_radius=3)
        draw_text(surface, "HP", bx - 28, by + 1, 12, GRAY)

        sh_ratio = p.shield / p.max_shield
        sy = by + 18
        pygame.draw.rect(surface, DARK_GRAY, (bx, sy, bar_w, 8), border_radius=2)
        pygame.draw.rect(surface, CYAN, (bx, sy, int(bar_w * sh_ratio), 8), border_radius=2)
        pygame.draw.rect(surface, (150, 150, 150), (bx, sy, bar_w, 8), 1, border_radius=2)
        draw_text(surface, "SH", bx - 28, sy - 1, 10, GRAY)

        w_idx = p.weapons.current_weapon
        wname = WEAPON_NAMES[w_idx]
        wcolor = WEAPON_COLORS[w_idx]
        draw_text(surface, wname, x + 80, y + 44, 16, wcolor)

        heat = p.weapons.overheat[w_idx] / OVERHEAT_MAX
        hx = x + 170
        hy = y + 47
        hw = 140
        hh = 10
        pygame.draw.rect(surface, DARK_GRAY, (hx, hy, hw, hh), border_radius=2)
        heat_c = RED if heat > 0.75 else (ORANGE if heat > 0.5 else YELLOW)
        if p.weapons.overheated[w_idx]:
            if int(pygame.time.get_ticks() / 80) % 2:
                heat_c = WHITE
        pygame.draw.rect(surface, heat_c, (hx, hy, int(hw * heat), hh), border_radius=2)
        pygame.draw.rect(surface, GRAY, (hx, hy, hw, hh), 1, border_radius=2)
        draw_text(surface, "HEAT", hx - 32, hy + 1, 10, GRAY)

        lvl = p.weapons.levels[w_idx]
        stars = "*" * lvl
        draw_text(surface, stars, x + w - 30, y + 44, 18, wcolor)

        if p.combo >= 5:
            c_c = PINK if p.combo >= 25 else (ORANGE if p.combo >= 15 else YELLOW)
            draw_text(surface, f"C: {p.combo}", x + w - 60, y + 8, 18, c_c)

    def _draw_score_wave(self, surface, score, wave_info):
        draw_text_outline(surface, f"SCORE: {score:,}", SCREEN_WIDTH // 2,
                          25, 28, WHITE, BLACK, center=True)
        if wave_info:
            info = f"WAVE {wave_info['wave']}"
            if wave_info['is_boss']:
                info += " [BOSS]"
                c = RED
            else:
                c = WHITE
            draw_text(surface, info, SCREEN_WIDTH // 2, 55, 18, c, center=True)

            if wave_info['state'] == 'boss_intro':
                alpha = int(255 * min(1.0, wave_info.get('state_timer', 3) / 3))
                s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                pygame.draw.rect(s, (0, 0, 0, alpha // 2), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
                surface.blit(s, (0, 0))
                draw_text_outline(surface, "!! WARNING !!", SCREEN_WIDTH // 2,
                                  SCREEN_HEIGHT // 2 - 30, 64, RED, BLACK, center=True)
                draw_text_outline(surface, "BOSS APPROACHING", SCREEN_WIDTH // 2,
                                  SCREEN_HEIGHT // 2 + 30, 40, ORANGE, BLACK, center=True)
            elif wave_info['state'] == 'wave_clear':
                draw_text_outline(surface, f"WAVE {wave_info['wave']} CLEARED!",
                                  SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20,
                                  48, GREEN, BLACK, center=True)
                draw_text(surface, "GET READY...",
                          SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30,
                          24, WHITE, center=True)
            elif wave_info['state'] == 'preparing' and wave_info['wave'] > 0:
                draw_text_outline(surface, f"WAVE {wave_info['wave'] + 1}",
                                  SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2,
                                  56, CYAN, BLACK, center=True)

            prog = wave_info['progress']
            if not wave_info['is_boss'] and prog > 0:
                pw = 160
                px = SCREEN_WIDTH // 2 - pw // 2
                py = 78
                pygame.draw.rect(surface, DARK_GRAY, (px, py, pw, 6), border_radius=3)
                pygame.draw.rect(surface, CYAN, (px, py, int(pw * prog), 6), border_radius=3)


class GameOverScreen:
    def __init__(self, on_restart, on_menu, on_save_score):
        self.buttons = []
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2 + 100
        self.buttons.append(Button(cx - 170, cy, 200, 55, "SAVE SCORE", on_save_score, font_size=22, center=False))
        self.buttons.append(Button(cx + 170, cy, 200, 55, "RESTART", on_restart, font_size=22, center=False))
        self.buttons.append(Button(cx, cy + 80, 200, 55, "MAIN MENU", on_menu, font_size=22))
        self.timer = 0
        self.save_input = False
        self.name = "PILOT"
        self.cursor_blink = 0

    def start_save_input(self):
        self.save_input = True
        self.name = "PILOT"

    def handle_event(self, event):
        if self.save_input:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self.save_input = False
                    return 'save', self.name
                elif event.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                elif event.unicode and event.unicode.isalnum() and len(self.name) < 12:
                    self.name += event.unicode.upper()
            return None
        for b in self.buttons:
            if b.handle_event(event):
                return True
        return False

    def update(self, dt, mouse_pos, score=0, wave=0, combo=0):
        self.timer += dt
        self.cursor_blink += dt
        for b in self.buttons:
            b.update(mouse_pos)

    def draw(self, surface, score, wave, max_combo, duration_sec, new_hs=False):
        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(dark, (0, 0, 0, 200), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        surface.blit(dark, (0, 0))

        title_c = RED if not new_hs else YELLOW
        draw_text_outline(surface, "GAME OVER", SCREEN_WIDTH // 2,
                          140 + math.sin(self.timer * 3) * 5, 72, title_c, BLACK, center=True)
        if new_hs:
            draw_text_outline(surface, "** NEW HIGH SCORE **", SCREEN_WIDTH // 2,
                              210, 28, PINK, BLACK, center=True)

        info_y = 280
        info_data = [
            ("FINAL SCORE", f"{score:,}", YELLOW),
            ("WAVE REACHED", str(wave), CYAN),
            ("MAX COMBO", f"x{max_combo}", ORANGE),
            ("DURATION", f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}", GREEN),
        ]
        for i, (label, val, c) in enumerate(info_data):
            draw_text(surface, label, SCREEN_WIDTH // 2 - 200, info_y + i * 45, 20, GRAY)
            draw_text(surface, val, SCREEN_WIDTH // 2 + 200, info_y + i * 45, 24, c)
            line_y = info_y + i * 45 + 30
            pygame.draw.line(surface, DARK_GRAY,
                             (SCREEN_WIDTH // 2 - 220, line_y),
                             (SCREEN_WIDTH // 2 + 220, line_y))

        if self.save_input:
            draw_text(surface, "ENTER NAME:", SCREEN_WIDTH // 2 - 160, info_y + 185, 20, WHITE)
            show_cursor = int(self.cursor_blink * 2) % 2 == 0
            display = self.name + ("_" if show_cursor else "")
            draw_text(surface, display, SCREEN_WIDTH // 2 + 40, info_y + 180, 32, CYAN)
            draw_text(surface, "(A-Z / 0-9, max 12, ENTER to save)",
                      SCREEN_WIDTH // 2, info_y + 220, 14, GRAY, center=True)

        for b in self.buttons:
            b.draw(surface)


class PauseMenu:
    def __init__(self, on_resume, on_quit, on_settings=None):
        self.buttons = []
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        self.buttons.append(Button(cx, cy - 70, 280, 55, "RESUME", on_resume, font_size=24))
        if on_settings:
            self.buttons.append(Button(cx, cy, 280, 55, "SETTINGS", on_settings, font_size=24))
        self.buttons.append(Button(cx, cy + 70, 280, 55, "QUIT TO MENU", on_quit, font_size=24))

    def handle_event(self, event):
        for b in self.buttons:
            if b.handle_event(event):
                return True
        return False

    def update(self, mouse_pos):
        for b in self.buttons:
            b.update(mouse_pos)

    def draw(self, surface):
        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(dark, (0, 0, 0, 160), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        surface.blit(dark, (0, 0))
        draw_text_outline(surface, "PAUSED", SCREEN_WIDTH // 2,
                          SCREEN_HEIGHT // 2 - 150, 64, WHITE, BLACK, center=True)
        for b in self.buttons:
            b.draw(surface)


class LeaderboardScreen:
    def __init__(self, on_back):
        self.back_btn = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80,
                               240, 50, "BACK", on_back, font_size=22)

    def handle_event(self, event):
        return self.back_btn.handle_event(event)

    def update(self, mouse_pos):
        self.back_btn.update(mouse_pos)

    def draw(self, surface, scores):
        surface.fill(BLACK)
        draw_text_outline(surface, "LEADERBOARD", SCREEN_WIDTH // 2, 80,
                          48, YELLOW, BLACK, center=True)

        header_y = 160
        headers = [("RANK", 120), ("NAME", 280), ("SCORE", 480),
                   ("WAVE", 720), ("COMBO", 880), ("DATE", 1060)]
        for h, x in headers:
            draw_text(surface, h, x, header_y, 18, CYAN)
        pygame.draw.line(surface, CYAN, (100, header_y + 28),
                         (SCREEN_WIDTH - 100, header_y + 28), 2)

        if not scores:
            draw_text(surface, "No scores yet. Play a game!",
                      SCREEN_WIDTH // 2, 350, 28, GRAY, center=True)
        else:
            for i, s in enumerate(scores):
                y = header_y + 55 + i * 42
                c = YELLOW if i == 0 else (ORANGE if i == 1 else
                                            (CYAN if i == 2 else WHITE))
                rank_c = PINK if i == 0 else (ORANGE if i < 3 else WHITE)
                draw_text(surface, "#%d" % (i + 1), 120, y, 20, rank_c)
                draw_text(surface, s['name'], 280, y, 20, c)
                draw_text(surface, f"{s['score']:,}", 480, y, 20, YELLOW)
                draw_text(surface, str(s['wave']), 720, y, 20, CYAN)
                draw_text(surface, "x%d" % s['max_combo'], 880, y, 20, ORANGE)
                draw_text(surface, s['date'], 1060, y, 16, GRAY)
                if s.get('coop'):
                    draw_text(surface, "[CO-OP]", 1180, y, 14, GREEN)

        self.back_btn.draw(surface)


class SettingsScreen:
    def __init__(self, on_back, get_volumes, set_sfx, set_music):
        self.on_back = on_back
        self.get_volumes = get_volumes
        self.set_sfx = set_sfx
        self.set_music = set_music
        self.back_btn = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 70,
                               240, 50, "BACK", on_back, font_size=22)

    def handle_event(self, event):
        if self.back_btn.handle_event(event):
            return True
        mp = pygame.mouse.get_pos()
        mb = pygame.mouse.get_pressed()
        if mb[0]:
            mx, my = mp
            sfx_rect = (SCREEN_WIDTH // 2 - 200, 290, 400, 20)
            mus_rect = (SCREEN_WIDTH // 2 - 200, 390, 400, 20)
            if sfx_rect[0] <= mx <= sfx_rect[0] + sfx_rect[2] and sfx_rect[1] <= my <= sfx_rect[1] + sfx_rect[3]:
                v = (mx - sfx_rect[0]) / sfx_rect[2]
                self.set_sfx(v)
                return True
            if mus_rect[0] <= mx <= mus_rect[0] + mus_rect[2] and mus_rect[1] <= my <= mus_rect[1] + mus_rect[3]:
                v = (mx - mus_rect[0]) / mus_rect[2]
                self.set_music(v)
                return True
        return False

    def update(self, mouse_pos):
        self.back_btn.update(mouse_pos)

    def draw(self, surface):
        surface.fill(BLACK)
        draw_text_outline(surface, "SETTINGS", SCREEN_WIDTH // 2, 80,
                          48, CYAN, BLACK, center=True)

        vols = self.get_volumes()

        controls = [
            ("MOVE", "WASD / Arrow Keys", 180),
            ("FIRE", "SPACE / Left Mouse", 210),
            ("SWITCH WEAPON", "Q / E", 240),
            ("PAUSE", "ESC / P", 270),
        ]
        draw_text(surface, "CONTROLS:", SCREEN_WIDTH // 2 - 200, 160, 20, YELLOW)
        for lbl, val, y in controls:
            draw_text(surface, lbl, SCREEN_WIDTH // 2 - 200, y, 16, GRAY)
            draw_text(surface, val, SCREEN_WIDTH // 2 + 20, y, 16, WHITE)

        draw_text(surface, "AUDIO:", SCREEN_WIDTH // 2 - 200, 290, 20, YELLOW)

        bx = SCREEN_WIDTH // 2 - 200
        pygame.draw.rect(surface, DARK_GRAY, (bx, 290, 400, 20), border_radius=4)
        pygame.draw.rect(surface, ORANGE, (bx, 290, int(400 * vols['sfx']), 20), border_radius=4)
        pygame.draw.rect(surface, WHITE, (bx, 290, 400, 20), 2, border_radius=4)
        draw_text(surface, "SFX VOLUME", bx - 120, 288, 16, GRAY)
        draw_text(surface, "%d%%" % int(vols['sfx'] * 100), bx + 420, 288, 18, ORANGE)

        pygame.draw.rect(surface, DARK_GRAY, (bx, 390, 400, 20), border_radius=4)
        pygame.draw.rect(surface, CYAN, (bx, 390, int(400 * vols['music']), 20), border_radius=4)
        pygame.draw.rect(surface, WHITE, (bx, 390, 400, 20), 2, border_radius=4)
        draw_text(surface, "MUSIC VOLUME", bx - 120, 388, 16, GRAY)
        draw_text(surface, "%d%%" % int(vols['music'] * 100), bx + 420, 388, 18, CYAN)

        tips = [
            "TIPS:",
            "- Each weapon has 3 upgrade levels",
            "- Watch the HEAT bar to avoid overheating",
            "- Destroy weak points on Bosses for massive damage",
            "- Chain kills for COMBO bonuses",
            "- Near-miss grants SLOW-MO dodge bonus",
        ]
        for i, t in enumerate(tips):
            c = YELLOW if i == 0 else (200, 200, 200)
            draw_text(surface, t, SCREEN_WIDTH // 2 - 200, 460 + i * 28, 16, c)

        self.back_btn.draw(surface)


class ShipCustomize:
    def __init__(self, on_back, on_confirm):
        self.on_back = on_back
        self.on_confirm = on_confirm
        self.body_idx = 0
        self.engine_idx = 0
        self.cockpit_idx = 0
        self.color_idx = 0
        self.colors = [CYAN, GREEN, YELLOW, ORANGE, PINK, PURPLE, WHITE]
        self.color_names = ["CYAN", "GREEN", "YELLOW", "ORANGE", "PINK", "PURPLE", "WHITE"]

        cx = SCREEN_WIDTH // 2
        self.prev_btn = Button(cx - 300, 380, 130, 45, "<< PREV",
                               lambda: self._nav(-1), font_size=18)
        self.next_btn = Button(cx + 300, 380, 130, 45, "NEXT >>",
                               lambda: self._nav(1), font_size=18)
        self.confirm_btn = Button(cx - 160, SCREEN_HEIGHT - 70, 200, 50,
                                  "CONFIRM", on_confirm, font_size=22, center=False)
        self.back_btn = Button(cx + 160, SCREEN_HEIGHT - 70, 200, 50,
                               "BACK", on_back, font_size=22, center=False)
        self.options = ["BODY SHAPE", "ENGINE TYPE", "COCKPIT", "COLOR"]
        self.current_opt = 0

    def _nav(self, d):
        if self.current_opt == 0:
            self.body_idx = (self.body_idx + d) % 3
        elif self.current_opt == 1:
            self.engine_idx = (self.engine_idx + d) % 3
        elif self.current_opt == 2:
            self.cockpit_idx = (self.cockpit_idx + d) % 3
        else:
            self.color_idx = (self.color_idx + d) % len(self.colors)

    def get_config(self):
        return self.body_idx, self.engine_idx, self.cockpit_idx, self.colors[self.color_idx]

    def handle_event(self, event):
        for b in [self.prev_btn, self.next_btn, self.confirm_btn, self.back_btn]:
            if b.handle_event(event):
                return True
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_LEFT, pygame.K_a]:
                self._nav(-1)
                return True
            elif event.key in [pygame.K_RIGHT, pygame.K_d]:
                self._nav(1)
                return True
            elif event.key in [pygame.K_UP, pygame.K_w]:
                self.current_opt = (self.current_opt - 1) % len(self.options)
                return True
            elif event.key in [pygame.K_DOWN, pygame.K_s]:
                self.current_opt = (self.current_opt + 1) % len(self.options)
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for i in range(len(self.options)):
                ry = 460 + i * 32
                if SCREEN_WIDTH // 2 - 200 <= mx <= SCREEN_WIDTH // 2 + 200 and ry <= my <= ry + 28:
                    self.current_opt = i
                    return True
        return False

    def update(self, mouse_pos):
        for b in [self.prev_btn, self.next_btn, self.confirm_btn, self.back_btn]:
            b.update(mouse_pos)

    def draw(self, surface, preview_ship_func):
        surface.fill(BLACK)
        draw_text_outline(surface, "SHIP CUSTOMIZATION", SCREEN_WIDTH // 2,
                          60, 42, CYAN, BLACK, center=True)

        preview_rect = (SCREEN_WIDTH // 2 - 160, 100, 320, 260)
        pygame.draw.rect(surface, (20, 20, 35), preview_rect, border_radius=12)
        pygame.draw.rect(surface, CYAN, preview_rect, 2, border_radius=12)

        if preview_ship_func:
            preview_ship_func(surface, SCREEN_WIDTH // 2, 230,
                              self.body_idx, self.engine_idx, self.cockpit_idx,
                              self.colors[self.color_idx])

        for i, opt in enumerate(self.options):
            y = 460 + i * 32
            selected = (i == self.current_opt)
            bg = (40, 40, 70) if selected else (20, 20, 30)
            pygame.draw.rect(surface, bg, (SCREEN_WIDTH // 2 - 200, y, 400, 28), border_radius=6)
            if selected:
                pygame.draw.rect(surface, YELLOW, (SCREEN_WIDTH // 2 - 200, y, 400, 28), 2, border_radius=6)
            val_idx = [self.body_idx, self.engine_idx, self.cockpit_idx, self.color_idx][i]
            if i < 3:
                val = f"TYPE {val_idx + 1}"
            else:
                val = self.color_names[self.color_idx]
            draw_text(surface, opt, SCREEN_WIDTH // 2 - 180, y + 3, 16, WHITE if selected else GRAY)
            c = self.colors[self.color_idx] if i == 3 else YELLOW
            draw_text(surface, val, SCREEN_WIDTH // 2 + 120, y + 3, 16, c)

        self.prev_btn.draw(surface)
        self.next_btn.draw(surface)
        self.confirm_btn.draw(surface)
        self.back_btn.draw(surface)

        draw_text(surface, "Use WASD / Arrows to navigate and change options",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120, 14, GRAY, center=True)


class ReplayScreen:
    def __init__(self, on_back, on_play, on_delete):
        self.on_back = on_back
        self.on_play = on_play
        self.on_delete = on_delete
        self.back_btn = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 70,
                               240, 50, "BACK", on_back, font_size=22)
        self.selected = -1
        self.scroll = 0
        self.buttons = {}

    def handle_event(self, event, replays):
        if self.back_btn.handle_event(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mx, my = event.pos
                for i in range(len(replays)):
                    ry = 170 + i * 45 - self.scroll
                    if 80 <= mx <= SCREEN_WIDTH - 80 and ry <= my <= ry + 40:
                        self.selected = i
                        return True
                    if SCREEN_WIDTH - 140 <= mx <= SCREEN_WIDTH - 90 and ry <= my <= ry + 40:
                        if i < len(replays):
                            self.on_delete(replays[i]['filename'])
                            self.selected = -1
                            return True
                if 900 <= mx <= 1100 and 120 <= my <= 160 and self.selected >= 0:
                    if self.selected < len(replays):
                        self.on_play(replays[self.selected]['filepath'])
                        return True
            elif event.button == 4:
                self.scroll = max(0, self.scroll - 40)
                return True
            elif event.button == 5:
                self.scroll = min(max(0, len(replays) * 45 - 400), self.scroll + 40)
                return True
        return False

    def update(self, mouse_pos, replays):
        self.back_btn.update(mouse_pos)

    def draw(self, surface, replays):
        surface.fill(BLACK)
        draw_text_outline(surface, "REPLAYS", SCREEN_WIDTH // 2, 70,
                          48, PURPLE, BLACK, center=True)

        if not replays:
            draw_text(surface, "No replays saved yet.",
                      SCREEN_WIDTH // 2, 350, 28, GRAY, center=True)
            draw_text(surface, "Play a game first! Epic battles are auto-saved.",
                      SCREEN_WIDTH // 2, 400, 18, (150, 150, 150), center=True)
            self.back_btn.draw(surface)
            return

        headers = [("#", 100), ("DATE / TIME", 170), ("SCORE", 500),
                   ("WAVE", 700), ("LENGTH", 820), ("", 1100)]
        for h, x in headers:
            draw_text(surface, h, x, 145, 15, CYAN)
        pygame.draw.line(surface, DARK_GRAY, (80, 165),
                         (SCREEN_WIDTH - 80, 165))

        for i, r in enumerate(replays):
            y = 170 + i * 45 - self.scroll
            if y < 170 or y > SCREEN_HEIGHT - 120:
                continue
            selected = (i == self.selected)
            c_bg = (40, 30, 60) if selected else (20, 20, 30)
            pygame.draw.rect(surface, c_bg, (80, y, SCREEN_WIDTH - 160, 40), border_radius=6)
            if selected:
                pygame.draw.rect(surface, YELLOW, (80, y, SCREEN_WIDTH - 160, 40), 2, border_radius=6)

            import time
            date_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(r['date']))
            mins = r['frames'] // (30 * 60)
            secs = (r['frames'] % (30 * 60)) // 30
            draw_text(surface, str(i + 1), 100, y + 10, 16, WHITE)
            draw_text(surface, date_str, 170, y + 10, 15, (220, 220, 220))
            draw_text(surface, f"{r['score']:,}", 500, y + 10, 18, YELLOW)
            draw_text(surface, str(r['wave']), 700, y + 10, 16, CYAN)
            draw_text(surface, f"{mins}:{secs:02d}", 820, y + 10, 16, ORANGE)
            del_col = RED if selected else (180, 80, 80)
            draw_text(surface, "[DEL]", 1110, y + 10, 14, del_col)

        if self.selected >= 0:
            play_c = GREEN if self.selected < len(replays) else DARK_GRAY
            pygame.draw.rect(surface, play_c, (900, 120, 200, 40), border_radius=8)
            pygame.draw.rect(surface, WHITE, (900, 120, 200, 40), 2, border_radius=8)
            draw_text(surface, "PLAY REPLAY", 1000, 125, 18, BLACK, center=True)

        draw_text(surface, "Scroll: Mouse Wheel  |  Click to select  |  DEL: Delete",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 115, 14, GRAY, center=True)

        self.back_btn.draw(surface)
