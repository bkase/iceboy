from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spec.compare_scopes import OracleMode
from spec.profiles import MemoryBehaviorProfile, ModelProfile, ResetProfile

SCHEMA_PATH = ROOT / "bench" / "manifests" / "rom_schema.yaml"
INVENTORY_PATH = ROOT / "bench" / "manifests" / "rom_inventory.yaml"
EXPECTED_ROM_IDS = [
    "LOADS_BASIC",
    "ALU_FLAGS",
    "ALU16_SP",
    "FLOW_STACK",
    "CB_BITOPS",
    "MEM_RWB",
    "ALU_LOOP",
    "TIMER_DIV_BASIC",
    "EI_DELAY",
    "TIMER_IRQ_HALT",
    "JOY_DIVERGE_PERSIST",
    "DMA_OAM_COPY",
    "MBC1_SWITCH",
    "MBC1_RAM",
    "MBC3_SWITCH",
    "MBC3_RAM",
    "PPU_STAT_IRQ",
    "BG_STATIC",
    "BG_SCROLL_SIGNED",
    "PPU_WINDOW",
    "PPU_SPRITES",
]


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ROM manifest validation failed: {message}")


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        fail(f"{path.relative_to(ROOT)} must contain a YAML mapping at the top level")
    return data


def require_keys(mapping: dict, required: list[str], context: str) -> None:
    missing = [key for key in required if key not in mapping]
    if missing:
        fail(f"{context} is missing required keys: {', '.join(missing)}")


def expect_type(value, expected_type, context: str) -> None:
    if not isinstance(value, expected_type):
        fail(f"{context} must be a {expected_type.__name__}")


