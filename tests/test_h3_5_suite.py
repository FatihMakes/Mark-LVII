"""
tests/test_h3_5_suite.py — Unit & Integration Test Suite for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Validates:
1. Real-time voice barge-in, double-talk detection, sub-300ms latency.
2. Startup owner face recognition, liveness, and personalized greeting.
3. Age Intelligence (human adult approximate range & artifact era).
4. Always-ready state transitions & macOS power management.
5. All 9 specialist GPT engines (Astro, Space, Mythology, Face, Age, Voice, Universal ID, Advisor, Philosopher).
6. Cross-specialist coordination (Space + Mythology).
7. Smart context resolver and short-hint conversational chaining.
8. Emotional intelligence & adaptive persona tone profiles.
9. Verified knowledge acquisition engine.
10. Specialist intelligence action integration.
"""

from __future__ import annotations

import unittest
import numpy as np

from core.barge_in import BargeInEngine, get_barge_in_engine
from core.always_ready import AlwaysReadyEngine, AssistantListeningState, get_always_ready_engine
from core.face_intelligence import FaceIntelligenceEngine, FaceDetectionResult, get_face_intelligence_engine
from core.specialist_orchestrator import SpecialistOrchestrator, get_specialist_orchestrator
from core.context_resolver import ContextResolver, get_context_resolver
from core.emotional_intelligence import EmotionalIntelligenceEngine, EmotionalState, get_emotional_engine
from core.knowledge_acquisition import KnowledgeAcquisitionEngine, get_knowledge_engine
from actions.specialist_intelligence import specialist_intelligence, TOOL


