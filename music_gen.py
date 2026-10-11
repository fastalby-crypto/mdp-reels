#!/usr/bin/env python3
"""Genera una base strumentale morbida (pad + basso + ritmo leggero, ~96 bpm), libera
da diritti perche' creata da zero. Usata solo se la cartella music/ e' vuota.

Uso: python3 music_gen.py <secondi> <file.wav> [seme]
"""
import sys
import wave

import numpy as np

SR = 48000


def env(n, a=0.01, r=0.3):
    t = np.linspace(0, 1, n)
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
    return e


def tone(freq, dur, kind="sine"):
    t = np.arange(int(SR * dur)) / SR
    if kind == "saw":
        x = 2 * (t * freq % 1) - 1
    else:
        x = np.sin(2 * np.pi * freq * t)
    return x


def main():
    secs, out = float(sys.argv[1]), sys.argv[2]
    rng = np.random.default_rng(int(sys.argv[3]) if len(sys.argv) > 3 else 7)
    bpm = 96
    beat = 60 / bpm
    bar = beat * 4
    n = int(SR * (secs + 1))
    mix = np.zeros(n)
    # progressione minore elegante: Am - F - C - G (frequenze in Hz)
    prog = [[220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 261.6, 329.6], [196.0, 246.9, 293.7]]
    shift = rng.choice([1.0, 1.0595, 0.9439])  # piccola variazione di tonalita' tra reel
    t0 = 0.0
    i = 0
    while t0 < secs:
        chord = [f * shift for f in prog[i % 4]]
        s = int(t0 * SR)
        L = int(bar * SR)
        pad = sum(tone(f, bar) + 0.3 * tone(f * 2, bar) for f in chord)
        pad *= np.minimum(1, np.linspace(0, 6, L)) * np.minimum(1, np.linspace(6, 0, L) + 0.4)
        bass = tone(chord[0] / 2, bar) * env(L, 0.02, 0.9)
        seg = 0.06 * pad + 0.18 * bass
        e = min(n, s + L)
        mix[s:e] += seg[: e - s]
        for b in range(4):  # cassa sui quarti, hi-hat in levare
            ks = s + int(b * beat * SR)
            kl = int(0.25 * SR)
            k = np.sin(2 * np.pi * np.cumsum(np.linspace(110, 45, kl)) / SR) * env(kl, 0.002, 0.12)
            if ks + kl < n:
                mix[ks:ks + kl] += 0.35 * k
            hs = ks + int(beat * SR / 2)
            hl = int(0.05 * SR)
            h = rng.standard_normal(hl) * env(hl, 0.001, 0.08)
            h = np.diff(h, prepend=0)
            if hs + hl < n:
                mix[hs:hs + hl] += 0.05 * h
        t0 += bar
        i += 1
    mix = mix[: int(SR * secs)]
    fade = int(SR * 1.5)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.6
    st = np.stack([mix, mix], axis=1)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    main()
