#!/usr/bin/env python3
"""
ADSR-envelope sine generator.

This script generates a usable sine wave contained in an ADSR envelope for a particular frequency. ADSR envolopes are used
by synthesizers to create different musical instrument sounds. The script has a lot of options, including generating a
wav tone file, plotting the envelope and sine wave, and exporting the wave to a CSV file for use in a device like an
arbitrary waveform generator. You can downsample the excel file to visualize the waveform more easily. You can also set
the Vpp range for electrical use.

Usage examples: (see command line below, too)
  # Quick preview (no file), 440 Hz A4, 10 ms attack, 200 ms decay, sustain 0.6 for 500 ms, 300 ms release
  python adsr_sine.py --freq 440 --attack 0.01 --decay 0.2 --sustain-level 0.6 --sustain 0.5 --release 0.3 --plot

  # Save to WAV at 48 kHz
  python adsr_sine.py --freq 261.63 --attack 0.02 --decay 0.15 --sustain-level 0.7 --sustain 0.8 --release 0.2 \
    --sr 48000 --outfile c4_note.wav

  # Save to WAV and CSV with a down sampled plot for easier Excel visualization
  python adsr_sine.py --freq 440 --attack 0.01 --decay 0.2 --sustain-level 0.6 \
  --sustain 0.5 --release 0.3 --sr 48000 --report-stats \
  --outfile tone.wav --csv-outfile tone.csv --csv-downsample 100 --vpp 0.8 --plot
"""

import argparse
import math
import sys
import wave
from dataclasses import dataclass
from typing import Tuple, Optional

import numpy as np

try:
    import matplotlib.pyplot as plt
    _HAVE_PLOT = True
except Exception:
    _HAVE_PLOT = False


@dataclass
class ADSR:
    attack: float         # seconds
    decay: float          # seconds
    sustain_level: float  # 0..1
    sustain: float        # seconds
    release: float        # seconds

    def total_duration(self) -> float:
        return max(0.0, self.attack) + max(0.0, self.decay) + max(0.0, self.sustain) + max(0.0, self.release)


def _segment(start: float, stop: float, n: int) -> np.ndarray:
    """Inclusive-exclusive linspace-like segment (start..stop, n samples)."""
    if n <= 0:
        return np.empty(0, dtype=np.float64)
    # Use endpoint=False and append stop at the boundary via next segment to avoid duplicate samples.
    return np.linspace(start, stop, num=n, endpoint=False, dtype=np.float64)


