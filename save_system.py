import json
import os
import time
import gzip
import pickle
from config import *


class HighScoreManager:
    def __init__(self, filepath=SAVE_FILE):
        self.filepath = filepath
        self.scores = []
        self.max_entries = 10
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.scores = data.get('scores', [])
            else:
                self.scores = []
        except Exception:
            self.scores = []

    def save(self):
        try:
            data = {
                'scores': self.scores,
                'version': 1,
                'saved_at': time.time()
            }
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def add_score(self, name, score, wave, combo, duration, is_coop=False):
        entry = {
            'name': name[:12],
            'score': int(score),
            'wave': int(wave),
            'max_combo': int(combo),
            'duration': int(duration),
            'coop': is_coop,
            'date': time.strftime('%Y-%m-%d %H:%M')
        }
        self.scores.append(entry)
        self.scores.sort(key=lambda x: x['score'], reverse=True)
        self.scores = self.scores[:self.max_entries]
        self.save()
        return self.get_rank(score)

    def get_rank(self, score):
        for i, s in enumerate(self.scores):
            if score >= s['score']:
                return i + 1
        return len(self.scores) + 1

    def is_high_score(self, score):
        if len(self.scores) < self.max_entries:
            return True
        return score > self.scores[-1]['score']

    def get_top(self, n=10):
        return self.scores[:n]

    def clear(self):
        self.scores = []
        self.save()


class ReplayRecorder:
    def __init__(self, replay_dir=REPLAY_DIR):
        self.replay_dir = replay_dir
        self.frames = []
        self.metadata = {}
        self.recording = False
        self.max_frames = 30 * 60 * 10
        self.current_frame = 0
        self._ensure_dir()

    def _ensure_dir(self):
        try:
            os.makedirs(self.replay_dir, exist_ok=True)
        except Exception:
            pass

    def start(self, game_info):
        self.frames = []
        self.current_frame = 0
        self.metadata = {
            'game_info': game_info,
            'start_time': time.time(),
            'version': 1
        }
        self.recording = True

    def record_frame(self, frame_data):
        if not self.recording:
            return
        if len(self.frames) >= self.max_frames:
            self.recording = False
            return
        self.frames.append(frame_data)
        self.current_frame += 1

    def stop(self, final_info=None):
        self.recording = False
        if final_info:
            self.metadata['final_info'] = final_info
        self.metadata['end_time'] = time.time()
        self.metadata['frame_count'] = len(self.frames)

    def save(self, filename=None):
        if not self.frames:
            return None
        try:
            if filename is None:
                ts = time.strftime('%Y%m%d_%H%M%S')
                score = self.metadata.get('game_info', {}).get('score', 0)
                filename = f'replay_{ts}_{score}.rsb'
            filepath = os.path.join(self.replay_dir, filename)

            data = {
                'metadata': self.metadata,
                'frames': self.frames
            }
            with gzip.open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            return filepath
        except Exception:
            return None

    def list_replays(self):
        try:
            files = []
            if os.path.exists(self.replay_dir):
                for f in os.listdir(self.replay_dir):
                    if f.endswith('.rsb'):
                        fp = os.path.join(self.replay_dir, f)
                        try:
                            with gzip.open(fp, 'rb') as gf:
                                data = pickle.load(gf)
                                meta = data.get('metadata', {})
                                gi = meta.get('game_info', {})
                                fi = meta.get('final_info', {})
                                files.append({
                                    'filename': f,
                                    'filepath': fp,
                                    'score': fi.get('score', gi.get('score', 0)),
                                    'wave': fi.get('wave', gi.get('wave', 0)),
                                    'frames': meta.get('frame_count', 0),
                                    'date': meta.get('start_time', time.time())
                                })
                        except Exception:
                            continue
            files.sort(key=lambda x: x['date'], reverse=True)
            return files
        except Exception:
            return []

    def load(self, filepath):
        try:
            with gzip.open(filepath, 'rb') as f:
                data = pickle.load(f)
            return data.get('metadata', {}), data.get('frames', [])
        except Exception:
            return None, []

    def delete(self, filename):
        try:
            fp = os.path.join(self.replay_dir, filename)
            if os.path.exists(fp):
                os.remove(fp)
                return True
        except Exception:
            pass
        return False


