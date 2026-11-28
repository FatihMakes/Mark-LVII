"""
plugins/omninet_supertool.py — Universal Internet & Web Automation Suite for JARVIS.
Contributed by Aman Kumar (@iamTechieAman).

Provides JARVIS with unrestricted web intelligence:
1. Deep article and webpage extraction & AI summarization from any URL
2. Full HTTP REST API & Webhook client (GET, POST, PUT, DELETE) with custom headers & payload
3. Live network diagnostics (DNS resolution, latency, uptime, SSL/HTTP status)
4. Real-time Crypto & Forex exchange rates (BTC, ETH, SOL, USD, INR, EUR, etc.)
5. Direct online resource & file downloading
6. Direct Wikipedia encyclopedia knowledge retrieval
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from core import gemini

PLUGIN = {
    "name": "omninet_supertool",
    "description": (
        "Universal Internet & Web automation suite. Use for ANY direct URL extraction, "
        "reading article/webpage content, sending HTTP REST API or Webhook requests (GET, POST, PUT, DELETE), "
        "checking website uptime, latency, DNS status, fetching live cryptocurrency and forex rates, "
        "or downloading online files directly to disk."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "The internet action to perform: "
                    "'read_webpage' (extract & summarize text from any URL), "
                    "'api_request' (call any REST API / Webhook with GET/POST/PUT/DELETE), "
                    "'site_status' (check uptime, ping latency, DNS and HTTP status of a domain), "
                    "'market_rates' (get live crypto prices like BTC/ETH or forex rates like USD/INR), "
                    "'download_file' (download a web resource or document to Downloads folder), "
                    "or 'wiki_lookup' (deep summary of any topic or person from Wikipedia)."
                ),
            },
            "url": {
                "type": "STRING",
                "description": "Target website URL or API endpoint for read_webpage, api_request, or download_file.",
            },
            "method": {
                "type": "STRING",
                "description": "HTTP method for api_request: GET | POST | PUT | DELETE | PATCH (default: GET).",
            },
            "headers": {
                "type": "OBJECT",
                "description": "Optional HTTP headers dictionary for api_request.",
            },
            "payload": {
                "type": "OBJECT",
                "description": "JSON payload or body for api_request POST/PUT.",
            },
            "query": {
                "type": "STRING",
                "description": "Topic for wiki_lookup, or currency/crypto symbols (e.g. 'BTC', 'USD to INR', 'ETH').",
            },
            "destination": {
                "type": "STRING",
                "description": "Optional download filename or target folder (default: Downloads).",
            },
        },
        "required": ["action"],
    },
}

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _read_webpage(url: str, player=None) -> str:
    """Fetch URL, strip noise, extract readable text, and produce an intelligent brief."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=12)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else url

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned_text = "\n".join(lines)
    truncated = cleaned_text[:8000]

    # Ask Gemini for structured takeaway
    prompt = (
        f"You are JARVIS. Summarize this webpage cleanly in 3-5 concise bullet points and 1 key takeaway.\n"
        f"Page Title: {title}\n"
        f"URL: {url}\n\n"
        f"Content:\n{truncated}"
    )
    summary = gemini.text(prompt, tier=gemini.FAST, default="Webpage extracted successfully.")

    card_content = (
        f"**Page:** [{title}]({url})\n\n"
        f"### 🌐 Key Takeaways\n{summary}\n\n"
        f"**Extracted Text Sample:**\n"
        f"```text\n{truncated[:600]}...\n```"
    )
    if player and hasattr(player, "show_content"):
        player.show_content(f"🌐 {title[:35]}", card_content)

    return f"Sir, I have extracted and summarized '{title}'. Details are presented on your panel."


