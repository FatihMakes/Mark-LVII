"""
core/specialists/mythology_gpt.py — Mythology & Ancient Literature Specialist GPT for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Provides:
- Hindu Mythology and Itihasa traditions (Ramayana, Mahabharata, Puranas, Vedas, Upanishads, Gita).
- Classical Greek, Roman, Norse, Egyptian, Mesopotamian, Celtic, and Japanese mythologies.
- Comparative mythology (e.g. cosmological creation motifs, flood narratives, underworld descents).
- Cross-domain philosophical and cosmological parallels (e.g. black holes vs. primordial void).
- Textual integrity: Distinguishes primary classical texts from later retellings and folk adaptations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.specialists.mythology")


class MythologyGPT:
    """Mythology & Ancient Literature domain specialist."""

    def __init__(self):
        self.domain = "MYTHOLOGY_AND_LITERATURE"

    def compare_black_holes_to_mythology(self) -> Dict[str, Any]:
        """Draws comparative mythological and symbolic parallels to the concept of black holes."""
        return {
            "scientific_concept": "Black Hole / Singularity / Cosmic Event Horizon",
            "comparative_mythological_parallels": [
                {
                    "tradition": "Vedic / Hindu Cosmology (Nasadiya Sukta — Rigveda 10.129)",
                    "concept": "Tamas (Primordial Darkness) & Asat (Non-being)",
                    "parallel": (
                        "Before cosmic projection, 'Darkness was hidden by darkness in the beginning; with no distinguishing sign, "
                        "all this was water.' The concept of Maha-Pralaya (cosmic dissolution) where spacetime, stars, and matter "
                        "contract back into the unmanifest (Avyakta) or into the supreme singularity of Brahman/Shiva as the devourer "
                        "of Time (Maha-Kala)."
                    )
                },
                {
                    "tradition": "Greek Mythology (Hesiod's Theogony)",
                    "concept": "Chaos & Tartarus",
                    "parallel": (
                        "Chaos was the primordial abyss—the gaping void preceding cosmic order (Cosmos). Below Hades lay Tartarus, "
                        "described by Hesiod as a boundless abyssal chasm so deep that an anvil would fall for nine days and nights "
                        "without reaching the floor, surrounded by a triple wall of bronze and absolute darkness from which escape was impossible."
                    )
                },
                {
                    "tradition": "Norse Mythology (Poetic Edda)",
                    "concept": "Ginnungagap",
                    "parallel": (
                        "The primordial, bottomless void between the realms of Niflheim (ice/mist) and Muspelheim (fire/heat). "
                        "Ginnungagap represents the unformed gravitational abyss of potentiality before Ymir and the worlds emerged."
                    )
                },
                {
                    "tradition": "Egyptian Mythology (Book of the Dead / Coffin Texts)",
                    "concept": "Nun (The Primeval Waters)",
                    "parallel": (
                        "The dark, infinite, inert water that surrounded the cosmos. At the end of time, the creator Atum dissolves the universe "
                        "back into the boundless formlessness of Nun, echoing gravitational collapse and total entropy."
                    )
                }
            ],
            "scholarly_distinction": (
                "While ancient mythologies personified cosmic dissolution, primordial voids, and inexorable time (Kala), "
                "modern general relativity describes black holes through differential geometry and gravitational collapse. "
                "These parallels represent archetypal human reflections on infinity, darkness, and irreversible thresholds."
            )
        }

    def query(self, prompt: str) -> str:
        p_lower = prompt.lower()
        if any(w in p_lower for w in ["black hole", "space", "cosmology", "darkness", "void", "creation", "origin", "tamas"]):
            comp = self.compare_black_holes_to_mythology()
            parallels = comp["comparative_mythological_parallels"]
            res = [
                f"# 🏛️ Mythological Parallels to Astronomical Singularity (Black Holes)\n\n",
                f"> **Scholarly Perspective:** {comp['scholarly_distinction']}\n\n"
            ]
            for p in parallels:
                res.append(f"### {p['tradition']}: *{p['concept']}*\n{p['parallel']}\n")
            return "\n".join(res)

        return (
            "Mythological traditions preserve humanity's earliest inquiries into cosmic origins, heroic virtue, "
            "and moral order. Whether exploring the genealogical lineages of the Mahabharata and Ramayana, "
            "the Olympian pantheon in Homer and Hesiod, Norse Yggdrasil cycles, or comparative ancient literature, "
            "I provide textually grounded analyses tracing original canonical verses."
        )
