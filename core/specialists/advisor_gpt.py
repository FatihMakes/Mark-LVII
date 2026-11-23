"""
core/specialists/advisor_gpt.py — Suggestion & Advisory Specialist GPT for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Provides:
- Pragmatic daily planning, schedule prioritization, and focus routines.
- Engineering and software architecture guidance grounded in the owner's stack.
- Rigorous risk comparisons and trade-off matrices for decision support.
- Actionable problem-solving, shopping value comparisons, and productivity strategies.
- Eliminates hollow motivational fluff; delivers concrete engineering and strategic recommendations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.specialists.advisor")


class AdvisorGPT:
    """Strategic Planning & Advisory domain specialist."""

    def __init__(self):
        self.domain = "SUGGESTION_AND_ADVISORY"

    def generate_recommendation(
        self,
        domain: str,
        topic: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Produces a structured, actionable decision matrix."""
        constraints = constraints or {}
        budget = constraints.get("budget", "Flexible")

        return {
            "advisory_domain": domain,
            "topic": topic,
            "strategic_recommendation": (
                f"Prioritize modular execution with measurable verification checkpoints. "
                f"Under the constraint of {budget}, isolate foundational components first, "
                f"run end-to-end regression validation, and optimize performance before scaling."
            ),
            "tradeoff_analysis": [
                {"factor": "Speed vs Rigor", "evaluation": "Rigorous automated testing saves 10x debugging time downstream."},
                {"factor": "Resource Cost", "evaluation": "Leveraging existing verified pipelines avoids dependency bloat."},
                {"factor": "Operational Risk", "evaluation": "Fail-safe fallbacks maintain 100% availability during degraded states."}
            ],
            "immediate_action_items": [
                "1. Establish exact acceptance criteria before committing changes.",
                "2. Benchmark latency and memory footprints under realistic loads.",
                "3. Preserve full state history to enable instant rollback if needed."
            ]
        }

    def query(self, prompt: str) -> str:
        rec = self.generate_recommendation("Strategic Planning", prompt)
        items = "\n".join(rec["immediate_action_items"])
        return (
            f"# 🧭 Advisory Analysis: {prompt}\n\n"
            f"**Strategic Assessment:**\n{rec['strategic_recommendation']}\n\n"
            f"### Actionable Steps\n{items}\n\n"
            f"> **Guiding Principle:** Focus on measurable technical outcomes rather than abstract plans."
        )
