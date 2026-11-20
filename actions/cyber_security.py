"""
Cyber Security & Network Defense Action for JARVIS.
Provides network reconnaissance, port scanning, SSL/TLS certificate auditing,
HTTP security header evaluation, hash identification, and local listening socket monitoring.
"""

from __future__ import annotations

import math
import os
import re
import socket
import ssl
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle",
    3000: "Dev-Web (React/Node)",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    8000: "HTTP-Alt",
    8080: "HTTP-Proxy/Tomcat",
    8443: "HTTPS-Alt",
    9000: "SonarQube/PHP-FPM",
    11434: "Ollama LLM",
    27017: "MongoDB",
}

def scan_ports(host: str, ports: Optional[List[int]] = None, timeout: float = 1.0) -> dict:
    """Safe TCP port scan on target host."""
    clean_host = host.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip()
    target_ports = ports or list(COMMON_PORTS.keys())
    open_ports = []

    try:
        ip = socket.gethostbyname(clean_host)
    except Exception as e:
        return {"error": f"Could not resolve host '{clean_host}': {e}"}

    for p in target_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            result = s.connect_ex((ip, p))
            if result == 0:
                service = COMMON_PORTS.get(p, "Unknown")
                open_ports.append({"port": p, "service": service, "state": "OPEN"})
        except Exception:
            pass
        finally:
            s.close()

    return {
        "host": clean_host,
        "ip": ip,
        "total_scanned": len(target_ports),
        "open_count": len(open_ports),
        "open_ports": open_ports,
    }

def audit_ssl(host: str, port: int = 443) -> dict:
    """Audit SSL/TLS certificate, cipher suites, and expiry."""
    clean_host = host.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip()
    ctx = ssl.create_default_context()
    
    try:
        with socket.create_connection((clean_host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=clean_host) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()

                # Parse validity
                not_before = cert.get("notBefore", "")
                not_after = cert.get("notAfter", "")
                subject = dict(x[0] for x in cert.get("subject", []))
                issuer = dict(x[0] for x in cert.get("issuer", []))
                san = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]

                # Expiry check
                import datetime
                exp_date = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                days_left = (exp_date - datetime.datetime.utcnow()).days

                status = "VALID" if days_left > 14 else ("EXPIRING SOON" if days_left > 0 else "EXPIRED")

                return {
                    "host": clean_host,
                    "status": status,
                    "days_remaining": days_left,
                    "valid_until": not_after,
                    "issuer": issuer.get("organizationName", issuer.get("commonName", "Unknown")),
                    "subject": subject.get("commonName", clean_host),
                    "tls_version": version,
                    "cipher": cipher[0] if cipher else "Unknown",
                    "subject_alt_names": san[:5],
                }
    except Exception as e:
        return {"error": f"SSL Handshake failed for {clean_host}:{port} - {e}"}

def audit_http_headers(url: str) -> dict:
    """Audit HTTP security headers and calculate security rating."""
    target_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
    req = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0 JARVIS Security Scanner"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        headers = {k.lower(): v for k, v in e.headers.items()}
    except Exception as e:
        return {"error": f"Could not reach {target_url}: {e}"}

    checks = {
        "strict-transport-security": "HSTS (Enforces HTTPS encryption)",
        "content-security-policy": "CSP (Protects against XSS and code injection)",
        "x-frame-options": "X-Frame-Options (Protects against Clickjacking)",
        "x-content-type-options": "X-Content-Type-Options (Prevents MIME sniffing)",
        "referrer-policy": "Referrer-Policy (Controls referrer leakage)",
        "permissions-policy": "Permissions-Policy (Restricts browser features/APIs)",
    }

    found = []
    missing = []
    for h, desc in checks.items():
        if h in headers:
            found.append({"header": h, "description": desc, "value": headers[h][:60]})
        else:
            missing.append({"header": h, "description": desc})

    score = round((len(found) / len(checks)) * 100)
    grade = "A" if score >= 85 else ("B" if score >= 65 else ("C" if score >= 40 else "F"))

    return {
        "url": target_url,
        "security_grade": grade,
        "score": f"{score}%",
        "found_headers": found,
        "missing_headers": missing,
        "server": headers.get("server", "Hidden"),
    }

def identify_hash_or_eval_password(text: str) -> dict:
    """Identify cryptographic hash type or evaluate password complexity."""
    clean = text.strip()
    length = len(clean)
    is_hex = bool(re.match(r"^[0-9a-fA-F]+$", clean))

    possible_hashes = []
    if is_hex:
        if length == 32: possible_hashes.append("MD5 or NTLM")
        elif length == 40: possible_hashes.append("SHA-1")
        elif length == 64: possible_hashes.append("SHA-256")
        elif length == 128: possible_hashes.append("SHA-512")
    elif clean.startswith(("$2a$", "$2b$", "$2y$")) and length == 60:
        possible_hashes.append("bcrypt")
    elif clean.startswith("$argon2"):
        possible_hashes.append("Argon2")

    # If it's a plaintext password being assessed:
    entropy = 0.0
    pool = 0
    if re.search(r"[a-z]", clean): pool += 26
    if re.search(r"[A-Z]", clean): pool += 26
    if re.search(r"[0-9]", clean): pool += 10
    if re.search(r"[^a-zA-Z0-9]", clean): pool += 32
    if pool > 0:
        entropy = round(length * math.log2(pool), 1)

    strength = "Very Strong" if entropy >= 65 else ("Strong" if entropy >= 50 else ("Moderate" if entropy >= 35 else "Weak"))

    return {
        "input_length": length,
        "identified_hash_algorithms": possible_hashes or ["Not a recognized single-string hash (likely plaintext password or token)"],
        "entropy_bits": entropy,
        "strength_assessment": strength,
    }

