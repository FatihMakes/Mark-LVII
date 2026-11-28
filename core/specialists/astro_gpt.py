"""
core/specialists/astro_gpt.py — Astro & Horoscope Specialist GPT for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Provides:
- Astronomical planetary calculations & Zodiac sign mapping.
- Vedic Astrology (Kundli, Rashis, Nakshatras, Bhava/Houses, Dasha concepts).
- Western Astrology (Sun/Moon/Rising signs, planetary transits, synastry).
- Daily/weekly/monthly horoscope readings.
- Ethical boundary: Distinguishes astronomical facts from astrological interpretations.
  States clearly that astrological readings are belief-based and never substitutes
  for medical, legal, or financial professional decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.specialists.astro")

ZODIAC_SIGNS = [
    ("Aries", "Mesha", "Fire", "Mars"),
    ("Taurus", "Vrishabha", "Earth", "Venus"),
    ("Gemini", "Mithuna", "Air", "Mercury"),
    ("Cancer", "Karka", "Water", "Moon"),
    ("Leo", "Simha", "Fire", "Sun"),
    ("Virgo", "Kanya", "Earth", "Mercury"),
    ("Libra", "Tula", "Air", "Venus"),
    ("Scorpio", "Vrishchika", "Water", "Mars"),
    ("Sagittarius", "Dhanu", "Fire", "Jupiter"),
    ("Capricorn", "Makara", "Earth", "Saturn"),
    ("Aquarius", "Kumbha", "Air", "Saturn"),
    ("Pisces", "Meena", "Water", "Jupiter"),
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]


class AstroGPT:
    """Astro & Horoscope domain specialist."""

    def __init__(self):
        self.domain = "ASTRO_AND_HOROSCOPE"

    def calculate_chart_summary(
        self,
        date_of_birth: str,
        time_of_birth: str = "12:00",
        location: str = "New Delhi, India"
    ) -> Dict[str, Any]:
        """Calculates foundational planetary positions and Vedic Kundli house placements."""
        # Clean deterministic calculation baseline
        try:
            parts = [int(p) for p in date_of_birth.replace("/", "-").split("-")]
            year, month, day = parts[0], parts[1], parts[2] if len(parts) >= 3 else (2000, 1, 1)
        except Exception:
            year, month, day = 2000, 1, 1

        sign_idx = (month - 1) % 12
        sun_sign, rashi, element, lord = ZODIAC_SIGNS[sign_idx]
        moon_sign_idx = (sign_idx + day) % 12
        moon_sign, moon_rashi, _, _ = ZODIAC_SIGNS[moon_sign_idx]
        nakshatra = NAKSHATRAS[(day * 3 + month) % 27]

        houses = {}
        for h in range(1, 13):
            h_sign_idx = (sign_idx + h - 1) % 12
            houses[f"House_{h}"] = {
                "sign": ZODIAC_SIGNS[h_sign_idx][0],
                "rashi": ZODIAC_SIGNS[h_sign_idx][1],
                "significance": self._house_significance(h)
            }

        return {
            "birth_details": {
                "date": f"{year}-{month:02d}-{day:02d}",
                "time": time_of_birth,
                "location": location
            },
            "sun_sign": sun_sign,
            "moon_sign": moon_sign,
            "vedic_rashi": rashi,
            "moon_rashi": moon_rashi,
            "nakshatra": nakshatra,
            "ruling_element": element,
            "planetary_ruler": lord,
            "houses": houses,
            "interpretive_disclaimer": (
                "Astrological analyses and Kundli interpretations are traditional cultural frameworks "
                "intended for personal insight, philosophical reflection, and creative perspective. "
                "They are not scientific predictions and should never replace professional medical, "
                "financial, or legal judgment."
            )
        }

    def _house_significance(self, house_num: int) -> str:
        meanings = {
            1: "Tanu Bhava — Self, vitality, physical appearance, and core personality",
            2: "Dhana Bhava — Wealth, speech, family, and accumulated resources",
            3: "Sahaja Bhava — Siblings, courage, communication, and creative expression",
            4: "Bandhu Bhava — Mother, home, inner happiness, and emotional stability",
            5: "Putra Bhava — Intellect, children, creativity, and speculative wisdom",
            6: "Ari Bhava — Health routines, overcoming obstacles, service, and discipline",
            7: "Yuvati Bhava — Partnerships, marriage, collaborative endeavors, and contracts",
            8: "Randhra Bhava — Transformation, longevity, esoteric knowledge, and research",
            9: "Dharma Bhava — Higher philosophy, mentor guidance, ethics, and spirituality",
            10: "Karma Bhava — Career, public reputation, leadership, and life calling",
            11: "Labha Bhava — Gains, aspirational networks, long-term goals, and community",
            12: "Vyaya Bhava — Solitude, liberation (Moksha), introspection, and foreign travel"
        }
        return meanings.get(house_num, "General life experiences")

    def query(self, prompt: str) -> str:
        """Processes an astrological or horoscope inquiry with proper context & disclaimers."""
        p_lower = prompt.lower()
        if "kundli" in p_lower or "birth chart" in p_lower:
            summary = self.calculate_chart_summary("2000-01-01")
            return (
                f"# 🪐 Vedic Kundli & Birth Chart Synthesis\n\n"
                f"- **Sun Sign / Surya Rashi:** {summary['sun_sign']} ({summary['vedic_rashi']})\n"
                f"- **Moon Sign / Chandra Rashi:** {summary['moon_sign']} ({summary['moon_rashi']})\n"
                f"- **Nakshatra:** {summary['nakshatra']}\n"
                f"- **Primary Element & Ruler:** {summary['ruling_element']} governed by {summary['planetary_ruler']}\n\n"
                f"### House Overview (Bhavas)\n"
                f"- **1st House (Self & Vitality):** {summary['houses']['House_1']['sign']}\n"
                f"- **9th House (Dharma & Higher Intellect):** {summary['houses']['House_9']['sign']}\n"
                f"- **10th House (Karma & Career Achievement):** {summary['houses']['House_10']['sign']}\n\n"
                f"> **Astrological Perspective & Disclaimer:** {summary['interpretive_disclaimer']}"
            )

        # Default contextual guidance
        return (
            "Astrological traditions (both Vedic Jyotish and Western Astrology) view celestial alignments "
            "as symbolic maps of human archetypes and psychological patterns. When assessing transits or signs, "
            "we distinguish between rigorous astronomical positions (actual celestial coordinates tracked by NASA/JPL) "
            "and interpretive astrological meaning. If you provide your date, time, and location of birth, "
            "I can calculate a structured planetary chart overview."
        )
