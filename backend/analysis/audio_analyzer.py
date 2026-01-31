"""Main audio analysis pipeline."""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional

import librosa
import numpy as np

from analysis.bpm_detector import BPMDetector
from analysis.key_detector import KeyDetector
from analysis.embedding_generator import EmbeddingGenerator


class AudioAnalyzer:
    """Main audio analysis pipeline for ephemeral processing.

    Downloads audio from cloud storage, analyzes it, and returns results.
    Audio files are deleted after processing.
    """

    SUPPORTED_FORMATS = {'.mp3', '.flac', '.wav', '.aiff', '.aac', '.ogg', '.m4a'}

    def __init__(
        self,
        sr: int = 22050,
        mono: bool = True,
        temp_dir: Optional[str] = None,
    ) -> None:
        """Initialize the audio analyzer.

        Args:
            sr: Target sample rate for analysis.
            mono: Whether to convert to mono.
            temp_dir: Temporary directory for downloads.
        """
        self.sr = sr
        self.mono = mono
        self.temp_dir = temp_dir or tempfile.gettempdir()

        # Initialize analyzers
        self.bpm_detector = BPMDetector(sr=sr)
        self.key_detector = KeyDetector(sr=sr)
        self.embedding_generator = EmbeddingGenerator(sr=sr)

    async def analyze_track(
        self,
        audio_source: str,
        compute_embedding: bool = True,
        compute_waveform: bool = True,
    ) -> dict:
        """Analyze a track from cloud storage or local path.

        This is the main entry point for ephemeral analysis:
        1. Download audio (if cloud URI)
        2. Analyze audio features
        3. Delete temporary file
        4. Return analysis results

        Args:
            audio_source: Cloud URI or local file path.
            compute_embedding: Whether to compute audio embedding.
            compute_waveform: Whether to compute waveform data.

        Returns:
            Dictionary with analysis results.
        """
        local_path = audio_source
        is_temp_file = False

        try:
            # Download if cloud URI
            if self._is_cloud_uri(audio_source):
                local_path = await self._download_from_cloud(audio_source)
                is_temp_file = True

            # Load audio
            y, sr = await asyncio.to_thread(
                librosa.load, local_path, sr=self.sr, mono=self.mono
            )

            # Run analysis
            results = await self._analyze_audio(
                y, sr,
                compute_embedding=compute_embedding,
                compute_waveform=compute_waveform,
            )

            return results

        finally:
            # Clean up temporary file
            if is_temp_file and local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass

    async def analyze_local_file(
        self,
        file_path: str,
        compute_embedding: bool = True,
        compute_waveform: bool = True,
    ) -> dict:
        """Analyze a local audio file.

        Args:
            file_path: Path to local audio file.
            compute_embedding: Whether to compute audio embedding.
            compute_waveform: Whether to compute waveform data.

        Returns:
            Dictionary with analysis results.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported audio format: {ext}")

        # Load audio
        y, sr = await asyncio.to_thread(
            librosa.load, file_path, sr=self.sr, mono=self.mono
        )

        return await self._analyze_audio(
            y, sr,
            compute_embedding=compute_embedding,
            compute_waveform=compute_waveform,
        )

    async def _analyze_audio(
        self,
        y: np.ndarray,
        sr: int,
        compute_embedding: bool = True,
        compute_waveform: bool = True,
    ) -> dict:
        """Run all analysis on loaded audio.

        Args:
            y: Audio time series.
            sr: Sample rate.
            compute_embedding: Whether to compute audio embedding.
            compute_waveform: Whether to compute waveform data.

        Returns:
            Dictionary with analysis results.
        """
        # Run analyses in parallel using thread pool
        bpm_task = asyncio.to_thread(self.bpm_detector.detect, y, sr)
        key_task = asyncio.to_thread(self.key_detector.detect, y, sr)
        energy_task = asyncio.to_thread(self._compute_energy, y)
        beat_task = asyncio.to_thread(
            self.bpm_detector.detect_with_beat_positions, y, sr
        )

        tasks = [bpm_task, key_task, energy_task, beat_task]

        if compute_embedding:
            embedding_task = asyncio.to_thread(self.embedding_generator.generate, y, sr)
            tasks.append(embedding_task)

        if compute_waveform:
            waveform_task = asyncio.to_thread(
                self.embedding_generator.generate_waveform_data, y, sr
            )
            tasks.append(waveform_task)

        results = await asyncio.gather(*tasks)

        # Unpack results
        bpm, bpm_confidence = results[0]
        root, mode, camelot, key_confidence = results[1]
        energy = results[2]
        _, beat_times, _ = results[3]

        analysis = {
            'bpm': bpm,
            'bpm_confidence': bpm_confidence,
            'key': camelot,
            'key_root': root,
            'key_mode': mode,
            'key_confidence': key_confidence,
            'energy': energy,
            'duration_ms': int(len(y) / sr * 1000),
        }

        # Add beat grid info
        if len(beat_times) > 0:
            analysis['first_beat_ms'] = int(beat_times[0] * 1000)
            analysis['beat_count'] = len(beat_times)

        # Add embedding if computed
        idx = 4
        if compute_embedding:
            analysis['embedding'] = results[idx].tolist()
            idx += 1

        if compute_waveform:
            analysis['waveform'] = results[idx]

        return analysis

    def _compute_energy(self, y: np.ndarray) -> float:
        """Compute overall energy level (0-1).

        Args:
            y: Audio time series.

        Returns:
            Energy level between 0 and 1.
        """
        # RMS energy
        rms = np.sqrt(np.mean(y ** 2))

        # Spectral energy
        spec = np.abs(librosa.stft(y))
        spectral_energy = np.mean(spec)

        # Combine and normalize
        combined = (rms + spectral_energy / 100) / 2

        # Map to 0-1 range (typical values are 0.01-0.3)
        energy = min(1.0, combined * 5)

        return round(energy, 3)

    def _is_cloud_uri(self, uri: str) -> bool:
        """Check if URI is a cloud storage URI.

        Args:
            uri: URI to check.

        Returns:
            True if cloud URI.
        """
        cloud_prefixes = [
            'gs://',      # Google Cloud Storage
            's3://',      # AWS S3
            'b2://',      # Backblaze B2
            'gdrive://',  # Google Drive
            'https://drive.google.com/',
            'https://storage.googleapis.com/',
        ]
        return any(uri.startswith(prefix) for prefix in cloud_prefixes)

    async def _download_from_cloud(self, uri: str) -> str:
        """Download audio file from cloud storage.

        Args:
            uri: Cloud storage URI.

        Returns:
            Path to downloaded temporary file.
        """
        # Import storage module lazily to avoid circular imports
        from storage.cloud import CloudStorage

        storage = CloudStorage()
        local_path = await storage.download_temp(uri, self.temp_dir)
        return local_path


class AnalysisResult:
    """Container for audio analysis results."""

    def __init__(self, data: dict) -> None:
        """Initialize from analysis data dict."""
        self.bpm: float = data.get('bpm', 0.0)
        self.bpm_confidence: float = data.get('bpm_confidence', 0.0)
        self.key: str = data.get('key', '')
        self.key_root: str = data.get('key_root', '')
        self.key_mode: str = data.get('key_mode', '')
        self.key_confidence: float = data.get('key_confidence', 0.0)
        self.energy: float = data.get('energy', 0.0)
        self.duration_ms: int = data.get('duration_ms', 0)
        self.embedding: Optional[list[float]] = data.get('embedding')
        self.waveform: Optional[list[float]] = data.get('waveform')
        self.first_beat_ms: Optional[int] = data.get('first_beat_ms')
        self.beat_count: Optional[int] = data.get('beat_count')

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'bpm': self.bpm,
            'bpm_confidence': self.bpm_confidence,
            'key': self.key,
            'key_root': self.key_root,
            'key_mode': self.key_mode,
            'key_confidence': self.key_confidence,
            'energy': self.energy,
            'duration_ms': self.duration_ms,
            'embedding': self.embedding,
            'waveform': self.waveform,
            'first_beat_ms': self.first_beat_ms,
            'beat_count': self.beat_count,
        }