class ReplayPlayer:
    def __init__(self):
        self.metadata = None
        self.frames = []
        self.frame_idx = 0
        self.playing = False
        self.speed = 1.0
        self.paused = False
        self._speed_levels = [0.25, 0.5, 1.0, 2.0, 4.0]
        self._speed_idx = 2
        self._accumulator = 0.0
        self.key_frames = {}

    def load(self, filepath, recorder):
        self.metadata, self.frames = recorder.load(filepath)
        self.frame_idx = 0
        self.speed = 1.0
        self._speed_idx = 2
        self.paused = False
        self._accumulator = 0.0
        self.key_frames = self._find_key_frames()
        return self.metadata is not None and len(self.frames) > 0

    def _find_key_frames(self):
        kf = {'boss_appear': -1, 'phase_change': {}, 'boss_defeat': -1, 'game_over': -1}
        prev_boss = None
        prev_phase = -1
        for i, f in enumerate(self.frames):
            try:
                b = f.get('boss')
                bi = f.get('boss_info', {})
                ph = bi.get('phase', -1) if bi else -1
                if prev_boss is None and b is not None and kf['boss_appear'] < 0:
                    kf['boss_appear'] = i
                if prev_phase != -1 and ph > prev_phase and ph not in kf['phase_change']:
                    kf['phase_change'][ph] = i
                if prev_boss is not None and b is None and kf['boss_defeat'] < 0:
                    kf['boss_defeat'] = max(0, i - 1)
                if b is not None:
                    prev_boss = b
                if ph >= 0:
                    prev_phase = ph
            except Exception:
                continue
        return kf

    def reset(self):
        self.frame_idx = 0
        self._accumulator = 0.0

    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused

    def cycle_speed(self):
        self._speed_idx = (self._speed_idx + 1) % len(self._speed_levels)
        self.speed = self._speed_levels[self._speed_idx]
        return self.speed

    def get_speed_label(self):
        return f"{self.speed:.2f}x"

    def seek(self, target_idx):
        if not self.frames:
            return False
        self.frame_idx = int(max(0, min(target_idx, len(self.frames) - 1)))
        self._accumulator = 0.0
        return True

    def seek_percent(self, pct):
        if not self.frames:
            return False
        return self.seek(int(pct * (len(self.frames) - 1)))

    def seek_key_frame(self, key):
        idx = -1
        if key == 'boss_appear':
            idx = self.key_frames.get('boss_appear', -1)
        elif key == 'boss_defeat':
            idx = self.key_frames.get('boss_defeat', -1)
        elif key == 'start':
            idx = 0
        elif key == 'end':
            idx = len(self.frames) - 1 if self.frames else -1
        if idx >= 0:
            return self.seek(idx)
        return False

    def seek_phase(self, phase_num):
        idx = self.key_frames.get('phase_change', {}).get(phase_num, -1)
        if idx >= 0:
            return self.seek(idx)
        return False

    def step_frame(self, steps=1):
        if not self.frames:
            return None
        self.frame_idx = max(0, min(self.frame_idx + steps, len(self.frames) - 1))
        if self.frame_idx < len(self.frames):
            return self.frames[self.frame_idx]
        return None

    def next_frame(self, dt=1.0 / 60):
        if not self.frames or self.frame_idx >= len(self.frames):
            return None
        if self.paused:
            if self.frame_idx < len(self.frames):
                return self.frames[self.frame_idx]
            return None
        self._accumulator += dt * 60 * self.speed
        frame = None
        while self._accumulator >= 1.0 and self.frame_idx < len(self.frames):
            frame = self.frames[self.frame_idx]
            self.frame_idx += 1
            self._accumulator -= 1.0
        if frame is None and self.frame_idx < len(self.frames):
            frame = self.frames[self.frame_idx]
        return frame

    def has_more(self):
        return self.frames and self.frame_idx < len(self.frames)

    def get_progress(self):
        if not self.frames:
            return 0
        return self.frame_idx / max(1, len(self.frames))

    def get_time_str(self):
        if not self.frames:
            return "00:00 / 00:00"
        try:
            total_frames = len(self.frames)
            t_cur = self.frame_idx / 60.0
            t_total = total_frames / 60.0
            m_cur, s_cur = int(t_cur // 60), int(t_cur % 60)
            m_tot, s_tot = int(t_total // 60), int(t_total % 60)
            return f"{m_cur:02d}:{s_cur:02d} / {m_tot:02d}:{s_tot:02d}"
        except Exception:
            return "00:00 / 00:00"
