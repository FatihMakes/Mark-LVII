"""actions/creator_info.py — Creator & Owner Lineage Action for JARVIS H3.2
Contributed by Aman Kumar (@iamTechieAman).

Handles queries regarding creator identity, owner authority, and system history.
"""
from __future__ import annotations

from core.creator_profile import get_creator_manager
from core.creator_brain import get_creator_brain


def creator_info(parameters: dict, player=None, session_memory=None) -> str:
    """Answers queries regarding creator, registered owner, and collaborative history."""
    query = (parameters.get("query") or parameters.get("topic") or "creator").lower().strip()
    cm = get_creator_manager()
    brain = get_creator_brain()
    emotion = brain.detect_emotional_tone(query)
    prefix = brain.format_empathetic_prefix(emotion, cm.get_profile().preferred_address)

    response_text = ""
    if any(w in query for w in ["who created", "who made", "creator", "architect", "built you"]):
        response_text = cm.answer_who_created_you()
    elif any(w in query for w in ["owner", "who owns", "whose jarvis"]):
        response_text = cm.answer_who_is_your_owner()
    elif any(w in query for w in ["tell me about", "about creator", "about aman"]):
        response_text = cm.answer_tell_me_about_creator()
    elif any(w in query for w in ["about me", "know about me", "my profile"]):
        response_text = cm.answer_what_do_you_know_about_me()
    elif any(w in query for w in ["how long", "together", "working together", "since when"]):
        response_text = cm.answer_how_long_working_together()
    else:
        response_text = cm.answer_who_created_you()

    if prefix:
        response_text = f"{prefix} {response_text}"

    if player and hasattr(player, "write_log"):
        player.write_log(f"CREATOR: Query processed for {cm.get_profile().preferred_address}")

    if player and hasattr(player, "show_content"):
        player.show_content(f"JARVIS — Creator & Lineage Intelligence", response_text)

    return response_text


creator_info_handler = creator_info


TOOL = {
    "name": "creator_info",
    "description": (
        "Answers queries regarding who created JARVIS, who its registered owner is, "
        "what it knows about its creator (Aman Kumar), and system lineage."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Question: 'who created you' | 'who is your owner' | 'tell me about your creator' | 'what do you know about me' | 'how long have we been working together'"
            }
        }
    },
    "handler": creator_info,
}

run = creator_info