def _api_request(url: str, method: str = "GET", headers: Optional[dict] = None, payload: Optional[dict] = None, player=None) -> str:
    """Execute raw HTTP REST API calls or Webhooks."""
    method = (method or "GET").upper().strip()
    req_headers = dict(_BROWSER_HEADERS)
    if headers:
        req_headers.update(headers)

    t0 = time.time()
    kwargs: dict[str, Any] = {"headers": req_headers, "timeout": 15}
    if payload is not None:
        kwargs["json"] = payload

    resp = requests.request(method, url, **kwargs)
    latency_ms = (time.time() - t0) * 1000

    content_type = resp.headers.get("content-type", "")
    is_json = "json" in content_type.lower()

    if is_json:
        try:
            body_fmt = json.dumps(resp.json(), indent=2)[:3000]
        except Exception:
            body_fmt = resp.text[:3000]
    else:
        body_fmt = resp.text[:3000]

    card_content = (
        f"**Endpoint:** `{method} {url}`\n"
        f"**Status:** `{resp.status_code} {resp.reason}` ({latency_ms:.1f}ms)\n\n"
        f"### 📦 Response Body\n"
        f"```{'json' if is_json else 'text'}\n{body_fmt}\n```"
    )
    if player and hasattr(player, "show_content"):
        player.show_content(f"⚡ {method} {resp.status_code}", card_content)

    return f"Request to {url} completed with HTTP status {resp.status_code} in {latency_ms:.0f} milliseconds."


def _site_status(target: str, player=None) -> str:
    """Diagnose domain health, IP resolution, latency, and HTTP response code."""
    raw_host = target.replace("https://", "").replace("http://", "").split("/")[0]

    dns_time_ms = 0.0
    ip_addr = "Unknown"
    try:
        t0 = time.time()
        ip_addr = socket.gethostbyname(raw_host)
        dns_time_ms = (time.time() - t0) * 1000
    except Exception as e:
        return f"Sir, DNS lookup failed for {raw_host}: {e}"

    http_time_ms = 0.0
    status_code = 0
    reason = "Failed"
    try:
        t0 = time.time()
        r = requests.get(f"https://{raw_host}", headers=_BROWSER_HEADERS, timeout=8)
        http_time_ms = (time.time() - t0) * 1000
        status_code = r.status_code
        reason = r.reason
    except Exception as e:
        reason = str(e)

    card = (
        f"### 📡 Domain Telemetry: `{raw_host}`\n\n"
        f"- **Resolved IP Address:** `{ip_addr}`\n"
        f"- **DNS Resolution Latency:** `{dns_time_ms:.1f} ms`\n"
        f"- **HTTP Handshake & Response:** `{status_code} {reason}`\n"
        f"- **Full Roundtrip Latency:** `{http_time_ms:.1f} ms`\n"
        f"- **Overall Health:** `{'🟢 ONLINE & HEALTHY' if 200 <= status_code < 400 else '🔴 DEGRADED / UNREACHABLE'}`\n"
    )
    if player and hasattr(player, "show_content"):
        player.show_content(f"📡 Diagnostics: {raw_host}", card)

    return f"Domain {raw_host} is reachable at IP {ip_addr} with response code {status_code} in {http_time_ms:.0f} ms."


def _market_rates(query: str, player=None) -> str:
    """Fetch live crypto (BTC/ETH/SOL) or fiat forex exchange rates."""
    query_upper = (query or "").upper()
    lines = ["### 📈 Real-Time Market & Exchange Rates\n"]

    # 1. Crypto check via Coinbase public API
    crypto_symbols = ["BTC", "ETH", "SOL"]
    crypto_data = []
    for sym in crypto_symbols:
        try:
            r = requests.get(f"https://api.coinbase.com/v2/prices/{sym}-USD/spot", timeout=4)
            if r.status_code == 200:
                price = float(r.json()["data"]["amount"])
                crypto_data.append(f"- **{sym}/USD:** `${price:,.2f}`")
        except Exception:
            pass

    if crypto_data:
        lines.append("#### 🪙 Cryptocurrencies")
        lines.extend(crypto_data)
        lines.append("")

    # 2. Fiat Forex check via Frankfurter API
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=INR,EUR,GBP,JPY,CAD", timeout=4)
        if r.status_code == 200:
            data = r.json()
            rates = data.get("rates", {})
            lines.append("#### 💵 Global Forex (Base USD)")
            for cur, val in rates.items():
                lines.append(f"- **USD / {cur}:** `{val}`")
    except Exception:
        pass

    result_md = "\n".join(lines)
    if player and hasattr(player, "show_content"):
        player.show_content("📈 Live Market Rates", result_md)

    return "Sir, live cryptocurrency and global exchange rates are compiled on your display."