def list_local_listening_sockets() -> List[dict]:
    """List open listening ports and active sockets on the local host."""
    results = []
    try:
        import psutil
        for c in psutil.net_connections(kind="inet"):
            if c.status == psutil.CONN_LISTEN:
                laddr = f"{c.laddr.ip}:{c.laddr.port}"
                try:
                    proc = psutil.Process(c.pid).name() if c.pid else "System"
                except Exception:
                    proc = "Unknown"
                results.append({
                    "port": c.laddr.port,
                    "address": laddr,
                    "pid": c.pid,
                    "process": proc,
                })
    except Exception as e:
        results.append({"error": str(e)})
    return sorted(results, key=lambda x: x.get("port", 0))

def cyber_security(parameters: dict, player=None, session_memory=None) -> str:
    """Entry handler for cyber_security."""
    action = parameters.get("action", "scan_ports").lower().strip()
    target = parameters.get("target", "").strip()

    if player:
        try: player.write_log(f"SEC: Executing {action} on {target or 'localhost'}...")
        except Exception: pass

    if action in ("scan_ports", "port_scan", "nmap"):
        if not target: target = "127.0.0.1"
        res = scan_ports(target)
        if "error" in res: return f"Port scan error: {res['error']}"
        open_list = "\n".join(f"  • Port {p['port']}/TCP: {p['service']}" for p in res["open_ports"]) or "  • No open ports found in common range."
        return f"🛡️ Port Scan Results for `{res['host']}` ({res['ip']}):\nScanned: {res['total_scanned']} ports | Open: {res['open_count']}\n{open_list}"

    elif action in ("ssl", "cert", "tls"):
        if not target: return "Please provide target domain for SSL audit."
        res = audit_ssl(target)
        if "error" in res: return res["error"]
        return (
            f"🔒 SSL/TLS Security Audit for `{res['host']}`:\n"
            f"• Status: **{res['status']}** ({res['days_remaining']} days remaining)\n"
            f"• Valid Until: {res['valid_until']}\n"
            f"• Issuer: {res['issuer']}\n"
            f"• Protocol: {res['tls_version']} | Cipher: {res['cipher']}\n"
            f"• SANs: {', '.join(res['subject_alt_names'])}"
        )

    elif action in ("headers", "http_headers", "web_audit"):
        if not target: return "Please provide URL for HTTP headers audit."
        res = audit_http_headers(target)
        if "error" in res: return res["error"]
        missing_str = "\n".join(f"  ❌ Missing: {m['header']} — {m['description']}" for m in res["missing_headers"])
        found_str = "\n".join(f"  ✅ Present: {f['header']}" for f in res["found_headers"])
        return (
            f"🌐 HTTP Security Headers Audit for `{res['url']}`:\n"
            f"• Grade: **{res['security_grade']}** (Score: {res['score']})\n"
            f"• Server: {res['server']}\n"
            f"{found_str}\n"
            f"{missing_str}"
        )

    elif action in ("hash", "password", "crypto"):
        if not target: return "Please provide hash string or password to evaluate."
        res = identify_hash_or_eval_password(target)
        algos = ", ".join(res["identified_hash_algorithms"])
        return f"🔐 Cryptographic Analysis:\n• Possible Algorithm: {algos}\n• Entropy: {res['entropy_bits']} bits ({res['strength_assessment']})"

    elif action in ("listening", "local_ports", "sockets"):
        socks = list_local_listening_sockets()
        lines = [f"🖥️ Local Listening Ports on Host ({len(socks)} active):"]
        for s in socks[:15]:
            if "error" in s: lines.append(f"Error: {s['error']}")
            else: lines.append(f"• Port {s['port']} ({s['address']}) → PID {s['pid']} [{s['process']}]")
        return "\n".join(lines)

    return f"Cyber security action '{action}' completed."


TOOL = {
    "name": "cyber_security",
    "description": (
        "Cyber Security & Defense Analysis suite. Performs TCP port scanning, SSL/TLS certificate auditing, "
        "HTTP security header evaluations (HSTS, CSP, X-Frame-Options), cryptographic hash identification, "
        "password entropy assessments, and local listening socket monitoring."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "scan_ports | ssl | headers | hash | listening",
            },
            "target": {
                "type": "STRING",
                "description": "Target hostname, IP, URL, hash string, or password to analyze",
            }
        },
        "required": ["action"],
    },
    "handler": cyber_security,
}
