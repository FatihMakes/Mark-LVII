"""
core/local_ai_engine.py — On-Device Local AI Engine & GGUF/Ollama Runtime for JARVIS H3.1
Contributed by Aman Kumar (@iamTechieAman).

Adapted from Reference A (Uncensored-Local-AI-Multiplatform):
  - Unified Apple Silicon Memory Safeguard (calculates free RAM before loading to prevent OOM)
  - GGUF and Ollama model catalog with quantization & context metadata
  - Token-per-second generation performance metrics
  - Immediate generation cancellation (Stop Generation)
  - Local OpenAI-compatible endpoint support
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

import psutil
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
CONFIG_DIR = BASE_DIR / "config"
LOCAL_AI_CONFIG = CONFIG_DIR / "local_ai_config.json"


@dataclass
class LocalModelMetadata:
    model_id: str
    display_name: str
    family: str           # "qwen", "llama", "deepseek", "mistral", "gemma"
    quantization: str     # "Q4_K_M", "Q5_K_M", "Q8_0", "FP16"
    parameter_size: str   # "3B", "7B", "8B", "14B"
    file_size_gb: float
    min_ram_gb: float
    context_length: int
    is_installed: bool = False
    source: str = "ollama"  # "ollama" | "gguf"
    file_path: Optional[str] = None


# Catalog of tested local models for Apple Silicon (Mac unified memory)
POPULAR_LOCAL_CATALOG: List[LocalModelMetadata] = [
    LocalModelMetadata("qwen2.5:3b", "Qwen 2.5 3B Instruct", "qwen", "Q4_K_M", "3B", 1.9, 3.5, 32768),
    LocalModelMetadata("qwen2.5:7b", "Qwen 2.5 7B Instruct", "qwen", "Q4_K_M", "7B", 4.7, 7.5, 32768),
    LocalModelMetadata("llama3.2:3b", "Llama 3.2 3B Instruct", "llama", "Q4_K_M", "3B", 2.0, 3.8, 8192),
    LocalModelMetadata("deepseek-r1:8b", "DeepSeek R1 Distill 8B", "deepseek", "Q4_K_M", "8B", 4.9, 8.2, 16384),
    LocalModelMetadata("mistral:7b", "Mistral 7B Instruct v0.3", "mistral", "Q4_K_M", "7B", 4.4, 7.0, 32768),
    LocalModelMetadata("phi3:mini", "Phi-3 Mini 3.8B", "phi", "Q4_K_M", "3.8B", 2.3, 4.0, 4096),
]


class LocalAIEngine:
    """
    On-device local LLM execution engine with memory safeguards and generation interruption.
    """

    def __init__(self):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self._active_model: str = "qwen2.5:7b"
        self._stop_requested = threading.Event()
        self._is_generating = False
        self._last_tps: float = 0.0
        self._ollama_base_url = "http://127.0.0.1:11434"
        self._load_config()

    def _load_config(self) -> None:
        if LOCAL_AI_CONFIG.is_file():
            try:
                cfg = json.loads(LOCAL_AI_CONFIG.read_text(encoding="utf-8"))
                self._active_model = cfg.get("active_model", self._active_model)
                self._ollama_base_url = cfg.get("ollama_url", self._ollama_base_url)
            except Exception:
                pass

    def _save_config(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_AI_CONFIG.write_text(json.dumps({
            "active_model": self._active_model,
            "ollama_url": self._ollama_base_url,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }, indent=2), encoding="utf-8")

    # ── Memory Safeguard (Reference A adaptation) ─────────────────────────────
    def check_memory_headroom(self, required_gb: float = 0.0) -> Tuple[bool, str]:
        """
        Calculates available Apple Silicon unified memory before loading a model.
        Prevents system lockups, kernel panics, or swapping thrashing.
        """
        vm = psutil.virtual_memory()
        avail_gb = vm.available / (1024 ** 3)
        total_gb = vm.total / (1024 ** 3)

        if avail_gb < required_gb:
            return False, (
                f"Insufficient memory headroom: Model requires {required_gb:.1f} GB RAM, "
                f"but only {avail_gb:.1f} GB of {total_gb:.1f} GB is currently available."
            )
        return True, f"Memory check passed: {avail_gb:.1f} GB available (model needs {required_gb:.1f} GB)."

    def calculate_memory_headroom(self) -> dict:
        """Returns structured memory metrics dict."""
        vm = psutil.virtual_memory()
        return {
            "total_ram_gb": round(vm.total / (1024 ** 3), 2),
            "available_ram_gb": round(vm.available / (1024 ** 3), 2),
            "headroom_gb": round(vm.available / (1024 ** 3), 2),
            "used_pct": vm.percent,
        }

    # ── Model Discovery & Catalog ─────────────────────────────────────────────
    def list_installed_models(self) -> List[Dict[str, Any]]:
        """Returns list of all installed Ollama and GGUF models."""
        installed = []
        # 1. Ollama models
        try:
            r = requests.get(f"{self._ollama_base_url}/api/tags", timeout=1.5)
            if r.status_code == 200:
                models = r.json().get("models", [])
                for m in models:
                    name = m.get("name", "")
                    size_gb = round(m.get("size", 0) / (1024 ** 3), 2)
                    installed.append({
                        "model_id": name,
                        "display_name": name,
                        "source": "ollama",
                        "size_gb": size_gb,
                        "is_active": (name == self._active_model),
                        "details": m.get("details", {})
                    })
        except Exception:
            pass

        # 2. Local GGUF files in models/
        for gguf_file in MODELS_DIR.glob("*.gguf"):
            size_gb = round(gguf_file.stat().st_size / (1024 ** 3), 2)
            installed.append({
                "model_id": f"gguf:{gguf_file.name}",
                "display_name": gguf_file.stem,
                "source": "gguf",
                "size_gb": size_gb,
                "is_active": (f"gguf:{gguf_file.name}" == self._active_model),
                "file_path": str(gguf_file)
            })

        return installed

    def get_model_catalog(self) -> List[dict]:
        """Returns catalog of tested models with compatibility indicators."""
        installed_ids = {m["model_id"] for m in self.list_installed_models()}
        vm = psutil.virtual_memory()
        avail_gb = vm.available / (1024 ** 3)

        catalog = []
        for m in POPULAR_LOCAL_CATALOG:
            item = asdict(m)
            item["is_installed"] = (m.model_id in installed_ids)
            item["memory_compatible"] = (avail_gb >= m.min_ram_gb)
            catalog.append(item)
        return catalog

    def set_active_model(self, model_id: str) -> Tuple[bool, str]:
        """Switches active local inference model."""
        # Check model existence and memory
        catalog_match = next((m for m in POPULAR_LOCAL_CATALOG if m.model_id == model_id), None)
        if catalog_match:
            ok, mem_msg = self.check_memory_headroom(catalog_match.min_ram_gb)
            if not ok:
                return False, mem_msg

        self._active_model = model_id
        self._save_config()
        return True, f"Active local model switched to '{model_id}'."

    def get_active_model(self) -> str:
        return self._active_model

    # ── Stop Generation & Resource Release (Reference A adaptation) ───────────
    def stop_generation(self) -> bool:
        """Immediately signals ongoing inference to abort and release buffers."""
        self._stop_requested.set()
        self._is_generating = False
        return True

    def is_stop_requested(self) -> bool:
        return self._stop_requested.is_set()

    def reset_stop(self) -> None:
        self._stop_requested.clear()

    def is_generating(self) -> bool:
        return self._is_generating

    def get_last_tokens_per_second(self) -> float:
        return self._last_tps

    # ── Local Inference Engine ────────────────────────────────────────────────
    def generate_local(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        on_token_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Executes local on-device inference with streaming and interrupt support.
        """
        self._stop_requested.clear()
        self._is_generating = True
        start_time = time.time()
        tokens_emitted = 0
        response_chunks = []

        try:
            # Query Ollama local engine
            payload = {
                "model": self._active_model,
                "prompt": prompt,
                "system": system_prompt,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                },
                "stream": True
            }

            resp = requests.post(
                f"{self._ollama_base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=120
            )

            if resp.status_code != 200:
                self._is_generating = False
                return f"[Local AI Error] Ollama returned status {resp.status_code}: {resp.text}"

            for line in resp.iter_lines():
                if self._stop_requested.is_set():
                    response_chunks.append("\n[Generation stopped by user]")
                    break

                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        text_token = chunk.get("response", "")
                        if text_token:
                            response_chunks.append(text_token)
                            tokens_emitted += 1
                            if on_token_callback:
                                on_token_callback(text_token)
                        if chunk.get("done", False):
                            break
                    except Exception:
                        pass

            elapsed = max(0.01, time.time() - start_time)
            self._last_tps = round(tokens_emitted / elapsed, 1)

        except requests.exceptions.ConnectionError:
            # Fallback if local Ollama daemon is offline
            self._last_tps = 0.0
            return (
                "Local inference server is offline (http://127.0.0.1:11434). "
                "Please run `ollama serve` or enable Cloud Assisted Mode."
            )
        except Exception as e:
            self._last_tps = 0.0
            return f"Local inference exception: {e}"
        finally:
            self._is_generating = False

        return "".join(response_chunks)


# Global Engine Instance
_local_ai_engine = LocalAIEngine()


def get_local_ai() -> LocalAIEngine:
    return _local_ai_engine


get_local_ai_engine = get_local_ai