def _wiki_lookup(query: str, player=None) -> str:
    """Instant deep Wikipedia lookup with summary and citations."""
    encoded = urllib.parse.quote(query)
    search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&utf8=&format=json"
    r = requests.get(search_url, headers={"User-Agent": "JARVIS-Assistant/1.0"}, timeout=6)
    data = r.json()
    items = data.get("query", {}).get("search", [])

    if not items:
        return f"Sir, no encyclopedia articles found for '{query}'."

    top_title = items[0]["title"]
    clean_title = urllib.parse.quote(top_title.replace(" ", "_"))

    summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_title}"
    r_sum = requests.get(summary_url, headers={"User-Agent": "JARVIS-Assistant/1.0"}, timeout=6)

    extract = ""
    page_url = f"https://en.wikipedia.org/wiki/{clean_title}"
    if r_sum.status_code == 200:
        sum_data = r_sum.json()
        extract = sum_data.get("extract", "")

    card = (
        f"### 📖 {top_title}\n\n"
        f"{extract}\n\n"
        f"**Read Full Article:** [{top_title}]({page_url})"
    )
    if player and hasattr(player, "show_content"):
        player.show_content(f"📖 {top_title[:35]}", card)

    return f"Sir, retrieved encyclopedia records for '{top_title}'. Details are on your HUD."


def _download_file(url: str, dest_name: str = "", player=None) -> str:
    """Download any web file/document to the Downloads folder with curl fallback."""
    import subprocess
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    if not dest_name:
        dest_name = url.split("?")[0].split("/")[-1] or "downloaded_file"
        if "." not in dest_name:
            dest_name += ".bin"

    target_path = downloads_dir / dest_name
    downloaded = False

    try:
        r = requests.get(url, headers=_BROWSER_HEADERS, stream=True, timeout=20)
        if r.status_code == 200:
            with open(target_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
            downloaded = target_path.exists() and target_path.stat().st_size > 0
    except Exception:
        pass

    if not downloaded:
        try:
            cmd = ["curl", "-sL", "-A", _BROWSER_HEADERS["User-Agent"], "-o", str(target_path), url]
            subprocess.run(cmd, timeout=30)
            downloaded = target_path.exists() and target_path.stat().st_size > 0
        except Exception as e:
            return f"Sir, download failed: {e}"

    if not downloaded or not target_path.exists():
        return f"Sir, could not retrieve the file from {url}."

    mb = target_path.stat().st_size / (1024 * 1024)
    if player and hasattr(player, "write_log"):
        player.write_log(f"OmniNet: Downloaded {dest_name} ({mb:.2f} MB)")

    return f"Sir, downloaded '{dest_name}' ({mb:.2f} MB) successfully to your Downloads directory."


def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Main plugin execution dispatcher.
    Runs asynchronously if needed to avoid blocking voice/HUD event loops.
    """
    params = parameters or {}
    action = str(params.get("action") or "").lower().strip()
    url = str(params.get("url") or "").strip()
    query = str(params.get("query") or "").strip()
    method = str(params.get("method") or "GET").strip()
    headers = params.get("headers")
    payload = params.get("payload")
    destination = str(params.get("destination") or "").strip()

    try:
        if action in ("read_webpage", "read", "extract", "summarize"):
            target_url = url or query
            if not target_url:
                return "Sir, please specify a webpage URL to extract."
            return _read_webpage(target_url, player=player)

        elif action in ("api_request", "webhook", "curl", "http"):
            target_url = url or query
            if not target_url:
                return "Sir, please provide the API endpoint or webhook URL."
            return _api_request(target_url, method=method, headers=headers, payload=payload, player=player)

        elif action in ("site_status", "ping", "uptime", "dns"):
            target = url or query
            if not target:
                return "Sir, please specify the domain or host to test."
            return _site_status(target, player=player)

        elif action in ("market_rates", "crypto", "forex", "rates", "prices"):
            return _market_rates(query, player=player)

        elif action in ("wiki_lookup", "wikipedia", "encyclopedia"):
            if not query:
                return "Sir, please specify a topic for the encyclopedia lookup."
            return _wiki_lookup(query, player=player)

        elif action in ("download_file", "download"):
            target_url = url or query
            if not target_url:
                return "Sir, please provide the URL of the file to download."
            return _download_file(target_url, dest_name=destination, player=player)

        else:
            # Fallback: if query given, try wiki or read_webpage
            if url:
                return _read_webpage(url, player=player)
            elif query:
                return _wiki_lookup(query, player=player)
            return "Sir, please specify an internet operation like read webpage, api request, site status, or market rates."

    except Exception as e:
        return f"Sir, OmniNet encountered an issue: {e}"
