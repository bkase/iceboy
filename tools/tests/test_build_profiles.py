from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROFILE_ROOT = ROOT / "build" / "profiles"


def _load_profile(name: str) -> dict[str, object]:
    return yaml.safe_load((PROFILE_ROOT / f"{name}.yaml").read_text(encoding="utf-8"))


class BuildProfilesTest(unittest.TestCase):
    def test_expected_build_profiles_exist(self) -> None:
        self.assertEqual(
            sorted(path.name for path in PROFILE_ROOT.glob("*.yaml")),
            ["sim_power.yaml", "sim_semantic.yaml", "sim_trace.yaml", "synth.yaml"],
        )

    def test_profile_contracts_match_ppu_build_flavor_plan(self) -> None:
        synth = _load_profile("synth")
        semantic = _load_profile("sim_semantic")
        trace = _load_profile("sim_trace")
        power = _load_profile("sim_power")

        self.assertEqual(synth["profile"], "synth")
        self.assertEqual(synth["simulation_tops"], ["board::icebreaker_top::icebreaker_top"])
        self.assertEqual(synth["output_ports"], [])
        self.assertEqual(
            synth["instrumentation"],
            {"semantic_commit": False, "debug_trace": False, "activity_counters": False},
        )
        self.assertEqual(synth["verification"]["script"], "tools/verify_hw_build.sh")
        self.assertEqual(
            synth["verification"]["forbids_debug_symbols"],
            ["CommitTrace", "DebugTrace", "PpuDebugTrace", "SimStimulus", "BusObs", "SocLockstepTopOut"],
        )

        self.assertIn("sim::semantic_observe_top::semantic_observe_top", semantic["simulation_tops"])
        self.assertIn("PpuSemanticCommit", semantic["output_ports"])
        self.assertEqual(semantic["instrumentation"]["semantic_commit"], True)
        self.assertEqual(semantic["instrumentation"]["debug_trace"], False)

        self.assertIn("sim::trace_observe_top::trace_observe_top", trace["simulation_tops"])
        self.assertIn("PpuDebugTrace", trace["output_ports"])
        self.assertEqual(trace["instrumentation"]["debug_trace"], True)

        self.assertIn("sim::soc_lockstep_top::soc_lockstep_top", power["simulation_tops"])
        self.assertIn("metric_total_cycles", power["output_ports"])
        self.assertEqual(power["instrumentation"]["activity_counters"], True)

    def test_profiles_have_resource_budget_notes(self) -> None:
        for name in ["synth", "sim_semantic", "sim_trace", "sim_power"]:
            profile = _load_profile(name)
            budget = profile["resource_budget"]
            self.assertIn(budget["expected_overhead"], {"none", "moderate", "high"})
            self.assertGreaterEqual(len(budget["notes"]), 2)


if __name__ == "__main__":
    unittest.main()
