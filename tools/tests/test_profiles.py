from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from spec.profiles import (
    CPU_BRING_UP_PROFILES,
    MemoryBehaviorProfile,
    ModelProfile,
    ResetProfile,
    SimulationProfiles,
)


ROOT = Path(__file__).resolve().parents[2]
ROM_INVENTORY_PATH = ROOT / "bench" / "manifests" / "rom_inventory.yaml"
SPADE_TYPES_PATH = ROOT / "src" / "cpu" / "types.spade"


class SimulationProfilesTest(unittest.TestCase):
    def test_cpu_bring_up_profiles_are_pinned(self) -> None:
        self.assertEqual(CPU_BRING_UP_PROFILES.model, ModelProfile.DMG)
        self.assertEqual(CPU_BRING_UP_PROFILES.reset, ResetProfile.SkipBoot)
        self.assertEqual(
            CPU_BRING_UP_PROFILES.memory_behavior,
            MemoryBehaviorProfile.DmgConservative,
        )

    def test_manifest_round_trip_mapping(self) -> None:
        round_trip = SimulationProfiles.from_mapping(CPU_BRING_UP_PROFILES.as_manifest_fields())
        self.assertEqual(round_trip, CPU_BRING_UP_PROFILES)

    def test_rom_inventory_records_bring_up_profiles(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        roms = inventory["roms"]
        self.assertGreater(len(roms), 0)

        for rom in roms:
            self.assertEqual(rom["model_profile"], CPU_BRING_UP_PROFILES.model.value)
            self.assertEqual(rom["reset_profile"], CPU_BRING_UP_PROFILES.reset.value)

    def test_wave_b_manifest_entries_use_instr_commit_with_checkpoints(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        roms = {rom["id"]: rom for rom in inventory["roms"]}

        self.assertEqual(
            roms["TIMER_DIV_BASIC"]["checkpoint_symbols"],
            [
                "__checkpoint_div_count",
                "__checkpoint_div_reset",
                "__checkpoint_tac_prescaler",
                "__checkpoint_tma_reload",
            ],
        )
        self.assertEqual(roms["TIMER_DIV_BASIC"]["oracle_mode"], "instr_commit")

        self.assertEqual(
            roms["EI_DELAY"]["checkpoint_symbols"],
            [
                "__checkpoint_ei_nop",
                "__checkpoint_ei_di",
                "__checkpoint_reti",
            ],
        )
        self.assertEqual(roms["EI_DELAY"]["oracle_mode"], "mcycle_commit")

        self.assertEqual(
            roms["TIMER_IRQ_HALT"]["checkpoint_symbols"],
            [
                "__checkpoint_halt_enter",
                "__checkpoint_irq_fire",
                "__checkpoint_isr_execute",
                "__checkpoint_halt_wake",
            ],
        )
        self.assertEqual(roms["TIMER_IRQ_HALT"]["oracle_mode"], "mcycle_commit")

    def test_joy_manifest_entry_uses_deterministic_action_script(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        roms = {rom["id"]: rom for rom in inventory["roms"]}

        self.assertEqual(roms["JOY_DIVERGE_PERSIST"]["path"], "bench/roms/out/joy_diverge_persist.gb")
        self.assertEqual(roms["JOY_DIVERGE_PERSIST"]["timeout_commits"], 4)
        self.assertEqual(roms["JOY_DIVERGE_PERSIST"]["checkpoint_symbols"], ["__checkpoint_poll"])
        self.assertEqual(roms["JOY_DIVERGE_PERSIST"]["action_script"], "bench/actions/joy_diverge_persist.yaml")
        self.assertIsNone(roms["JOY_DIVERGE_PERSIST"]["action_gen"])

    def test_spade_types_define_same_profile_names(self) -> None:
        spade_types = SPADE_TYPES_PATH.read_text(encoding="utf-8")

        for symbol in [
            "enum ModelProfile",
            "DMG",
            "CGB",
            "enum ResetProfile",
            "SkipBoot",
            "RawPowerOn",
            "enum MemoryBehaviorProfile",
            "DmgConservative",
            "DmgRevisionSpecific",
        ]:
            self.assertIn(symbol, spade_types)


if __name__ == "__main__":
    unittest.main()
