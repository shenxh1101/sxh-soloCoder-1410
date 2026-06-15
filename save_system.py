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

    def load(self, filepath, recorder):
        self.metadata, self.frames = recorder.load(filepath)
        self.frame_idx = 0
        return self.metadata is not None and len(self.frames) > 0

    def reset(self):
        self.frame_idx = 0

    def next_frame(self):
        if not self.frames or self.frame_idx >= len(self.frames):
            return None
        frame = self.frames[self.frame_idx]
        self.frame_idx += 1
        return frame

    def has_more(self):
        return self.frames and self.frame_idx < len(self.frames)

    def get_progress(self):
        if not self.frames:
            return 0
        return self.frame_idx / len(self.frames)
