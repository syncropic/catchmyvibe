"""Track recommendation engine for DJ sets."""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Track


@dataclass
class TrackRecommendation:
    """A recommended track with scoring details."""

    track: Track
    total_score: float
    bpm_score: float
    key_score: float
    energy_score: float
    embedding_score: float


class RecommendationEngine:
    """Engine for recommending next tracks during a DJ set."""

    # Camelot wheel adjacency for harmonic mixing
    CAMELOT_ADJACENT = {
        "1A": ["12A", "2A", "1B"],
        "2A": ["1A", "3A", "2B"],
        "3A": ["2A", "4A", "3B"],
        "4A": ["3A", "5A", "4B"],
        "5A": ["4A", "6A", "5B"],
        "6A": ["5A", "7A", "6B"],
        "7A": ["6A", "8A", "7B"],
        "8A": ["7A", "9A", "8B"],
        "9A": ["8A", "10A", "9B"],
        "10A": ["9A", "11A", "10B"],
        "11A": ["10A", "12A", "11B"],
        "12A": ["11A", "1A", "12B"],
        "1B": ["12B", "2B", "1A"],
        "2B": ["1B", "3B", "2A"],
        "3B": ["2B", "4B", "3A"],
        "4B": ["3B", "5B", "4A"],
        "5B": ["4B", "6B", "5A"],
        "6B": ["5B", "7B", "6A"],
        "7B": ["6B", "8B", "7A"],
        "8B": ["7B", "9B", "8A"],
        "9B": ["8B", "10B", "9A"],
        "10B": ["9B", "11B", "10A"],
        "11B": ["10B", "12B", "11A"],
        "12B": ["11B", "1B", "12A"],
    }

    def __init__(
        self,
        bpm_weight: float = 0.25,
        key_weight: float = 0.30,
        energy_weight: float = 0.20,
        embedding_weight: float = 0.25,
        bpm_tolerance: float = 6.0,
    ) -> None:
        """Initialize the recommendation engine.

        Args:
            bpm_weight: Weight for BPM compatibility score.
            key_weight: Weight for harmonic key compatibility.
            energy_weight: Weight for energy level similarity.
            embedding_weight: Weight for audio embedding similarity.
            bpm_tolerance: Maximum BPM difference for compatibility.
        """
        self.bpm_weight = bpm_weight
        self.key_weight = key_weight
        self.energy_weight = energy_weight
        self.embedding_weight = embedding_weight
        self.bpm_tolerance = bpm_tolerance

    async def get_recommendations(
        self,
        session: AsyncSession,
        current_track: Track,
        limit: int = 10,
        energy_direction: str = "maintain",
        exclude_track_ids: Optional[list[str]] = None,
    ) -> list[TrackRecommendation]:
        """Get recommended next tracks based on current track.

        Args:
            session: Database session.
            current_track: Currently playing track.
            limit: Maximum number of recommendations.
            energy_direction: "build", "maintain", or "drop".
            exclude_track_ids: Track IDs to exclude (already played).

        Returns:
            List of track recommendations sorted by score.
        """
        exclude_ids = set(exclude_track_ids or [])
        exclude_ids.add(current_track.id)

        # Build base query
        stmt = select(Track).where(Track.id.notin_(exclude_ids))

        # Filter by BPM range (including half/double time)
        if current_track.bpm:
            bpm_ranges = self._get_compatible_bpm_ranges(current_track.bpm)
            bpm_conditions = []
            for low, high in bpm_ranges:
                from sqlalchemy import and_
                bpm_conditions.append(and_(Track.bpm >= low, Track.bpm <= high))

            if bpm_conditions:
                from sqlalchemy import or_
                stmt = stmt.where(or_(*bpm_conditions))

        # Execute query
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        # Score each candidate
        recommendations = []
        for candidate in candidates:
            scores = self._calculate_scores(current_track, candidate, energy_direction)
            recommendations.append(
                TrackRecommendation(
                    track=candidate,
                    total_score=scores["total"],
                    bpm_score=scores["bpm"],
                    key_score=scores["key"],
                    energy_score=scores["energy"],
                    embedding_score=scores["embedding"],
                )
            )

        # Sort by total score descending
        recommendations.sort(key=lambda r: r.total_score, reverse=True)

        return recommendations[:limit]

    def _get_compatible_bpm_ranges(self, bpm: float) -> list[tuple[float, float]]:
        """Get compatible BPM ranges including half/double time.

        Args:
            bpm: Current track BPM.

        Returns:
            List of (low, high) BPM ranges.
        """
        ranges = [
            (bpm - self.bpm_tolerance, bpm + self.bpm_tolerance),
        ]

        # Add half-time range if reasonable
        if bpm > 120:
            half_bpm = bpm / 2
            ranges.append(
                (half_bpm - self.bpm_tolerance, half_bpm + self.bpm_tolerance)
            )

        # Add double-time range if reasonable
        if bpm < 100:
            double_bpm = bpm * 2
            ranges.append(
                (double_bpm - self.bpm_tolerance, double_bpm + self.bpm_tolerance)
            )

        return ranges

    def _calculate_scores(
        self,
        current: Track,
        candidate: Track,
        energy_direction: str,
    ) -> dict[str, float]:
        """Calculate compatibility scores between two tracks.

        Args:
            current: Current track.
            candidate: Candidate track.
            energy_direction: "build", "maintain", or "drop".

        Returns:
            Dictionary with individual and total scores.
        """
        bpm_score = self._score_bpm(current.bpm, candidate.bpm)
        key_score = self._score_key(current.key, candidate.key)
        energy_score = self._score_energy(
            current.energy, candidate.energy, energy_direction
        )
        embedding_score = self._score_embedding(current.embedding, candidate.embedding)

        total = (
            bpm_score * self.bpm_weight
            + key_score * self.key_weight
            + energy_score * self.energy_weight
            + embedding_score * self.embedding_weight
        )

        return {
            "bpm": bpm_score,
            "key": key_score,
            "energy": energy_score,
            "embedding": embedding_score,
            "total": total,
        }

    def _score_bpm(self, current_bpm: Optional[float], candidate_bpm: Optional[float]) -> float:
        """Score BPM compatibility.

        Args:
            current_bpm: Current track BPM.
            candidate_bpm: Candidate track BPM.

        Returns:
            Score between 0 and 1.
        """
        if not current_bpm or not candidate_bpm:
            return 0.5  # Neutral if unknown

        # Check direct BPM match
        diff = abs(current_bpm - candidate_bpm)
        if diff <= self.bpm_tolerance:
            return 1.0 - (diff / self.bpm_tolerance)

        # Check half-time
        half_diff = abs(current_bpm / 2 - candidate_bpm)
        if half_diff <= self.bpm_tolerance:
            return 0.8 * (1.0 - (half_diff / self.bpm_tolerance))

        # Check double-time
        double_diff = abs(current_bpm * 2 - candidate_bpm)
        if double_diff <= self.bpm_tolerance:
            return 0.8 * (1.0 - (double_diff / self.bpm_tolerance))

        return 0.0

    def _score_key(self, current_key: Optional[str], candidate_key: Optional[str]) -> float:
        """Score harmonic key compatibility using Camelot wheel.

        Args:
            current_key: Current track key (Camelot notation).
            candidate_key: Candidate track key.

        Returns:
            Score between 0 and 1.
        """
        if not current_key or not candidate_key:
            return 0.5  # Neutral if unknown

        current_key = current_key.upper()
        candidate_key = candidate_key.upper()

        # Perfect match
        if current_key == candidate_key:
            return 1.0

        # Adjacent on Camelot wheel (perfect for mixing)
        adjacent = self.CAMELOT_ADJACENT.get(current_key, [])
        if candidate_key in adjacent:
            return 0.9

        # Energy boost/drop (same number, different letter)
        if current_key[:-1] == candidate_key[:-1]:
            return 0.7

        # Two steps away on wheel
        for adj in adjacent:
            if candidate_key in self.CAMELOT_ADJACENT.get(adj, []):
                return 0.5

        return 0.2  # Not harmonically compatible

    def _score_energy(
        self,
        current_energy: Optional[float],
        candidate_energy: Optional[float],
        direction: str,
    ) -> float:
        """Score energy compatibility based on set direction.

        Args:
            current_energy: Current track energy (0-1).
            candidate_energy: Candidate track energy.
            direction: "build", "maintain", or "drop".

        Returns:
            Score between 0 and 1.
        """
        if current_energy is None or candidate_energy is None:
            return 0.5  # Neutral if unknown

        diff = candidate_energy - current_energy

        if direction == "build":
            # Prefer slightly higher energy
            if 0 <= diff <= 0.2:
                return 1.0
            elif 0.2 < diff <= 0.4:
                return 0.7
            elif -0.1 <= diff < 0:
                return 0.5
            else:
                return 0.2

        elif direction == "drop":
            # Prefer lower energy
            if -0.2 <= diff <= 0:
                return 1.0
            elif -0.4 <= diff < -0.2:
                return 0.7
            elif 0 < diff <= 0.1:
                return 0.5
            else:
                return 0.2

        else:  # maintain
            # Prefer similar energy
            abs_diff = abs(diff)
            if abs_diff <= 0.1:
                return 1.0
            elif abs_diff <= 0.2:
                return 0.7
            elif abs_diff <= 0.3:
                return 0.4
            else:
                return 0.2

    def _score_embedding(
        self,
        current_embedding: Optional[list[float]],
        candidate_embedding: Optional[list[float]],
    ) -> float:
        """Score audio embedding similarity.

        Args:
            current_embedding: Current track embedding.
            candidate_embedding: Candidate track embedding.

        Returns:
            Score between 0 and 1.
        """
        if not current_embedding or not candidate_embedding:
            return 0.5  # Neutral if no embeddings

        # Cosine similarity
        current = np.array(current_embedding)
        candidate = np.array(candidate_embedding)

        dot = np.dot(current, candidate)
        norm = np.linalg.norm(current) * np.linalg.norm(candidate)

        if norm == 0:
            return 0.5

        # Cosine similarity ranges from -1 to 1, normalize to 0-1
        similarity = (dot / norm + 1) / 2

        return float(similarity)

    def get_harmonic_keys(self, key: str) -> list[str]:
        """Get harmonically compatible keys for a given key.

        Args:
            key: Camelot notation key.

        Returns:
            List of compatible keys including the original.
        """
        key = key.upper()
        compatible = [key]
        compatible.extend(self.CAMELOT_ADJACENT.get(key, []))
        return compatible

    def get_suggested_bpm_range(self, bpm: float) -> dict:
        """Get suggested BPM range for mixing.

        Args:
            bpm: Current track BPM.

        Returns:
            Dict with min, max, and suggestions.
        """
        return {
            "current": bpm,
            "range": {
                "min": bpm - self.bpm_tolerance,
                "max": bpm + self.bpm_tolerance,
            },
            "half_time": {
                "bpm": bpm / 2,
                "min": bpm / 2 - self.bpm_tolerance,
                "max": bpm / 2 + self.bpm_tolerance,
            } if bpm > 120 else None,
            "double_time": {
                "bpm": bpm * 2,
                "min": bpm * 2 - self.bpm_tolerance,
                "max": bpm * 2 + self.bpm_tolerance,
            } if bpm < 100 else None,
        }
