"""
core/context_resolver.py — Smart Context & Short-Hint Resolution Engine for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Resolves short, conversational hints and references into fully qualified actionable intents:
  - "Under 70k" → Expands previous search ("Find the best laptops under 70000 INR")
  - "Compare the first two" → Extracts details from result #1 and #2 from active search state
  - "Open the cheaper one" → Identifies lowest price item from active list and navigates
  - "Make this into a PDF" → Synthesizes the active topic/content into a formal PDF
  - "Open that again" → Re-opens last visited URL or opened file
  - "What about his age?" → Queries Age GPT using last active subject or image
  - "Iska mythology mein koi comparison hai?" → Connects last topic (e.g. black holes) to Mythology GPT
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.context_resolver")


@dataclass
class ResolvedIntent:
    is_short_hint: bool
    resolved_query: str
    target_entity: Optional[str] = None
    action_type: str = "GENERAL_QUERY"  # "SEARCH" | "BROWSE" | "PDF" | "SPECIALIST" | "MEDIA"
    confidence: float = 1.0
    referenced_context_type: str = "CONVERSATION_HISTORY"  # "BROWSER_STATE" | "ACTIVE_FILE" | "LAST_TASK"
    disambiguation_needed: bool = False
    clarification_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextResolver:
    """Maintains active context and resolves short natural language hints."""

    def __init__(self):
        self._history: List[Dict[str, str]] = []  # list of {"role": str, "content": str}
        self._browser_state: Dict[str, Any] = {
            "last_query": "",
            "active_url": "",
            "search_results": [],
            "last_selected_index": -1
        }
        self._last_artifact: Optional[str] = None
        self._last_topic: str = ""
        self._last_action: Optional[str] = None
        self._speaker_address: str = "Sir"
        self._speaker_gender: str = "MALE"
        self._active_language: str = "ENGLISH"

    def set_active_language(self, lang: str) -> None:
        self._active_language = lang.upper() if lang else "ENGLISH"

    def get_active_language(self) -> str:
        return self._active_language

    def set_speaker_demographics(self, address: str, gender: str) -> None:
        self._speaker_address = address or ("Ma'am" if gender == "FEMALE" else "Sir")
        self._speaker_gender = gender.upper() if gender else "MALE"

    def get_speaker_address(self) -> str:
        return self._speaker_address

    def get_speaker_gender(self) -> str:
        return self._speaker_gender

    def record_turn(self, role: str, content: str) -> None:
        """Records a user or assistant utterance in sliding conversation window."""
        self._history.append({"role": role, "content": str(content or "").strip()})
        if len(self._history) > 20:
            self._history.pop(0)

        # Update last topic and active language if user turn
        if role.lower() == "user":
            txt = content.strip()
            try:
                from core.language_detector import detect_language
                self._active_language = detect_language(txt)
            except Exception:
                pass
            # If not a short hint, update the active topic
            if not self.is_elliptical_hint(txt):
                self._last_topic = txt

    def update_browser_state(
        self,
        query: str = "",
        url: str = "",
        results: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Updates the active browser search session and item candidates."""
        if query:
            self._browser_state["last_query"] = query
            self._last_topic = query
        if url:
            self._browser_state["active_url"] = url
        if results is not None:
            self._browser_state["search_results"] = results

    def update_last_artifact(self, path_or_title: str) -> None:
        self._last_artifact = path_or_title

    def update_last_action(self, action_name: str) -> None:
        self._last_action = action_name

    def is_elliptical_hint(self, text: str) -> bool:
        """Checks if utterance is an elliptical short hint that relies on surrounding context."""
        t = text.strip().lower()

        short_patterns = [
            r"^(under|below|above|between|less than|more than)\s+\d+",
            r"\b(under|below)\s+\d+k\b",
            r"^(compare|open|show|check|find|choose)\s+(the\s+)?(first|second|third|cheaper|next|both|two|three|last|previous)",
            r"^(make|turn)\s+this\s+into",
            r"^(tell me more|explain this|continue that|search more about it)",
            r"^(open that again|play the next one|what about his age|what about her age)",
            r"\b(kaha|kahan|kidhar|where)\b.*(save|rakha|file|pdf|screenshot)",
            r"\b(wo|woh|that|the)\s+(file|pdf|document|screenshot)\s*(kholo|open|dikhao|show|preview|kahan|kaha)",
            r"\b(file|pdf|document)\s*(nahi|ni)\s*mil\s*(raha|rahi)",
            r"\b(dubara|again)\s*(check|search|dhoondo|dhundo)",
            r"^(open|preview|show)\s+(the\s+)?(file|pdf|document|screenshot|it)$",
            r"\b(iska|uska|unka|iske|uske|is)\b.*(mythology|age|comparison|kya hai)",
            r"\b(cheaper one|sasta wala|dusra wala|pehle do|dono)\b",
            r"^(this|that|these|those|it|again|more|next)$"
        ]
        for pat in short_patterns:
            if re.search(pat, t):
                return True

        # Check for demonstrative / elliptical words when phrase is very short
        words = t.split()
        if len(words) <= 3 and any(w in words for w in ["this", "that", "it", "one", "second", "both", "again", "more", "next", "cheaper", "sasta", "pehle", "dusra", "iska"]):
            return True

        return False

    def resolve(self, raw_input: str) -> ResolvedIntent:
        """Resolves raw user input into an unambiguous, contextualized instruction."""
        text = str(raw_input or "").strip()
        t_lower = text.lower()

        if not self.is_elliptical_hint(text):
            return ResolvedIntent(
                is_short_hint=False,
                resolved_query=text,
                confidence=1.0
            )

        # 1. Price / Attribute filter (e.g. "Under 70k", "70 hazaar ke andar", "Under 50000")
        filter_match = re.search(r"(?:under|below|less than|ke andar|budget)\s*([\d,]+(?:\s*[kK]|(?:\s*hazaar|\s*thousand))?)", t_lower)
        if filter_match and self._browser_state.get("last_query"):
            budget_str = filter_match.group(1).replace(",", "").strip()
            base_q = self._browser_state["last_query"]
            expanded = f"{base_q} under {budget_str}"
            self._browser_state["last_query"] = expanded
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query=expanded,
                target_entity=budget_str,
                action_type="SEARCH",
                confidence=0.95,
                referenced_context_type="BROWSER_STATE"
            )

        # 2. Sequential comparison (e.g. "Pehle do compare karo", "Compare the first two", "Compare both")
        if any(w in t_lower for w in ["compare", "compare the first two", "pehle do compare", "compare both"]):
            base_q = self._browser_state.get("last_query") or self._last_topic or "results"
            expanded = f"Compare top 2 items from current search results for '{base_q}'"
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query=expanded,
                action_type="BROWSER_COMPARE",
                confidence=0.92,
                referenced_context_type="BROWSER_STATE"
            )

        # 3. Item selection (e.g. "Open the cheaper one", "Show me the second one", "Dusra dikhao")
        if any(w in t_lower for w in ["open the cheaper one", "cheaper one", "sasta wala"]):
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query="Select and open the item with the lowest price in active results",
                action_type="BROWSER_NAVIGATE",
                confidence=0.90,
                referenced_context_type="BROWSER_STATE"
            )

        if any(w in t_lower for w in ["second one", "dusra", "show the second", "show me the second"]):
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query="Select and display details for item #2 in active list",
                action_type="BROWSER_SELECT",
                confidence=0.93,
                referenced_context_type="BROWSER_STATE"
            )

        # 4. Cross-domain specialist query (e.g. "Iska mythology mein koi comparison hai?")
        if any(w in t_lower for w in ["mythology mein koi comparison", "mythology comparison", "mythological parallel"]):
            topic = self._last_topic or "black holes and cosmic singularities"
            expanded = f"Explain mythological parallels and comparisons for {topic}"
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query=expanded,
                target_entity=topic,
                action_type="SPECIALIST",
                confidence=0.96,
                referenced_context_type="CONVERSATION_HISTORY"
            )

        # 5. Age follow-up (e.g. "What about his age?", "Is person ki approximate age batao")
        if any(w in t_lower for w in ["his age", "her age", "their age", "approximate age", "age batao"]):
            topic = self._last_topic or "the currently referenced person or subject"
            expanded = f"Estimate the approximate age range for {topic}"
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query=expanded,
                target_entity=topic,
                action_type="SPECIALIST",
                confidence=0.94,
                referenced_context_type="CONVERSATION_HISTORY"
            )

        # 6. PDF conversion (e.g. "Make this into a PDF")
        if any(w in t_lower for w in ["make this into a pdf", "pdf bana do", "create pdf of this"]):
            topic = self._last_topic or "Technical Briefing"
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query=f"Generate a structured PDF report on topic: {topic}",
                target_entity=topic,
                action_type="PDF",
                confidence=0.95,
                referenced_context_type="CONVERSATION_HISTORY"
            )

        # 7. File location query (e.g. "Kahan pe rakha hai", "Where did you save it", "File nahi mil rahi")
        if any(w in t_lower for w in ["kaha pe rakha", "kaha save", "kahan save", "where is the file", "where did you save", "file nahi mil", "file ni mil", "dubara kehne pe", "dubara search", "kidhar save", "kidhar rakha"]):
            try:
                from core.file_tracker import get_file_tracker
                latest = get_file_tracker().get_latest_file()
                if latest:
                    loc_name = latest.get("name", "document")
                    loc_path = latest.get("path", "")
                    return ResolvedIntent(
                        is_short_hint=True,
                        resolved_query=f"Locate and show path of recently saved file: '{loc_name}' at `{loc_path}`",
                        target_entity=loc_path,
                        action_type="FILE_LOCATE",
                        confidence=0.98,
                        referenced_context_type="ACTIVE_FILE"
                    )
            except Exception:
                pass

        # 8. File open / preview query (e.g. "Wo file kholo", "Open that file", "Preview the pdf", "Wo pdf dikhao")
        if any(w in t_lower for w in ["wo file", "woh file", "open the file", "preview the file", "open that file", "file open karo", "wo pdf", "open that pdf", "pdf dikhao", "preview that", "open preview"]):
            try:
                from core.file_tracker import get_file_tracker
                latest = get_file_tracker().get_latest_file()
                if latest:
                    loc_name = latest.get("name", "document")
                    loc_path = latest.get("path", "")
                    return ResolvedIntent(
                        is_short_hint=True,
                        resolved_query=f"Open and preview the file '{loc_name}' located at `{loc_path}` in system viewer",
                        target_entity=loc_path,
                        action_type="FILE_PREVIEW",
                        confidence=0.98,
                        referenced_context_type="ACTIVE_FILE"
                    )
            except Exception:
                pass

        # Default fallback context anchoring
        if self._last_topic:
            expanded = f"{text} (regarding {self._last_topic})"
            return ResolvedIntent(
                is_short_hint=True,
                resolved_query=expanded,
                target_entity=self._last_topic,
                action_type="GENERAL_QUERY",
                confidence=0.80,
                referenced_context_type="CONVERSATION_HISTORY"
            )

        return ResolvedIntent(
            is_short_hint=True,
            resolved_query=text,
            confidence=0.70
        )


_resolver: Optional[ContextResolver] = None


def get_context_resolver() -> ContextResolver:
    global _resolver
    if _resolver is None:
        _resolver = ContextResolver()
    return _resolver
