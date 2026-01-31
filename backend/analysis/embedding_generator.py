"""Audio embedding generation for similarity search."""

from typing import Optional

import librosa
import numpy as np


class EmbeddingGenerator:
    """Generate audio embeddings for similarity search."""

    def __init__(
        self,
        sr: int = 22050,
        hop_length: int = 512,
        n_mfcc: int = 20,
        n_mels: int = 128,
    ) -> None:
        """Initialize embedding generator.

        Args:
            sr: Sample rate.
            hop_length: Hop length for feature extraction.
            n_mfcc: Number of MFCC coefficients.
            n_mels: Number of mel bands.
        """
        self.sr = sr
        self.hop_length = hop_length
        self.n_mfcc = n_mfcc
        self.n_mels = n_mels

    def generate(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
    ) -> np.ndarray:
        """Generate audio embedding from audio signal.

        Creates a fixed-length feature vector combining multiple
        audio characteristics.

        Args:
            y: Audio time series.
            sr: Sample rate.

        Returns:
            1D numpy array embedding (256 dimensions).
        """
        sr = sr or self.sr

        features = []

        # 1. MFCC statistics (20 x 4 = 80 features)
        mfcc = librosa.feature.mfcc(
            y=y, sr=sr, n_mfcc=self.n_mfcc, hop_length=self.hop_length
        )
        features.append(np.mean(mfcc, axis=1))
        features.append(np.std(mfcc, axis=1))
        features.append(np.min(mfcc, axis=1))
        features.append(np.max(mfcc, axis=1))

        # 2. Chroma features (12 x 2 = 24 features)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=self.hop_length)
        features.append(np.mean(chroma, axis=1))
        features.append(np.std(chroma, axis=1))

        # 3. Spectral features (7 x 2 = 14 features)
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        spectral_flatness = librosa.feature.spectral_flatness(y=y)

        features.append([np.mean(spectral_centroid), np.std(spectral_centroid)])
        features.append([np.mean(spectral_bandwidth), np.std(spectral_bandwidth)])
        features.append([np.mean(spectral_rolloff), np.std(spectral_rolloff)])
        features.append([np.mean(spectral_contrast), np.std(spectral_contrast)])
        features.append([np.mean(spectral_flatness), np.std(spectral_flatness)])

        # 4. Rhythm features (10 features)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        tempogram_mean = np.mean(tempogram, axis=1)[:8]  # Take first 8 components

        features.append([tempo / 200.0])  # Normalize tempo
        features.append([np.mean(onset_env), np.std(onset_env)])
        features.append(tempogram_mean)

        # 5. Zero crossing rate (2 features)
        zcr = librosa.feature.zero_crossing_rate(y)
        features.append([np.mean(zcr), np.std(zcr)])

        # 6. RMS energy (2 features)
        rms = librosa.feature.rms(y=y)
        features.append([np.mean(rms), np.std(rms)])

        # 7. Tonnetz (harmonic) features (6 x 2 = 12 features)
        try:
            tonnetz = librosa.feature.tonnetz(y=y, sr=sr)
            features.append(np.mean(tonnetz, axis=1))
            features.append(np.std(tonnetz, axis=1))
        except Exception:
            features.append(np.zeros(6))
            features.append(np.zeros(6))

        # Flatten and concatenate
        embedding = np.concatenate([np.atleast_1d(f).flatten() for f in features])

        # Normalize to unit length
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        # Pad or truncate to exactly 256 dimensions
        target_dim = 256
        if len(embedding) < target_dim:
            embedding = np.pad(embedding, (0, target_dim - len(embedding)))
        else:
            embedding = embedding[:target_dim]

        return embedding.astype(np.float32)

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding.
            embedding2: Second embedding.

        Returns:
            Similarity score between -1 and 1.
        """
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def find_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: list[np.ndarray],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Find most similar embeddings to query.

        Args:
            query_embedding: Query embedding vector.
            candidate_embeddings: List of candidate embeddings.
            top_k: Number of results to return.

        Returns:
            List of (index, similarity_score) tuples.
        """
        similarities = []

        for i, candidate in enumerate(candidate_embeddings):
            sim = self.compute_similarity(query_embedding, candidate)
            similarities.append((i, sim))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    def generate_waveform_data(
        self,
        y: np.ndarray,
        sr: Optional[int] = None,
        num_samples: int = 800,
    ) -> list[float]:
        """Generate downsampled waveform data for visualization.

        Args:
            y: Audio time series.
            sr: Sample rate.
            num_samples: Number of samples in output.

        Returns:
            List of amplitude values for waveform display.
        """
        sr = sr or self.sr

        # Calculate samples per bin
        samples_per_bin = len(y) // num_samples

        if samples_per_bin < 1:
            samples_per_bin = 1

        waveform = []
        for i in range(num_samples):
            start = i * samples_per_bin
            end = min(start + samples_per_bin, len(y))
            segment = y[start:end]

            if len(segment) > 0:
                # Use RMS of segment
                rms = np.sqrt(np.mean(segment ** 2))
                waveform.append(float(rms))
            else:
                waveform.append(0.0)

        # Normalize to 0-1 range
        max_val = max(waveform) if waveform else 1.0
        if max_val > 0:
            waveform = [v / max_val for v in waveform]

        return waveform
