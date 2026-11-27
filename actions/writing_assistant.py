"""
actions/writing_assistant.py — AI-Powered Writing & Communication Assistant for JARVIS
Contributed by Aman Kumar (@iamTechieAman).

Supports:
  - Drafting professional or casual emails
  - Crafting message replies
  - Writing engaging social media captions / hooks
  - Summarizing long text
  - Polishing and refining grammar/tone
"""
from __future__ import annotations

import logging
from typing import Optional

from core import gemini

logger = logging.getLogger("writing_assistant")


def writing_assistant(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = (params.get("action") or "draft_email").lower().strip()
    topic = params.get("topic") or params.get("prompt") or params.get("text") or ""
    recipient = params.get("recipient") or params.get("to") or "Colleague"
    tone = params.get("tone") or "professional"
    platform_name = params.get("platform") or "General"

    if not topic:
        return "Please specify what you would like me to write or draft, sir."

    if action in ("email", "draft_email", "mail"):
        prompt = (
            f"Draft a clear, well-structured {tone} email to {recipient} about: {topic}.\n"
            "Format with Subject line and Body. Keep it concise, natural, and ready to send."
        )
        title = f"Email Draft ({tone.title()} to {recipient})"

    elif action in ("reply", "craft_reply", "respond"):
        prompt = (
            f"Write a {tone} reply to the following message/email:\n\"{topic}\"\n"
            "Keep it polite, direct, and effective."
        )
        title = "Suggested Reply"

    elif action in ("caption", "social", "post", "tweet"):
        prompt = (
            f"Create 3 punchy, engaging social media captions/posts for {platform_name} with relevant hashtags "
            f"about: {topic}. Tone: {tone}."
        )
        title = f"Social Captions ({platform_name})"

    elif action in ("summarize", "summary", "tldr"):
        prompt = (
            f"Provide a concise executive summary of the following text with key bullet points:\n\n{topic}"
        )
        title = "Summary & Key Points"

    elif action in ("polish", "improve", "rewrite", "fix_grammar"):
        prompt = (
            f"Rewrite and polish the following text for clarity, high impact, and flawless grammar ({tone} tone):\n\n\"{topic}\""
        )
        title = "Polished Text"

    else:
        prompt = f"Write high-quality {tone} content about: {topic}"
        title = "Draft Content"

    # Generate draft via core.gemini
    draft = None
    try:
        draft = gemini.text(prompt, tier=gemini.SMART)
    except Exception as e:
        logger.warning(f"Gemini SMART writing failed: {e}")

    if not draft:
        try:
            draft = gemini.text(prompt, tier=gemini.FAST)
        except Exception as e:
            logger.warning(f"Gemini FAST writing failed: {e}")

    if not draft:
        draft = (
            f"Subject: {topic.title()}\n\n"
            f"Dear {recipient},\n\n"
            f"I am writing to discuss {topic}. Please let me know your thoughts.\n\n"
            "Best regards,\nAman"
        )

    # Present draft in HUD
    if player and hasattr(player, "show_content"):
        card = f"# ✍️ {title}\n\n{draft}"
        player.show_content(title, card)

    if player and hasattr(player, "write_log"):
        player.write_log(f"Writing Assistant: Generated {title.lower()}.")

    # Short spoken summary response
    first_line = draft.strip().split("\n")[0].replace("#", "").strip()
    return f"I have prepared the draft for you, sir: {first_line}. The full text is displayed in your HUD."


TOOL = {
    "name": "writing_assistant",
    "description": "AI-powered writing assistant for emails, message replies, social media captions, summaries, and text polishing.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "draft_email | reply | caption | summarize | polish"
            },
            "topic": {
                "type": "STRING",
                "description": "Topic, incoming message, or text to draft or summarize"
            },
            "recipient": {
                "type": "STRING",
                "description": "Recipient name (for emails)"
            },
            "tone": {
                "type": "STRING",
                "description": "professional | casual | persuasive | concise (default: professional)"
            },
            "platform": {
                "type": "STRING",
                "description": "Platform for captions (e.g. LinkedIn, Twitter, Instagram, YouTube)"
            }
        },
        "required": [
            "topic"
        ]
    },
    "handler": writing_assistant,
}

run = writing_assistant
