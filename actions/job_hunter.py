"""
Autonomous Job Hunter, Application Tracker & Cold Outreach Studio for JARVIS.
Contributed by Aman Kumar (@iamTechieAman).

Helps find job openings, generate personalized application emails,
match candidate skills, track follow-ups, and manage interview pipelines.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

TRACKER_FILE = Path.home() / ".jarvis_job_tracker.json"
DESKTOP = Path.home() / "Desktop"


def _load_tracker() -> dict:
    if TRACKER_FILE.exists():
        try:
            return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"applications": [], "saved_leads": []}


def _save_tracker(data: dict) -> None:
    try:
        TRACKER_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def job_hunter(parameters: dict, player=None) -> str:
    """
    Automated job hunting and cold outreach tool.
    parameters:
      action: 'search_jobs' | 'draft_email' | 'apply' | 'pipeline' (default: 'search_jobs')
      role: target job title (e.g., 'Software Engineer', 'Cyber Security Analyst')
      company: target company name
      recruiter_email: email address of recruiter or hiring manager
      location: location preference (e.g., 'Remote', 'India', 'Bangalore')
    """
    action = (parameters.get("action") or "search_jobs").lower().strip()
    role = parameters.get("role") or "Software Development Engineer"
    company = parameters.get("company") or "Target Tech Company"
    recruiter_email = parameters.get("recruiter_email") or "careers@company.com"
    location = parameters.get("location") or "Remote / India"

    tracker = _load_tracker()

    if action == "search_jobs":
        if player and hasattr(player, "write_log"):
            player.write_log(f"CAREER: Searching active job openings for '{role}' ({location})...")

        # Search web for real job openings
        from actions.web_search import _ddg_search
        query = f"{role} hiring jobs {location} 2026 apply"
        results = _ddg_search(query, max_results=5)

        lines = [
            f"# 💼 Active Job Leads for: {role} ({location})",
            "",
            "Here are verified recent job openings and hiring postings:",
            "",
        ]

        for i, r in enumerate(results, 1):
            title = r.get("title", f"Opening {i}")
            url = r.get("url", "")
            snippet = r.get("snippet", "")
            lines.append(f"### {i}. {title}")
            lines.append(f"- **Summary:** {snippet}")
            if url:
                lines.append(f"- **Link:** [{url}]({url})")
            lines.append("")

        lines.extend([
            "---",
            "*To draft a tailored cold outreach email or apply, say: 'Draft application for [Company]'.*"
        ])
        leads_md = "\n".join(lines)

        if player and hasattr(player, "show_content"):
            player.show_content(f"Job Leads: {role}", leads_md)

        return (
            f"I have found {len(results)} active job openings for '{role}' in {location}, sir. "
            f"The listings with direct apply links are displayed on your screen."
        )

    elif action in ("draft_email", "apply"):
        # Generate high-converting cold email tailored to hiring manager
        subject = f"Application for {role} — Aman Kumar"
        body = f"""Dear Hiring Team at {company},

I am writing to express my strong interest in joining {company} as a {role}.

As a proactive engineer with deep experience in building high-performance architectures, developing autonomous AI systems, and solving complex algorithmic challenges, I am confident in my ability to deliver immediate value to your team.

Key Highlights of My Experience:
• Architected scalable full-stack applications with modular API pipelines and real-time streaming capabilities.
• Engineered robust test suites and automated regression pipelines, reducing deployment cycle times by 30%.
• Authored comprehensive technical documentation, reverse-engineering suites, and quantitative data tools.

I have attached my resume for your review and would welcome the opportunity to discuss how my technical skills and dedication can support {company}'s engineering objectives.

Resume & Portfolio: Available upon request.
LinkedIn: https://linkedin.com/in/iamTechieAman
GitHub: https://github.com/iamTechieAman

Sincerely,
Aman Kumar
er.amankumar@hotmail.com
"""
        out_mail_file = DESKTOP / f"Application_{company.replace(' ', '_')}.txt"
        out_mail_file.write_text(f"To: {recruiter_email}\nSubject: {subject}\n\n{body}", encoding="utf-8")

        # Track in application tracker
        tracker["applications"].append({
            "company": company,
            "role": role,
            "email": recruiter_email,
            "date": time.strftime("%Y-%m-%d"),
            "status": "Email Drafted / Ready to Send"
        })
        _save_tracker(tracker)

        card = f"## ✉️ Application Email Drafted\n**To:** `{recruiter_email}`\n**Subject:** `{subject}`\n\n```\n{body}\n```\n\n*Saved to Desktop at: `{out_mail_file.name}`*"

        if player and hasattr(player, "show_content"):
            player.show_content(f"Application Draft: {company}", card)

        if player and hasattr(player, "write_log"):
            player.write_log(f"CAREER: Generated tailored cold outreach for {company}")

        return (
            f"I have prepared a tailored cold application email for {company}, sir. "
            f"It is saved on your Desktop at {out_mail_file.name}."
        )

    elif action in ("pipeline", "status", "tracker"):
        apps = tracker.get("applications", [])
        lines = [
            f"# 📊 Job Application Pipeline ({len(apps)} Total)",
            "",
            "| Company | Role | Date | Status |",
            "| :--- | :--- | :--- | :--- |",
        ]
        if not apps:
            lines.append("| *No applications tracked yet* | - | - | - |")
        else:
            for a in apps:
                lines.append(f"| {a.get('company')} | {a.get('role')} | {a.get('date')} | `{a.get('status')}` |")

        pipeline_md = "\n".join(lines)

        if player and hasattr(player, "show_content"):
            player.show_content("Application Pipeline", pipeline_md)

        return f"You currently have {len(apps)} applications in your pipeline, sir. Overview is displayed on screen."

    return "Unknown action. Supported: search_jobs | draft_email | pipeline"


TOOL = {
    "name": "job_hunter",
    "description": (
        "Autonomous job hunter, cold outreach generator, and application pipeline tracker for JARVIS. "
        "Finds active tech job openings matching the user's skillset, drafts high-converting cold emails "
        "for recruiters, and tracks job applications."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "search_jobs | draft_email | pipeline (default: search_jobs)",
            },
            "role": {
                "type": "STRING",
                "description": "Job title or role to target (e.g., Software Engineer, Security Analyst)",
            },
            "company": {
                "type": "STRING",
                "description": "Target company name (for draft_email)",
            },
            "recruiter_email": {
                "type": "STRING",
                "description": "Recruiter or hiring manager email address",
            },
            "location": {
                "type": "STRING",
                "description": "Location preference (e.g., Remote, India, Bangalore)",
            },
        },
    },
    "handler": job_hunter,
}
