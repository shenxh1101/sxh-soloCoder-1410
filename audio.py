import math
import random
import struct
import io
import os
import pygame
from config import *

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class ProceduralAudio:
    def __init__(self):
        self.sounds = {}
        self.music_playing = False
        self.music_volume = 0.4
        self.sfx_volume = 0.7
        self.intensity = 0.0
        self.enabled = True
        self.music_channels = []
        self.bass_channel = None
        self.melody_channel = None
        self._try_init_mixer()

    def _try_init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.enabled = True
            pygame.mixer.set_num_channels(32)
        except Exception:
            self.enabled = False

    def _generate_wave(self, samples, func, volume=0.5, freq=440, duration=0.1, sample_rate=44100):
        if not self.enabled or not HAS_NUMPY:
            return None
        n_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        if func == 'sine':
            wave = np.sin(2 * np.pi * freq * t)
        elif func == 'square':
            wave = np.sign(np.sin(2 * np.pi * freq * t))
        elif func == 'sawtooth':
            wave = 2 * (t * freq - np.floor(0.5 + t * freq))
        elif func == 'triangle':
            wave = 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
        elif func == 'noise':
            wave = np.random.uniform(-1, 1, n_samples)
        else:
            wave = np.sin(2 * np.pi * freq * t)

        envelope = np.ones(n_samples)
        attack = int(n_samples * 0.02)
        decay = int(n_samples * 0.15)
        sustain = int(n_samples * 0.5)
        release = n_samples - attack - decay - sustain
        if attack > 0:
            envelope[:attack] = np.linspace(0, 1, attack)
        if decay > 0:
            envelope[attack:attack + decay] = np.linspace(1, 0.7, decay)
        if release > 0:
            envelope[-release:] = np.linspace(0.7, 0, release)

        wave *= envelope * volume
        stereo = np.column_stack([wave, wave])
        audio = (stereo * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(audio)

    def _generate_complex_sound(self, generators, duration=0.1, sample_rate=44100):
        if not self.enabled or not HAS_NUMPY:
            return None
        n_samples = int(sample_rate * duration)
        mixed = np.zeros(n_samples)
        t = np.linspace(0, duration, n_samples, False)

        for gen in generators:
            wave_type = gen.get('type', 'sine')
            freq = gen.get('freq', 440)
            vol = gen.get('vol', 0.3)
            freq_end = gen.get('freq_end', freq)

            if wave_type == 'sine':
                w = np.sin(2 * np.pi * freq * t + 2 * np.pi * (freq_end - freq) * t * t / 2)
            elif wave_type == 'square':
                f = np.linspace(freq, freq_end, n_samples)
                w = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sample_rate))
            elif wave_type == 'sawtooth':
                f = np.linspace(freq, freq_end, n_samples)
                phase = np.cumsum(f) / sample_rate
                w = 2 * (phase - np.floor(0.5 + phase))
            elif wave_type == 'noise':
                w = np.random.uniform(-1, 1, n_samples)
            else:
                w = np.sin(2 * np.pi * freq * t)

            attack = gen.get('attack', 0.01)
            decay = gen.get('decay', 0.1)
            sustain = gen.get('sustain', 0.5)
            release = gen.get('release', 0.05)
            env = self._make_envelope(n_samples, attack, decay, sustain, release, sample_rate)

            mixed += w * vol * env

        mixed = np.clip(mixed, -1, 1)
        stereo = np.column_stack([mixed, mixed])
        audio = (stereo * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(audio)

    def _make_envelope(self, n_samples, attack, decay, sustain, release, sample_rate):
        if not HAS_NUMPY:
            return [1.0] * n_samples
        env = np.ones(n_samples)
        a = int(attack * sample_rate)
        d = int(decay * sample_rate)
        r = int(release * sample_rate)
        if a > 0:
            env[:a] = np.linspace(0, 1, a)
        if d > 0 and a + d < n_samples - r:
            env[a:a + d] = np.linspace(1, sustain, d)
        if r > 0:
            env[-r:] = np.linspace(sustain, 0, r)
        if a + d < n_samples - r:
            env[a + d:-r] = sustain
        return env

    def init_sounds(self):
        if not self.enabled or not HAS_NUMPY:
            return

        self.sounds['laser'] = [
            self._generate_complex_sound([
                {'type': 'sawtooth', 'freq': 1200, 'freq_end': 600, 'vol': 0.2,
                 'attack': 0.005, 'decay': 0.02, 'sustain': 0, 'release': 0.05},
                {'type': 'sine', 'freq': 800, 'freq_end': 400, 'vol': 0.15,
                 'attack': 0.002, 'decay': 0.05, 'sustain': 0, 'release': 0.03}
            ], duration=0.08) for _ in range(3)
        ]

        self.sounds['spread'] = [
            self._generate_complex_sound([
                {'type': 'square', 'freq': 400, 'freq_end': 200, 'vol': 0.15,
                 'attack': 0.003, 'decay': 0.05, 'sustain': 0, 'release': 0.04},
                {'type': 'noise', 'freq': 1, 'vol': 0.08,
                 'attack': 0, 'decay': 0.02, 'sustain': 0, 'release': 0.05}
            ], duration=0.1) for _ in range(3)
        ]

        self.sounds['missile'] = [
            self._generate_complex_sound([
                {'type': 'sawtooth', 'freq': 150, 'freq_end': 300, 'vol': 0.18,
                 'attack': 0.01, 'decay': 0.1, 'sustain': 0.5, 'release': 0.1},
                {'type': 'sine', 'freq': 80, 'freq_end': 120, 'vol': 0.2,
                 'attack': 0.005, 'decay': 0.15, 'sustain': 0.6, 'release': 0.1}
            ], duration=0.25) for _ in range(2)
        ]

        self.sounds['plasma'] = [
            self._generate_complex_sound([
                {'type': 'sine', 'freq': 100, 'freq_end': 400, 'vol': 0.22,
                 'attack': 0.02, 'decay': 0.1, 'sustain': 0.4, 'release': 0.15},
                {'type': 'sawtooth', 'freq': 60, 'freq_end': 200, 'vol': 0.15,
                 'attack': 0.01, 'decay': 0.12, 'sustain': 0.3, 'release': 0.1}
            ], duration=0.3) for _ in range(2)
        ]

        self.sounds['plasma_fire'] = [
            self._generate_complex_sound([
                {'type': 'sine', 'freq': 80, 'freq_end': 700, 'vol': 0.3,
                 'attack': 0.005, 'decay': 0.2, 'sustain': 0.3, 'release': 0.25},
                {'type': 'sawtooth', 'freq': 50, 'freq_end': 400, 'vol': 0.18,
                 'attack': 0.005, 'decay': 0.25, 'sustain': 0.25, 'release': 0.15},
                {'type': 'square', 'freq': 150, 'freq_end': 50, 'vol': 0.1,
                 'attack': 0, 'decay': 0.2, 'sustain': 0, 'release': 0.1}
            ], duration=0.55) for _ in range(2)
        ]

        self.sounds['explosion_small'] = [
            self._generate_complex_sound([
                {'type': 'noise', 'freq': 1, 'vol': 0.3,
                 'attack': 0, 'decay': 0.1, 'sustain': 0, 'release': 0.15},
                {'type': 'sine', 'freq': 120, 'freq_end': 40, 'vol': 0.2,
                 'attack': 0, 'decay': 0.15, 'sustain': 0, 'release': 0.1}
            ], duration=0.25) for _ in range(4)
        ]

        self.sounds['explosion_big'] = [
            self._generate_complex_sound([
                {'type': 'noise', 'freq': 1, 'vol': 0.4,
                 'attack': 0, 'decay': 0.2, 'sustain': 0.3, 'release': 0.4},
                {'type': 'sawtooth', 'freq': 80, 'freq_end': 20, 'vol': 0.25,
                 'attack': 0, 'decay': 0.25, 'sustain': 0.2, 'release': 0.3},
                {'type': 'sine', 'freq': 60, 'freq_end': 30, 'vol': 0.3,
                 'attack': 0, 'decay': 0.3, 'sustain': 0.2, 'release': 0.2}
            ], duration=0.7) for _ in range(2)
        ]

        self.sounds['hit'] = [
            self._generate_complex_sound([
                {'type': 'square', 'freq': 200, 'freq_end': 100, 'vol': 0.15,
                 'attack': 0, 'decay': 0.02, 'sustain': 0, 'release': 0.04}
            ], duration=0.06) for _ in range(4)
        ]

        self.sounds['player_hit'] = [
            self._generate_complex_sound([
                {'type': 'noise', 'freq': 1, 'vol': 0.2,
                 'attack': 0, 'decay': 0.08, 'sustain': 0, 'release': 0.1},
                {'type': 'sawtooth', 'freq': 300, 'freq_end': 80, 'vol': 0.18,
                 'attack': 0, 'decay': 0.1, 'sustain': 0, 'release': 0.1}
            ], duration=0.2)
        ]

        self.sounds['combo'] = [
            self._generate_complex_sound([
                {'type': 'sine', 'freq': 600 + i * 200, 'freq_end': 900 + i * 300,
                 'vol': 0.18, 'attack': 0.01, 'decay': 0.05, 'sustain': 0, 'release': 0.1}
            ], duration=0.12) for i in range(5)
        ]

        self.sounds['dodge'] = self._generate_complex_sound([
            {'type': 'sine', 'freq': 200, 'freq_end': 800, 'vol': 0.2,
             'attack': 0.01, 'decay': 0.1, 'sustain': 0.3, 'release': 0.15},
            {'type': 'sine', 'freq': 400, 'freq_end': 1200, 'vol': 0.12,
             'attack': 0.02, 'decay': 0.08, 'sustain': 0.2, 'release': 0.1}
        ], duration=0.25)

        self.sounds['overheat'] = self._generate_complex_sound([
            {'type': 'sawtooth', 'freq': 150, 'freq_end': 80, 'vol': 0.2,
             'attack': 0.02, 'decay': 0.2, 'sustain': 0, 'release': 0.1}
        ], duration=0.3)

        self.sounds['pickup'] = [
            self._generate_complex_sound([
                {'type': 'sine', 'freq': 500 + i * 150, 'freq_end': 700 + i * 200,
                 'vol': 0.2, 'attack': 0.005, 'decay': 0.04, 'sustain': 0, 'release': 0.08}
            ], duration=0.1) for i in range(3)
        ]

        self.sounds['upgrade'] = self._generate_complex_sound([
            {'type': 'sine', 'freq': 400, 'freq_end': 800, 'vol': 0.22,
             'attack': 0.01, 'decay': 0.1, 'sustain': 0.4, 'release': 0.15},
            {'type': 'sine', 'freq': 600, 'freq_end': 1200, 'vol': 0.15,
             'attack': 0.02, 'decay': 0.08, 'sustain': 0.3, 'release': 0.12}
        ], duration=0.4)

        self.sounds['wave_start'] = self._generate_complex_sound([
            {'type': 'sine', 'freq': 220, 'freq_end': 440, 'vol': 0.2,
             'attack': 0.02, 'decay': 0.1, 'sustain': 0.3, 'release': 0.15},
            {'type': 'square', 'freq': 110, 'freq_end': 220, 'vol': 0.1,
             'attack': 0.01, 'decay': 0.15, 'sustain': 0.2, 'release': 0.1}
        ], duration=0.5)

        self.sounds['boss_appear'] = self._generate_complex_sound([
            {'type': 'sawtooth', 'freq': 50, 'freq_end': 150, 'vol': 0.25,
             'attack': 0.1, 'decay': 0.3, 'sustain': 0.5, 'release': 0.3},
            {'type': 'sine', 'freq': 80, 'freq_end': 200, 'vol': 0.2,
             'attack': 0.05, 'decay': 0.25, 'sustain': 0.4, 'release': 0.25},
            {'type': 'noise', 'freq': 1, 'vol': 0.1,
             'attack': 0, 'decay': 0.2, 'sustain': 0.2, 'release': 0.2}
        ], duration=1.5)

        self.sounds['boss_defeated'] = self._generate_complex_sound([
            {'type': 'sine', 'freq': 523, 'freq_end': 1046, 'vol': 0.25,
             'attack': 0.05, 'decay': 0.2, 'sustain': 0.6, 'release': 0.3},
            {'type': 'sine', 'freq': 659, 'freq_end': 1318, 'vol': 0.18,
             'attack': 0.08, 'decay': 0.15, 'sustain': 0.5, 'release': 0.25},
            {'type': 'sine', 'freq': 784, 'freq_end': 1568, 'vol': 0.12,
             'attack': 0.1, 'decay': 0.1, 'sustain': 0.4, 'release': 0.2}
        ], duration=1.2)

        self.sounds['game_over'] = self._generate_complex_sound([
            {'type': 'sawtooth', 'freq': 400, 'freq_end': 80, 'vol': 0.25,
             'attack': 0.1, 'decay': 0.5, 'sustain': 0.2, 'release': 0.4},
            {'type': 'sine', 'freq': 300, 'freq_end': 60, 'vol': 0.2,
             'attack': 0.15, 'decay': 0.4, 'sustain': 0.15, 'release': 0.35}
        ], duration=1.2)

        self._init_music()

    def _init_music(self):
        if not self.enabled or not HAS_NUMPY:
            return
        try:
            bass_notes = [55, 65, 55, 73, 65, 55, 49, 65]
            melody_notes = [220, 262, 294, 330, 294, 262, 247, 262]
            sample_rate = 44100
            note_dur = 0.4

            n = int(note_dur * sample_rate)
            t = np.linspace(0, note_dur, n, False)
            bass_mix = np.array([])
            melody_mix = np.array([])

            for i in range(16):
                bi = i % len(bass_notes)
                mi = i % len(melody_notes)
                b = 0.5 * np.sin(2 * np.pi * bass_notes[bi] * t)
                b += 0.3 * np.sign(np.sin(2 * np.pi * bass_notes[bi] * t * 2))
                m = 0.35 * np.sin(2 * np.pi * melody_notes[mi] * t)
                m += 0.15 * np.sin(2 * np.pi * melody_notes[mi] * 1.5 * t)
                env = self._make_envelope(n, 0.02, 0.05, 0.7, 0.1, sample_rate)
                bass_mix = np.concatenate([bass_mix, b * env])
                melody_mix = np.concatenate([melody_mix, m * env])

            bass_stereo = np.column_stack([bass_mix, bass_mix])
            melody_stereo = np.column_stack([melody_mix, melody_mix])
            bass_audio = (bass_stereo * 28000).astype(np.int16)
            melody_audio = (melody_stereo * 25000).astype(np.int16)

            self.bass_sound = pygame.sndarray.make_sound(bass_audio)
            self.melody_sound = pygame.sndarray.make_sound(melody_audio)
            self.bass_channel = pygame.mixer.Channel(28)
            self.melody_channel = pygame.mixer.Channel(29)
        except Exception:
            pass

    def play(self, sound_name, index=None):
        if not self.enabled or sound_name not in self.sounds:
            return
        sound_list = self.sounds[sound_name]
        if isinstance(sound_list, list):
            idx = index if index is not None else random.randint(0, len(sound_list) - 1)
            sound = sound_list[idx]
        else:
            sound = sound_list
        if sound:
            ch = sound.play()
            if ch:
                ch.set_volume(self.sfx_volume)

    def play_fire(self, weapon_idx):
        names = ['laser', 'spread', 'missile', 'plasma']
        self.play(names[weapon_idx])

    def play_explosion(self, big=False):
        self.play('explosion_big' if big else 'explosion_small')

    def play_combo(self, combo_count):
        idx = min(4, combo_count // 10)
        self.play('combo', idx)

    def start_music(self):
        if not self.enabled or self.music_playing:
            return
        try:
            if self.bass_sound and self.bass_channel:
                self.bass_channel.play(self.bass_sound, loops=-1)
                self.bass_channel.set_volume(self.music_volume * 0.5)
            if self.melody_sound and self.melody_channel:
                self.melody_channel.play(self.melody_sound, loops=-1)
                self.melody_channel.set_volume(self.music_volume * 0.7)
            self.music_playing = True
        except Exception:
            pass

    def stop_music(self):
        if not self.enabled:
            return
        if self.bass_channel:
            self.bass_channel.fadeout(500)
        if self.melody_channel:
            self.melody_channel.fadeout(500)
        self.music_playing = False

    def update_intensity(self, intensity):
        self.intensity = clamp(intensity, 0, 1)
        if not self.enabled:
            return
        try:
            if self.bass_channel:
                self.bass_channel.set_volume(self.music_volume * (0.3 + 0.5 * self.intensity))
            if self.melody_channel:
                target = 0.2 + 0.8 * self.intensity
                self.melody_channel.set_volume(self.music_volume * target)
        except Exception:
            pass

    def set_sfx_volume(self, v):
        self.sfx_volume = clamp(v, 0, 1)

    def set_music_volume(self, v):
        self.music_volume = clamp(v, 0, 1)
        if self.music_playing and self.bass_channel:
            self.bass_channel.set_volume(self.music_volume * (0.3 + 0.5 * self.intensity))
        if self.music_playing and self.melody_channel:
            self.melody_channel.set_volume(self.music_volume * 0.7)
