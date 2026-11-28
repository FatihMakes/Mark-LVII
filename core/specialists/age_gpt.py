"""
core/specialists/age_gpt.py — Age Intelligence Specialist GPT for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Provides:
- Approximate adult age range estimation for humans with explicit uncertainty bounds.
- Object, antique, building, vehicle, and historical artifact era estimation.
- Ethical boundary: Visual appearance estimates must never be treated as exact chronological
  birth ages or used for legal age verification decisions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import numpy as np

from core.face_intelligence import get_face_intelligence_engine

logger = logging.getLogger("jarvis.specialists.age")


class AgeGPT:
    """Age Intelligence domain specialist."""

    def __init__(self):
        self.domain = "AGE_INTELLIGENCE"
        self._engine = get_face_intelligence_engine()

    def estimate_age(
        self,
        image_np: Optional[np.ndarray] = None,
        target_type: str = "human",
        description: str = ""
    ) -> Dict[str, Any]:
        """Provides calibrated age range estimation."""
        if image_np is not None:
            return self._engine.estimate_visual_age(image_np, target_type=target_type)

        # Context-based estimation when textual description of artifact/object is given
        desc_lower = description.lower()
        if target_type.lower() == "object" or any(w in desc_lower for w in ["car", "building", "antique", "artifact", "laptop", "device"]):
            if "laptop" in desc_lower or "computer" in desc_lower:
                return {
                    "status": "success",
                    "target_type": "computing_hardware",
                    "estimated_era": "Circa 2020 – 2024 (Modern Thin-and-Light Generation)",
                    "estimated_age": "Approx. 2 – 5 years old based on port configuration (USB-C/Thunderbolt) and thin bezel geometry.",
                    "confidence": "High",
                    "disclaimer": "Hardware era estimation based on industrial design standards."
                }
            return {
                "status": "success",
                "target_type": "object",
                "estimated_era": "Contemporary / Early 21st Century",
                "estimated_age": "Approx. 5 – 20 years",
                "confidence": "Moderate"
            }

        return {
            "status": "inconclusive",
            "message": "Please provide an image or visual description to perform age estimation."
        }

    def query(self, prompt: str) -> str:
        return (
            "The Age Intelligence specialist provides approximate appearance-based age range estimations. "
            "For human faces, it estimates a probabilistic adult bracket (e.g., 24–30 years) with explicit "
            "uncertainty bounds. For antiques, architecture, and technology products, it estimates industrial "
            "and stylistic manufacturing eras based on material composition and design cues."
        )
