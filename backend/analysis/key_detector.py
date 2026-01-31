"""Musical key detection using librosa."""

from typing import Optional, Tuple

import librosa
import numpy as np


class KeyDetector:
    """Detect musical key from audio signals."""

    # Key profiles (Krumhansl-Schmuckler)
    MAJOR_PROFILE = np.array([
        6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
        2.52, 5.19, 2.39, 3.66, 2.29, 2.88
    ])
    MINOR_PROFILE = np.array([
        6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
        2.54, 4.75, 3.98, 2.69, 3.34, 3.17
    ])

    # Pitch class names
    PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    # Camelot wheel mapping
    CAMELOT_MAP = {
        ('C', 'major'): '8B', ('C', 'minor'): '5A',
        ('C#', 'major'): '3B', ('C#', 'minor'): '12A',
        ('D', 'major'): '10B', ('D', 'minor'): '7A',
        ('D#', 'major'): '5B', ('D#', 'minor'): '2A',
        ('E', 'major'): '12B', ('E', 'minor'): '9A',
        ('F', 'major'): '7B', ('F', 'minor'): '4A',
        ('F#', 'major'): '2B', ('F#', 'minor'): '11A',
        ('G', 'major'): '9B', ('G', 'minor'): '6A',
        ('G#', 'major'): '4B', ('G#', 'minor'): '1A',
        ('A', 'major'): '11B', ('A', 'minor'): '8A',
        ('A#', 'major'): '6B', ('A#', 'minor'): '3A',
        ('B', 'major'): '1B', ('B', 'minor'): '10A',
    }

    def __init__(
        self,
        sr: int = 22050,
        hop_length: int = 512,
    ) -> None:
        """Initialize key detector.

        Args:
            sr: Sample rate.
            hop_length: Hop length for chroma computation.
        """
        self.sr = sr
        self.hop_length = hop_length

    def detect(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
    ) -> Tuple[str, str, str, float]:
        """Detect musical key from audio.

        Args:
            y: Audio time series.
            sr: Sample rate.

        Returns:
            Tuple of (root_note, mode, camelot_key, confidence).
        """
        sr = sr or self.sr

        # Compute chromagram
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=self.hop_length)

        # Average chroma across time
        chroma_avg = np.mean(chroma, axis=1)

        # Normalize
        chroma_avg = chroma_avg / (np.linalg.norm(chroma_avg) + 1e-10)

        # Correlate with key profiles
        best_key = None
        best_mode = None
        best_correlation = -1

        for pitch_class in range(12):
            # Rotate profiles to match pitch class
            major_rotated = np.roll(self.MAJOR_PROFILE, pitch_class)
            minor_rotated = np.roll(self.MINOR_PROFILE, pitch_class)

            # Normalize profiles
            major_rotated = major_rotated / np.linalg.norm(major_rotated)
            minor_rotated = minor_rotated / np.linalg.norm(minor_rotated)

            # Calculate correlation
            major_corr = np.corrcoef(chroma_avg, major_rotated)[0, 1]
            minor_corr = np.corrcoef(chroma_avg, minor_rotated)[0, 1]

            if major_corr > best_correlation:
                best_correlation = major_corr
                best_key = pitch_class
                best_mode = 'major'

            if minor_corr > best_correlation:
                best_correlation = minor_corr
                best_key = pitch_class
                best_mode = 'minor'

        root_note = self.PITCH_CLASSES[best_key]
        camelot_key = self.CAMELOT_MAP.get((root_note, best_mode), '')

        # Confidence based on correlation strength
        confidence = max(0.0, min(1.0, (best_correlation + 1) / 2))

        return root_note, best_mode, camelot_key, round(confidence, 3)

    def detect_camelot(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
    ) -> Tuple[str, float]:
        """Detect key and return in Camelot notation.

        Args:
            y: Audio time series.
            sr: Sample rate.

        Returns:
            Tuple of (camelot_key, confidence).
        """
        _, _, camelot_key, confidence = self.detect(y, sr)
        return camelot_key, confidence

    def get_key_strength(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
    ) -> float:
        """Get overall key strength (how tonal the audio is).

        Higher values indicate clearer tonal center.

        Args:
            y: Audio time series.
            sr: Sample rate.

        Returns:
            Key strength between 0 and 1.
        """
        sr = sr or self.sr

        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=self.hop_length)
        chroma_avg = np.mean(chroma, axis=1)

        # Key strength is the ratio of max to mean chroma energy
        if np.mean(chroma_avg) > 0:
            key_strength = np.max(chroma_avg) / np.mean(chroma_avg)
            # Normalize to 0-1 range
            key_strength = min(1.0, (key_strength - 1) / 5)
        else:
            key_strength = 0.0

        return round(key_strength, 3)

    def get_harmonic_compatible_keys(self, camelot_key: str) -> list[str]:
        """Get harmonically compatible keys for mixing.

        Args:
            camelot_key: Camelot notation key (e.g., "8A", "5B").

        Returns:
            List of compatible Camelot keys.
        """
        if not camelot_key or len(camelot_key) < 2:
            return []

        try:
            number = int(camelot_key[:-1])
            letter = camelot_key[-1].upper()
        except ValueError:
            return []

        compatible = [camelot_key]

        # Same number, different letter (relative major/minor)
        other_letter = 'B' if letter == 'A' else 'A'
        compatible.append(f"{number}{other_letter}")

        # Adjacent numbers, same letter
        prev_num = 12 if number == 1 else number - 1
        next_num = 1 if number == 12 else number + 1
        compatible.append(f"{prev_num}{letter}")
        compatible.append(f"{next_num}{letter}")

        return compatible

    def analyze_key_changes(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
        segment_duration: float = 10.0,
    ) -> list[dict]:
        """Analyze key changes throughout the track.

        Args:
            y: Audio time series.
            sr: Sample rate.
            segment_duration: Duration of each segment in seconds.

        Returns:
            List of dicts with time, key, and confidence for each segment.
        """
        sr = sr or self.sr

        segment_samples = int(segment_duration * sr)
        results = []

        for start in range(0, len(y), segment_samples):
            end = min(start + segment_samples, len(y))
            segment = y[start:end]

            if len(segment) < sr:  # Skip segments shorter than 1 second
                continue

            root, mode, camelot, confidence = self.detect(segment, sr)

            results.append({
                'time': start / sr,
                'root': root,
                'mode': mode,
                'camelot': camelot,
                'confidence': confidence,
            })

        return results