class TestH35MultimodalSpecialistSuite(unittest.TestCase):

    def setUp(self):
        self.barge_engine = get_barge_in_engine()
        self.always_ready = get_always_ready_engine()
        self.face_engine = get_face_intelligence_engine()
        self.orchestrator = get_specialist_orchestrator()
        self.context_resolver = get_context_resolver()
        self.emotional_engine = get_emotional_engine()
        self.knowledge_engine = get_knowledge_engine()

    # ── 1. Voice Barge-In & Interruption ──────────────────────────────────────

    def test_01_voice_barge_in_interruption_detection(self):
        """Verifies that sustained user voice during TTS triggers an interruption with < 300ms latency."""
        interrupted_flag = [False]

        def on_interrupt():
            interrupted_flag[0] = True

        engine = BargeInEngine(interrupt_callback=on_interrupt, sensitivity="high")

        # Simulate synthetic user voice audio block (high RMS above threshold)
        sr = 16000
        t = np.linspace(0, 0.05, int(sr * 0.05), endpoint=False)
        voice_block = (np.sin(2 * np.pi * 320 * t) * 18000).astype(np.int16)

        # Feed 2-3 consecutive blocks to simulate speech onset
        res1, lat1 = engine.process_mic_frame(voice_block, sr, is_speaking=True, current_out_level=0.1)
        res2, lat2 = engine.process_mic_frame(voice_block, sr, is_speaking=True, current_out_level=0.1)

        self.assertTrue(res2)
        self.assertTrue(interrupted_flag[0])
        self.assertIsNotNone(lat2)
        self.assertLess(lat2, 300.0)  # Must be sub-300ms

    # ── 2. Startup Face Recognition & Liveness ────────────────────────────────

    def test_02_face_recognition_and_liveness(self):
        """Verifies multi-frame liveness verification and personalized owner greeting."""
        # Generate two synthetic video frames with slight micro-motion
        frame1 = np.ones((200, 200, 3), dtype=np.uint8) * 120
        frame2 = frame1.copy()
        frame2[50:150, 50:150] = 135  # micro-variation simulating breathing/motion

        is_live, score = self.face_engine.verify_liveness([frame1, frame2])
        self.assertTrue(is_live)
        self.assertGreater(score, 0.0)

        # Startup greeting format
        mock_result = FaceDetectionResult(
            face_detected=True,
            is_owner_match=True,
            matched_owner_name="Aman Kumar",
            is_live=True
        )
        greeting = self.face_engine.generate_startup_greeting(mock_result)
        self.assertIn("Aman Kumar", greeting)
        self.assertIn("JARVIS is online", greeting)

    # ── 3. Age Intelligence ───────────────────────────────────────────────────

    def test_03_age_intelligence_human_and_artifact(self):
        """Verifies calibrated approximate age range and hardware era estimations."""
        # Human face synthetic test
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2 = __import__("cv2")
        cv2.circle(img, (100, 100), 50, (200, 200, 200), -1)

        age_res = self.face_engine.estimate_visual_age(img, target_type="human")
        self.assertIn("status", age_res)
        self.assertIn("disclaimer", age_res)

        # Object / device era test
        from core.specialists.age_gpt import AgeGPT
        age_gpt = AgeGPT()
        laptop_res = age_gpt.estimate_age(target_type="object", description="Modern aluminum laptop computer with USB-C")
        self.assertEqual(laptop_res["status"], "success")
        self.assertIn("computing_hardware", laptop_res["target_type"])
        self.assertIn("approx", laptop_res["estimated_age"].lower())

    # ── 4. Always-Ready & Power Management ────────────────────────────────────

    def test_04_always_ready_power_management(self):
        """Verifies state transitions and power telemetry."""
        self.always_ready.set_state(AssistantListeningState.ALWAYS_READY_LISTENING)
        self.assertEqual(self.always_ready.state, AssistantListeningState.ALWAYS_READY_LISTENING)

        self.always_ready.start_task("test_background_sync")
        telem = self.always_ready.get_power_telemetry()
        self.assertIn("battery_percent", telem)
        self.assertIn("thermal_pressure", telem)
        self.assertGreaterEqual(telem["active_tasks_count"], 1)

        self.always_ready.finish_task("test_background_sync")
        self.assertEqual(self.always_ready.get_power_telemetry()["active_tasks_count"], 0)

    # ── 5. Specialist GPT Ecosystem ───────────────────────────────────────────

    def test_05_specialist_gpt_astro(self):
        """Verifies Astro GPT calculates Kundli chart, rashis, and provides interpretive disclaimers."""
        res = self.orchestrator.route_query("Explain my Vedic Kundli and birth chart houses")
        self.assertTrue(res["handled"])
        self.assertIn("ASTRO", res["domains"])
        self.assertIn("Kundli", res["response"])
        self.assertIn("disclaimer", res["response"].lower())

    def test_06_specialist_gpt_space(self):
        """Verifies Space GPT provides physics breakdown with Event Horizon and primary citations."""
        res = self.orchestrator.route_query("Explain black holes and event horizons in cosmology")
        self.assertTrue(res["handled"])
        self.assertIn("SPACE", res["domains"])
        self.assertIn("Event Horizon", res["response"])
        self.assertIn("EHT", res["response"])

    def test_07_specialist_gpt_mythology(self):
        """Verifies Mythology GPT draws comparisons across Vedic and Greek traditions."""
        from core.specialists.mythology_gpt import MythologyGPT
        myth = MythologyGPT()
        res = myth.query("What is the mythological concept of cosmic darkness?")
        self.assertIn("Rigveda", res)
        self.assertIn("Hesiod", res)

    def test_08_cross_domain_specialist_coordination(self):
        """Verifies multi-specialist coordination for queries spanning Space and Mythology."""
        query = "Explain black holes and is there any comparison in mythology?"
        domains = self.orchestrator.classify_intent(query)
        self.assertIn("SPACE", domains)
        self.assertIn("MYTHOLOGY", domains)

        routed = self.orchestrator.route_query(query)
        self.assertTrue(routed["handled"])
        self.assertTrue(routed["multi_specialist"])
        self.assertIn("Astrophysics", routed["response"])
        self.assertIn("Mythological", routed["response"])

    # ── 6. Smart Context & Short-Hint Resolution ──────────────────────────────

    def test_09_smart_context_and_short_hints(self):
        """Verifies short hint expansion across multi-turn conversational sequences."""
        resolver = ContextResolver()

        # Step 1: User asks for laptops
        resolver.record_turn("user", "Find the best laptops for programming")
        resolver.update_browser_state(query="best laptops for programming")

        # Step 2: User provides short price hint
        hint_price = resolver.resolve("Under 70k")
        self.assertTrue(hint_price.is_short_hint)
        self.assertIn("70k", hint_price.resolved_query)
        self.assertEqual(hint_price.action_type, "SEARCH")

        # Step 3: User asks to compare the first two
        hint_compare = resolver.resolve("Compare the first two")
        self.assertTrue(hint_compare.is_short_hint)
        self.assertEqual(hint_compare.action_type, "BROWSER_COMPARE")

        # Step 4: User asks for mythological parallel follow-up
        resolver.record_turn("user", "Explain black holes")
        hint_myth = resolver.resolve("Iska mythology mein koi comparison hai?")
        self.assertTrue(hint_myth.is_short_hint)
        self.assertIn("black holes", hint_myth.resolved_query.lower())
        self.assertEqual(hint_myth.action_type, "SPECIALIST")

    # ── 7. Emotional Intelligence & Adaptive Personality ──────────────────────

    def test_10_emotional_intelligence_adaptive_profiles(self):
        """Verifies tone modulation under frustration vs curiosity."""
        frustrated_profile = self.emotional_engine.analyze_utterance("Why is it asking again? Just send it!")
        self.assertEqual(frustrated_profile.detected_state, EmotionalState.FRUSTRATED)
        self.assertEqual(frustrated_profile.brevity_level, "CONCISE")

        curious_profile = self.emotional_engine.analyze_utterance("Why does quantum entanglement happen across spacetime?")
        self.assertEqual(curious_profile.detected_state, EmotionalState.CURIOUS)
        self.assertEqual(curious_profile.brevity_level, "EXPANSIVE")

    # ── 8. Knowledge Acquisition & Action Integration ─────────────────────────

    def test_11_knowledge_acquisition_indexing(self):
        """Verifies autonomous 8-stage research indexing with source provenance."""
        entry = self.knowledge_engine.research_and_index(
            topic="Quantum Error Correction Topology",
            sources=["Surface Code Architecture (Google Quantum AI, 2023)"],
            summary="Surface code lattice using physical qubits with fault-tolerant stabilizer measurements."
        )
        self.assertTrue(entry.verified)
        self.assertIn("KNOW_", entry.entry_id)

        queried = self.knowledge_engine.query_index("Quantum")
        self.assertGreaterEqual(len(queried), 1)

    def test_12_specialist_action_integration(self):
        """Verifies specialist_intelligence action parameters and thread-safe execution."""
        self.assertEqual(TOOL["name"], "specialist_intelligence")

        # Test telemetry action
        res_voice = specialist_intelligence({"action": "barge_in_status"})
        self.assertIn("latency", res_voice.lower())

        # Test specialist query action
        res_space = specialist_intelligence({"action": "query", "query": "Explain event horizon in black holes"})
        self.assertIn("Event Horizon", res_space)


if __name__ == "__main__":
    unittest.main()
