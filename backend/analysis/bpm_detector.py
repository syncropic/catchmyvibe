"""BPM detection using librosa."""

from typing import Optional, Tuple

import librosa
import numpy as np


class BPMDetector:
    """Detect BPM (tempo) from audio signals using multiple methods."""

    def __init__(
        self,
        sr: int = 22050,
        hop_length: int = 512,
    ) -> None:
        """Initialize BPM detector.

        Args:
            sr: Sample rate for analysis.
            hop_length: Hop length for onset detection.
        """
        self.sr = sr
        self.hop_length = hop_length

    def detect(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
    ) -> Tuple[float, float]:
        """Detect BPM from audio signal.

        Args:
            y: Audio time series.
            sr: Sample rate (uses instance sr if not provided).

        Returns:
            Tuple of (bpm, confidence).
        """
        sr = sr or self.sr

        # Method 1: Beat tracking
        tempo_beat, _ = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=self.hop_length
        )
        tempo_beat = float(tempo_beat) if np.isscalar(tempo_beat) else float(tempo_beat[0])

        # Method 2: Onset-based tempo estimation
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self.hop_length)
        tempo_onset = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
        tempo_onset = float(tempo_onset[0]) if len(tempo_onset) > 0 else tempo_beat

        # Method 3: Tempogram-based
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        tempo_tempogram = self._estimate_from_tempogram(tempogram, sr)

        # Combine estimates
        tempos = [tempo_beat, tempo_onset]
        if tempo_tempogram:
            tempos.append(tempo_tempogram)

        # Filter out unrealistic tempos
        tempos = [t for t in tempos if 60 <= t <= 200]

        if not tempos:
            # Try to find reasonable tempo by halving/doubling
            for t in [tempo_beat, tempo_onset]:
                if 30 <= t < 60:
                    tempos.append(t * 2)
                elif t > 200:
                    tempos.append(t / 2)

        if not tempos:
            return tempo_beat, 0.0

        # Calculate final BPM as median of estimates
        final_bpm = float(np.median(tempos))

        # Calculate confidence based on agreement between methods
        if len(tempos) > 1:
            std = np.std(tempos)
            confidence = max(0.0, 1.0 - (std / final_bpm))
        else:
            confidence = 0.5

        return round(final_bpm, 2), round(confidence, 3)

    def _estimate_from_tempogram(
        self,
        tempogram: np.ndarray,
        sr: int,
    ) -> Optional[float]:
        """Estimate tempo from tempogram.

        Args:
            tempogram: Tempogram array.
            sr: Sample rate.

        Returns:
            Estimated tempo or None.
        """
        # Sum across time to get aggregate tempo profile
        tempo_profile = np.mean(tempogram, axis=1)

        # Get tempo axis
        tempo_freqs = librosa.tempo_frequencies(tempogram.shape[0], sr=sr)

        # Find peak in reasonable tempo range
        mask = (tempo_freqs >= 60) & (tempo_freqs <= 200)
        if not np.any(mask):
            return None

        masked_profile = tempo_profile.copy()
        masked_profile[~mask] = 0

        peak_idx = np.argmax(masked_profile)
        if peak_idx < len(tempo_freqs):
            return float(tempo_freqs[peak_idx])

        return None

    def detect_with_beat_positions(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
    ) -> Tuple[float, np.ndarray, float]:
        """Detect BPM and return beat positions.

        Args:
            y: Audio time series.
            sr: Sample rate.

        Returns:
            Tuple of (bpm, beat_times_in_seconds, confidence).
        """
        sr = sr or self.sr

        tempo, beat_frames = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=self.hop_length
        )
        tempo = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        # Convert frames to time
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sr, hop_length=self.hop_length
        )

        # Calculate confidence from beat regularity
        if len(beat_times) > 2:
            intervals = np.diff(beat_times)
            std = np.std(intervals)
            mean = np.mean(intervals)
            confidence = max(0.0, 1.0 - (std / mean)) if mean > 0 else 0.0
        else:
            confidence = 0.5

        return tempo, beat_times, round(confidence, 3)

    def get_downbeats(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
    ) -> np.ndarray:
        """Estimate downbeat positions (first beat of each bar).

        Args:
            y: Audio time series.
            sr: Sample rate.

        Returns:
            Array of downbeat times in seconds.
        """
        sr = sr or self.sr

        _, beat_frames = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=self.hop_length
        )
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sr, hop_length=self.hop_length
        )

        # Simple downbeat estimation: assume 4/4 time signature
        # Take every 4th beat starting from the first
        if len(beat_times) >= 4:
            downbeat_times = beat_times[::4]
        else:
            downbeat_times = beat_times[:1] if len(beat_times) > 0 else np.array([])

        return downbeat_times