def adsr_envelope(adsr: ADSR, sr: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build a linear ADSR envelope.

    Returns:
      env: shape (N,), values in [0,1]
      t:   shape (N,), time vector in seconds (monotonic, last sample < total_duration)
    """
    if sr <= 0:
        raise ValueError("Sample rate must be positive.")
    a_n = int(round(max(0.0, adsr.attack) * sr))
    d_n = int(round(max(0.0, adsr.decay) * sr))
    s_n = int(round(max(0.0, adsr.sustain) * sr))
    r_n = int(round(max(0.0, adsr.release) * sr))

    # Build segments
    a_seg = _segment(0.0, 1.0, a_n)                       # 0 -> 1
    d_seg = _segment(1.0, adsr.sustain_level, d_n)        # 1 -> sustain
    s_seg = np.full(s_n, adsr.sustain_level, dtype=np.float64)  # sustain hold
    r_seg = _segment(adsr.sustain_level, 0.0, r_n)        # sustain -> 0

    env = np.concatenate([a_seg, d_seg, s_seg, r_seg])
    # Time vector aligned with samples
    t = np.arange(env.size, dtype=np.float64) / sr
    # Clip any numerical overshoot
    np.clip(env, 0.0, 1.0, out=env)
    return env, t


def sine_wave(freq: float, duration: float, sr: int, phase: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    """Generate a pure sine of given duration. Returns (x, t)."""
    if freq <= 0:
        raise ValueError("Frequency must be positive.")
    if sr <= 0:
        raise ValueError("Sample rate must be positive.")
    n = int(round(max(0.0, duration) * sr))
    t = np.arange(n, dtype=np.float64) / sr
    x = np.sin(2.0 * math.pi * freq * t + phase, dtype=np.float64)
    return x, t


def synth_adsr_sine(freq: float, adsr: ADSR, sr: int = 48000, amplitude: float = 0.9, phase: float = 0.0) -> Tuple[np.ndarray, int]:
    """
    Create an ADSR-shaped sine tone.
    Returns:
      y: float64 audio samples in [-1, 1)
      sr: sample rate
    """
    if not (0.0 <= amplitude <= 1.0):
        raise ValueError("Amplitude must be in [0, 1].")
    # Rule-of-thumb: at least 8× oversampling vs. frequency for nice plots; Nyquist requires >= 2×.
    if sr < 2 * freq:
        print(f"Warning: sample rate {sr} Hz is below Nyquist for {freq} Hz. Increase sr to >= {2*freq:.0f} Hz.",
              file=sys.stderr)
    env, _ = adsr_envelope(adsr, sr)
    x, _ = sine_wave(freq, adsr.total_duration(), sr, phase=phase)
    n = min(env.size, x.size)
    y = amplitude * env[:n] * x[:n]
    return y.astype(np.float64, copy=False), sr


def write_wav_pcm16(path: str, samples: np.ndarray, sr: int) -> None:
    """Write mono WAV PCM16 using stdlib 'wave' to avoid extra deps."""
    # Normalize to [-1, 1) just in case then convert to int16
    s = np.asarray(samples, dtype=np.float64)
    max_mag = np.max(np.abs(s)) if s.size else 1.0
    if max_mag > 1.0:
        s = s / max_mag
    s16 = np.clip(np.round(s * 32767.0), -32768, 32767).astype(np.int16)

    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        wf.writeframes(s16.tobytes())


def write_csv(path: str, t: np.ndarray, env: np.ndarray, sine: np.ndarray, y: np.ndarray, sr: int, downsample: int = 1, meta: Optional[str] = None) -> None:
    """Write CSV with columns: time (s), envelope, sine_raw, waveform."""
    import numpy as np
    n = min(t.size, env.size, sine.size, y.size)
    step = max(1, downsample)
    idx = np.arange(0, n, step)
    data = np.column_stack([t[idx], env[idx], sine[idx], y[idx]])
    header = f"time_sec,envelope,sine_raw,waveform\n# sample_rate={sr}Hz, csv_downsample={downsample}"
    np.savetxt(path, data, delimiter=",", header=header, comments="")

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate an ADSR-envelope-shaped sine wave.")
    ap.add_argument("--freq", type=float, required=True, help="Sine frequency in Hz (e.g., 440)")
    ap.add_argument("--attack", type=float, required=True, help="Attack time in seconds (e.g., 0.01)")
    ap.add_argument("--decay", type=float, required=True, help="Decay time in seconds (e.g., 0.2)")
    ap.add_argument("--sustain-level", type=float, required=True, help="Sustain level (0..1)")
    ap.add_argument("--sustain", type=float, required=True, help="Sustain time in seconds (e.g., 0.5)")
    ap.add_argument("--release", type=float, required=True, help="Release time in seconds (e.g., 0.3)")
    ap.add_argument("--sr", type=int, default=48000, help="Sample rate in Hz (default: 48000)")
    ap.add_argument("--amplitude", type=float, default=0.9, help="Peak amplitude 0..1 (default: 0.9)")
    ap.add_argument("--phase", type=float, default=0.0, help="Initial phase in radians (default: 0)")
    ap.add_argument("--vpp", type=float, default=None, help="Target peak-to-peak amplitude for the OUTPUT waveform; scales final signal to this Vpp")
    ap.add_argument("--outfile", type=str, default=None, help="Optional WAV output path")
    ap.add_argument("--plot", action="store_true", help="Show plots (requires matplotlib)")
    ap.add_argument("--report-stats", action="store_true", help="Print min/max/Vpp summary of the final waveform")
    ap.add_argument("--csv-outfile", type=str, default=None, help="Optional CSV output path (time,envelope,sine_raw,waveform)")
    ap.add_argument("--csv-downsample", type=int, default=1, help="Downsample factor for CSV (default=1, i.e. no downsampling)")

    args = ap.parse_args(argv)

    if not (0.0 <= args.sustain_level <= 1.0):
        ap.error("--sustain-level must be in [0,1]")

    adsr = ADSR(
        attack=max(0.0, args.attack),
        decay=max(0.0, args.decay),
        sustain_level=args.sustain_level,
        sustain=max(0.0, args.sustain),
        release=max(0.0, args.release),
    )

    y, sr = synth_adsr_sine(args.freq, adsr, sr=args.sr, amplitude=args.amplitude, phase=args.phase)
    # Apply optional Vpp scaling to the final waveform
    vpp_target = args.vpp
    vpp_measured = None
    if y.size:
        # y_min = float(np.min(y))
        # y_max = float(np.max(y))
        y_min = float(min(y))
        y_max = float(max(y))
        vpp_measured = y_max - y_min
        if vpp_target is not None and vpp_target > 0 and vpp_measured > 0:
            scale = vpp_target / vpp_measured
            y = y * scale
            # Recompute stats after scaling
            # y_min = float(np.min(y))
            # y_max = float(np.max(y))
            y_min = float(min(y))
            y_max = float(max(y))
            vpp_measured = y_max - y_min
    else:
        y_min = y_max = 0.0
        vpp_measured = 0.0

    if args.report_stats:
        print(f"Waveform stats: min={y_min:.6f}, max={y_max:.6f}, Vpp={vpp_measured:.6f}")

    if args.csv_outfile:
        env, t = adsr_envelope(adsr, sr)
        sine_raw, _ = sine_wave(args.freq, adsr.total_duration(), sr, phase=args.phase)
        meta = f"vpp_target={args.vpp}, vpp_measured={vpp_measured:.6f}"
        write_csv(args.csv_outfile, t, env, sine_raw, y, sr, downsample=args.csv_downsample, meta=meta)
        print(f"Wrote CSV {args.csv_outfile} ({y.size} samples @ {sr} Hz)")

    if args.outfile:
        write_wav_pcm16(args.outfile, y, sr)
        print(f"Wrote {args.outfile} ({y.size} samples @ {sr} Hz)")

    if args.plot:
        if not _HAVE_PLOT:
            print("matplotlib not available; cannot plot.", file=sys.stderr)
        else:
            # Plot envelope and a short segment of waveform for clarity
            import matplotlib.pyplot as plt
            import numpy as np

            # Recompute envelope/time for plotting
            env, t = adsr_envelope(adsr, sr)
            n = min(env.size, y.size)
            env = env[:n]; t = t[:n]

            plt.figure()
            plt.title("ADSR Envelope")
            plt.plot(t, env)
            plt.xlabel("Time (s)")
            plt.ylabel("Amplitude (0..1)")
            plt.grid(True)

            # Zoom into the first 30 ms of the waveform
            ms = 0.03
            n_zoom = min(int(sr * ms), y.size)
            tz = np.arange(n_zoom) / sr

            plt.figure()
            plt.title("Waveform (first 30 ms)")
            plt.plot(tz, y[:n_zoom])
            plt.xlabel("Time (s)")
            plt.ylabel("Amplitude")
            plt.grid(True)

            plt.show()

    # If neither outfile nor plot, still print a short summary
    if not args.outfile and not args.plot:
        print(f"Generated {y.size} samples at {sr} Hz (duration {y.size/sr:.3f} s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