def main() -> int:
    schema = load_yaml(SCHEMA_PATH)
    inventory = load_yaml(INVENTORY_PATH)

    if schema.get("schema_version") != 1:
        fail("schema_version in rom_schema.yaml must be 1")
    if inventory.get("schema_version") != schema["schema_version"]:
        fail("rom_inventory.yaml schema_version must match rom_schema.yaml")

    require_keys(inventory, schema["inventory_contract"]["top_level_required"], "rom_inventory.yaml")

    allowed_requires = set(schema["allowed_values"]["requires"])
    allowed_model_profiles = {profile.value for profile in ModelProfile}
    allowed_reset_profiles = {profile.value for profile in ResetProfile}
    allowed_oracle_modes = {mode.value for mode in OracleMode}
    allowed_memory_profiles = {profile.value for profile in MemoryBehaviorProfile}
    allowed_compare_domains = set(schema["allowed_values"]["compare_domains"])
    allowed_pass_kinds = set(schema["allowed_values"]["pass_condition_kinds"])
    allowed_action_generators = set(schema["allowed_values"]["action_generators"])

    schema_abi = schema["abi_contract"]
    inventory_abi = inventory["abi_contract"]

    if inventory_abi.get("sym_file_required") is not True:
        fail("abi_contract.sym_file_required must be true")
    if inventory_abi.get("executable_labels") != schema_abi["executable_labels"]:
        fail("abi_contract.executable_labels must match rom_schema.yaml")
    if inventory_abi.get("wram_signature_block", {}).get("id") != schema_abi["wram_signature_block"]["id"]:
        fail("abi_contract.wram_signature_block.id must match rom_schema.yaml")
    if inventory_abi.get("wram_signature_block", {}).get("versioned") is not True:
        fail("abi_contract.wram_signature_block.versioned must be true")

    roms = inventory["roms"]
    expect_type(roms, list, "rom_inventory.yaml roms")

    ids = []
    seen_paths = set()
    required_rom_fields = schema["inventory_contract"]["rom_entry_required"]

    for rom in roms:
        expect_type(rom, dict, "each rom entry")
        require_keys(rom, required_rom_fields, f"ROM entry {rom.get('id', '<unknown>')}")

        rom_id = rom["id"]
        path = rom["path"]
        ids.append(rom_id)

        expect_type(rom_id, str, "rom id")
        expect_type(path, str, f"{rom_id}.path")
        if not path.startswith("bench/roms/out/") or not path.endswith(".gb"):
            fail(f"{rom_id}.path must point at bench/roms/out/*.gb")
        if path in seen_paths:
            fail(f"duplicate ROM path detected: {path}")
        seen_paths.add(path)

        model_profile = rom["model_profile"]
        if model_profile not in allowed_model_profiles:
            fail(f"{rom_id}.model_profile is not allowed")

        reset_profile = rom["reset_profile"]
        if reset_profile not in allowed_reset_profiles:
            fail(f"{rom_id}.reset_profile is not allowed")

        requires = rom["requires"]
        expect_type(requires, list, f"{rom_id}.requires")
        if not requires:
            fail(f"{rom_id}.requires must not be empty")
        if any(capability not in allowed_requires for capability in requires):
            fail(f"{rom_id}.requires contains an unknown capability")

        oracle_mode = rom["oracle_mode"]
        if oracle_mode not in allowed_oracle_modes:
            fail(f"{rom_id}.oracle_mode is not allowed")

        memory_profile = rom["memory_behavior_profile"]
        if memory_profile not in allowed_memory_profiles:
            fail(f"{rom_id}.memory_behavior_profile is not allowed")

        timeout_commits = rom["timeout_commits"]
        expect_type(timeout_commits, int, f"{rom_id}.timeout_commits")
        if timeout_commits <= 0:
            fail(f"{rom_id}.timeout_commits must be positive")

        checkpoint_symbols = rom["checkpoint_symbols"]
        expect_type(checkpoint_symbols, list, f"{rom_id}.checkpoint_symbols")
        if any(not isinstance(symbol, str) or not symbol.startswith("__checkpoint_") for symbol in checkpoint_symbols):
            fail(f"{rom_id}.checkpoint_symbols must only contain __checkpoint_* labels")

        pass_condition = rom["pass_condition"]
        expect_type(pass_condition, dict, f"{rom_id}.pass_condition")
        if pass_condition.get("kind") not in allowed_pass_kinds:
            fail(f"{rom_id}.pass_condition.kind is not allowed")
        if pass_condition.get("pass_label") != "__pass":
            fail(f"{rom_id}.pass_condition.pass_label must be __pass")
        if pass_condition.get("fail_label") != "__fail":
            fail(f"{rom_id}.pass_condition.fail_label must be __fail")
        if pass_condition.get("signature_block") != inventory_abi["wram_signature_block"]["id"]:
            fail(f"{rom_id}.pass_condition.signature_block must reference the shared WRAM signature block")

        compare_scope = rom["compare_scope"]
        expect_type(compare_scope, dict, f"{rom_id}.compare_scope")
        domains = compare_scope.get("domains")
        expect_type(domains, list, f"{rom_id}.compare_scope.domains")
        if not domains:
            fail(f"{rom_id}.compare_scope.domains must not be empty")
        if any(domain not in allowed_compare_domains for domain in domains):
            fail(f"{rom_id}.compare_scope.domains contains an unknown domain")
        if oracle_mode == "frame_hash" and domains != ["frame_hash"]:
            fail(f"{rom_id} must use compare_scope.domains [frame_hash] with oracle_mode frame_hash")
        if "frame_hash" in domains and oracle_mode != "frame_hash":
            fail(f"{rom_id} uses frame_hash compare scope without oracle_mode frame_hash")

        action_script = rom["action_script"]
        if action_script is not None and not isinstance(action_script, str):
            fail(f"{rom_id}.action_script must be null or a relative path string")

        action_gen = rom["action_gen"]
        if action_gen is not None:
            expect_type(action_gen, dict, f"{rom_id}.action_gen")
            if action_gen.get("name") not in allowed_action_generators:
                fail(f"{rom_id}.action_gen.name is not allowed")
            seed = action_gen.get("seed")
            expect_type(seed, int, f"{rom_id}.action_gen.seed")
            if seed < 0:
                fail(f"{rom_id}.action_gen.seed must be non-negative")

        if model_profile != "DMG":
            fail(f"{rom_id} must pin model_profile to DMG for CPU bring-up")
        if reset_profile != "SkipBoot":
            fail(f"{rom_id} must pin reset_profile to SkipBoot for CPU bring-up")

    if ids != EXPECTED_ROM_IDS:
        fail("rom_inventory.yaml must contain the exact Wave A-D ROM inventory in plan order")
    if len(set(ids)) != len(ids):
        fail("rom_inventory.yaml contains duplicate ROM ids")

    print(f"Validated ROM manifest schema and inventory for {len(ids)} ROM stubs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
