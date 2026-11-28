"""
core/language_detector.py — Dynamic Language Detection and Adaptation for JARVIS.
Contributed by Aman Kumar (@iamTechieAman).

Accurately detects whether the speaker is communicating in English, Hindi (Devanagari),
or Hinglish (Romanized Hindi/Urdu), or another language, enabling JARVIS to
dynamically mirror and adapt its response language turn-by-turn without getting stuck.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# Common conversational Hindi/Urdu words written in Latin/Roman script (Hinglish)
_HINGLISH_WORDS = {
    # Pronouns & pointers
    "aap", "aapka", "aapki", "aapke", "aapko", "tum", "tumhara", "tumhari", "tumhare",
    "main", "mera", "meri", "mere", "mujhe", "mujhko", "hum", "hamara", "hamari",
    "yeh", "ye", "woh", "wo", "iska", "iski", "iske", "isko", "uska",
    "uski", "uske", "usko", "inka", "unka", "inko", "unko", "kisi", "kisko",
    # Question words
    "kya", "kyu", "kyun", "kaise", "kaisa", "kaisi", "kab", "kaha", "kahan", "kidhar", "kitna", "kitne", "kitni",
    # Auxiliary verbs & tenses
    "hai", "hain", "hoon", "hun", "tha", "the", "thi", "hoga", "hogi", "hoge",
    "raha", "rahe", "rahi", "huye", "hue", "gaya", "gaye", "gayi", "chahiye", "sakta", "sakte", "sakti",
    # Common action verbs
    "karo", "karna", "karke", "karenge", "karta", "karti", "kardo", "batao", "bataiye",
    "bolo", "boliye", "bhejo", "bhej", "kholo", "chalao", "chala",
    "dekho", "dekh", "suno", "sun", "aao", "jao", "chalo", "ruko", "samjhao", "dhoondo",
    "lagao", "hatao", "badlo", "rakho", "dena", "dedo",
    # Connectors, adverbs & particles
    "aur", "lekin", "magar", "bhi", "toh", "se", "ko", "ke", "ki", "ka",
    "nahi", "nahin", "theek", "thik", "acha", "achha", "achi", "achhi",
    "bahut", "bohot", "thoda", "thodi", "jaldi", "abhi", "baad", "pehle", "saath",
    "bhai", "bhaiya", "yaar",
    # Domain words in conversational Hindi
    "mausam", "samay", "waqt", "aaj", "kal", "parso", "subah", "shaam", "raat",
    "gana", "gaana", "aawaz", "awaaz", "khabar", "baat", "kaam", "cheez"
}

# Common English structural and conversational words
_ENGLISH_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for",
    "not", "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by",
    "from", "they", "we", "say", "her", "she", "or", "an", "will", "my", "one", "all",
    "would", "there", "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no", "just", "him",
    "know", "take", "people", "into", "year", "your", "good", "some", "could", "them",
    "see", "other", "than", "then", "now", "look", "only", "come", "its", "over",
    "think", "also", "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these", "give", "day",
    "most", "us", "please", "open", "play", "search", "check", "send", "turn", "volume",
    "mute", "unmute", "weather", "news", "reminder", "timer", "file", "desktop", "browser",
    "system", "status", "screen", "camera", "battery", "wifi", "bluetooth", "brightness"
}

# Devanagari Unicode Block: U+0900 to U+097F
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def detect_language(text: str) -> str:
    """
    Detects whether the given transcript is in HINDI (Devanagari),
    HINGLISH (Romanized Hindi), ENGLISH, or OTHER.

    Returns:
        "HINDI" | "HINGLISH" | "ENGLISH" | "UNKNOWN"
    """
    raw = str(text or "").strip()
    if not raw:
        return "ENGLISH"

    # 1. Check for Devanagari characters
    devanagari_chars = _DEVANAGARI_RE.findall(raw)
    if len(devanagari_chars) >= 2 or (len(raw) <= 5 and len(devanagari_chars) >= 1):
        return "HINDI"

    # 2. Tokenize Latin words
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z']+\b", raw)]
    if not words:
        return "ENGLISH"

    hinglish_count = 0
    english_count = 0

    for w in words:
        clean_w = w.strip("'")
        if clean_w in _HINGLISH_WORDS:
            hinglish_count += 1
        if clean_w in _ENGLISH_WORDS:
            english_count += 1

    # Ratio evaluation
    total_matches = hinglish_count + english_count
    if total_matches == 0:
        return "ENGLISH"

    # If significant Hinglish tokens are present (e.g. "kya haal hai", "yeh file bhej do", "aaj mausam kaisa hai")
    if hinglish_count >= 2 or (hinglish_count >= 1 and english_count <= 1 and len(words) <= 4):
        return "HINGLISH"

    if english_count >= hinglish_count:
        return "ENGLISH"

    return "HINGLISH" if hinglish_count > english_count else "ENGLISH"


def get_language_directive(detected_language: str) -> str:
    """
    Returns a crisp, unambiguous system directive for the model to respond
    in the detected language for the current turn.
    """
    lang = detected_language.upper()
    if lang == "HINDI":
        return (
            "[LANGUAGE REQUIREMENT: HINDI]\n"
            "The user is speaking in Hindi (हिंदी). You MUST formulate and speak your response "
            "entirely in natural, polite Hindi."
        )
    elif lang == "HINGLISH":
        return (
            "[LANGUAGE REQUIREMENT: HINGLISH]\n"
            "The user is speaking in Hinglish (conversational Hindi in Roman script). "
            "You MUST respond in natural, friendly Hinglish/conversational Hindi (e.g. 'Ji sir, main abhi check karta hoon')."
        )
    else:  # ENGLISH
        return (
            "[LANGUAGE REQUIREMENT: ENGLISH]\n"
            "The user is speaking in English. You MUST formulate and speak your response "
            "entirely in crisp, polished English. Do not switch to Hindi."
        )
