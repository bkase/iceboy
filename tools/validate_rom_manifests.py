from __future__ import annotations

import json
import sys
from hashlib import sha256
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
    "OAM_DMA_ISOLATION",
    "MBC1_SWITCH",
    "MBC1_RAM",
    "MBC3_SWITCH",
    "MBC3_RAM",
    "CPU_INSTRS_BLARGG",
    "PPU_OFF_ON_BASIC",
    "LY_LYC_BASIC",
    "STAT_MODE_SEQ",
    "VBLANK_IRQ_BASIC",
    "VRAM_OAM_GATING",
    "PPU_STAT_IRQ",
    "BG_STATIC",
    "JOYPAD_BG_SMOKE",
    "BG_SCROLL_WRAP",
    "BG_SIGNED_ADDR",
    "WINDOW_BASIC",
    "WINDOW_LINE_COUNTER",
    "WINDOW_WX_WY_EDGE",
    "WINDOW_WX0_STUTTER",
    "WINDOW_WX166_NEXTLINE",
    "WINDOW_WX_RETRIGGER_GLITCH",
    "WINDOW_WINEN_TOGGLE_REARM",
    "PPU_SPRITES",
]
EXPECTED_ARTIFACT_SCHEMAS = {
    "replay_capsule": "bench/schemas/replay_capsule.schema.json",
    "oracle_capture": "bench/schemas/oracle_capture.schema.json",
    "line_summary": "bench/schemas/line_summary.schema.json",
}


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


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        fail(f"{path.relative_to(ROOT)} must contain a JSON object at the top level")
    return data


def expect_string_list(values: object, context: str) -> list[str]:
    expect_type(values, list, context)
    if any(not isinstance(value, str) for value in values):
        fail(f"{context} must only contain strings")
    return list(values)


def main() -> int:
    schema = load_yaml(SCHEMA_PATH)
    inventory = load_yaml(INVENTORY_PATH)

    if schema.get("schema_version") != 2:
        fail("schema_version in rom_schema.yaml must be 2")
    if inventory.get("schema_version") != schema["schema_version"]:
        fail("rom_inventory.yaml schema_version must match rom_schema.yaml")

    require_keys(inventory, schema["inventory_contract"]["top_level_required"], "rom_inventory.yaml")

    allowed_requires = set(schema["allowed_values"]["requires"])
    allowed_model_profiles = {profile.value for profile in ModelProfile}
    allowed_reset_profiles = {profile.value for profile in ResetProfile}
    allowed_oracle_modes = {mode.value for mode in OracleMode}
    allowed_memory_profiles = {profile.value for profile in MemoryBehaviorProfile}
    allowed_build_flavors = set(schema["allowed_values"]["build_flavor"])
    allowed_memory_backends = set(schema["allowed_values"]["memory_backend"])
    allowed_compare_domains = set(schema["allowed_values"]["compare_domains"])
    allowed_pass_kinds = set(schema["allowed_values"]["pass_condition_kinds"])
    allowed_action_generators = set(schema["allowed_values"]["action_generators"])
    allowed_rule_confidence = set(schema["allowed_values"]["rule_confidence"])
    allowed_uncertainty = set(schema["allowed_values"]["allowed_uncertainty"])
    allowed_coord_spaces = set(schema["allowed_values"]["raster_event_coord_space"])
    allowed_soc_revisions = set(schema["allowed_values"]["soc_revision"])
    allowed_behavior_features = set(schema["allowed_values"]["behavior_feature"])

    schema_abi = schema["abi_contract"]
    inventory_abi = inventory["abi_contract"]
    artifact_schemas = inventory["artifact_schemas"]

    if inventory_abi.get("sym_file_required") is not True:
        fail("abi_contract.sym_file_required must be true")
    if inventory_abi.get("executable_labels") != schema_abi["executable_labels"]:
        fail("abi_contract.executable_labels must match rom_schema.yaml")
    if inventory_abi.get("wram_signature_block", {}).get("id") != schema_abi["wram_signature_block"]["id"]:
        fail("abi_contract.wram_signature_block.id must match rom_schema.yaml")
    if inventory_abi.get("wram_signature_block", {}).get("versioned") is not True:
        fail("abi_contract.wram_signature_block.versioned must be true")

    expect_type(artifact_schemas, dict, "rom_inventory.yaml artifact_schemas")
    if artifact_schemas != EXPECTED_ARTIFACT_SCHEMAS:
        fail("artifact_schemas must reference the shared bench/schemas JSON contracts")
    for artifact_id, artifact_path in artifact_schemas.items():
        path = ROOT / artifact_path
        if not path.exists():
            fail(f"artifact schema {artifact_id} is missing: {artifact_path}")
        payload = load_json(path)
        if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"{artifact_path} must declare the draft 2020-12 JSON Schema URI")
        if payload.get("type") != "object":
            fail(f"{artifact_path} must define an object-shaped schema")
        schema_version_prop = payload.get("properties", {}).get("schema_version", {})
        if schema_version_prop.get("const") != 1:
            fail(f"{artifact_path} must pin schema_version via properties.schema_version.const")

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
        if not path.endswith(".gb") or not (path.startswith("bench/roms/out/") or path.startswith("roms/")):
            fail(f"{rom_id}.path must point at bench/roms/out/*.gb or roms/*.gb")
        if path in seen_paths:
            fail(f"duplicate ROM path detected: {path}")
        seen_paths.add(path)
        rom_path = ROOT / path

        rom_sha256 = rom["rom_sha256"]
        if rom_path.exists():
            expect_type(rom_sha256, str, f"{rom_id}.rom_sha256")
            if len(rom_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in rom_sha256):
                fail(f"{rom_id}.rom_sha256 must be a lowercase 64-character hex digest")
            actual_sha256 = sha256(rom_path.read_bytes()).hexdigest()
            if rom_sha256 != actual_sha256:
                fail(f"{rom_id}.rom_sha256 does not match {path}")
        elif rom_sha256 is not None:
            fail(f"{rom_id}.rom_sha256 must be null until {path} exists")

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

        build_flavor = rom["build_flavor"]
        if build_flavor not in allowed_build_flavors:
            fail(f"{rom_id}.build_flavor is not allowed")

        memory_backend = rom["memory_backend"]
        if memory_backend not in allowed_memory_backends:
            fail(f"{rom_id}.memory_backend is not allowed")

        behavior_config = rom["behavior_config"]
        expect_type(behavior_config, dict, f"{rom_id}.behavior_config")
        if behavior_config.get("model") != model_profile:
            fail(f"{rom_id}.behavior_config.model must match model_profile")
        soc_revision = behavior_config.get("soc_revision")
        if soc_revision is not None and soc_revision not in allowed_soc_revisions:
            fail(f"{rom_id}.behavior_config.soc_revision is not allowed")
        behavior_features = expect_string_list(
            behavior_config.get("features", []),
            f"{rom_id}.behavior_config.features",
        )
        if any(feature not in allowed_behavior_features for feature in behavior_features):
            fail(f"{rom_id}.behavior_config.features contains an unknown feature")

        rule_confidence = rom["rule_confidence"]
        if rule_confidence not in allowed_rule_confidence:
            fail(f"{rom_id}.rule_confidence is not allowed")

        allowed_uncertainty_values = expect_string_list(rom["allowed_uncertainty"], f"{rom_id}.allowed_uncertainty")
        if any(value not in allowed_uncertainty for value in allowed_uncertainty_values):
            fail(f"{rom_id}.allowed_uncertainty contains an unknown compare surface")

        coord_space = rom["raster_event_coord_space"]
        if coord_space not in allowed_coord_spaces:
            fail(f"{rom_id}.raster_event_coord_space is not allowed")

        expected_soc_revisions = expect_string_list(rom["expected_soc_revisions"], f"{rom_id}.expected_soc_revisions")
        if any(revision not in allowed_soc_revisions for revision in expected_soc_revisions):
            fail(f"{rom_id}.expected_soc_revisions contains an unknown SoC revision")
        if soc_revision is not None and expected_soc_revisions and soc_revision not in expected_soc_revisions:
            fail(f"{rom_id}.behavior_config.soc_revision must be included in expected_soc_revisions when pinned")

        required_behavior_features = expect_string_list(
            rom["required_behavior_features"],
            f"{rom_id}.required_behavior_features",
        )
        forbidden_behavior_features = expect_string_list(
            rom["forbidden_behavior_features"],
            f"{rom_id}.forbidden_behavior_features",
        )
        if any(feature not in allowed_behavior_features for feature in required_behavior_features):
            fail(f"{rom_id}.required_behavior_features contains an unknown feature")
        if any(feature not in allowed_behavior_features for feature in forbidden_behavior_features):
            fail(f"{rom_id}.forbidden_behavior_features contains an unknown feature")
        if set(required_behavior_features) & set(forbidden_behavior_features):
            fail(f"{rom_id} cannot require and forbid the same behavior feature")

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
        pass_kind = pass_condition.get("kind")
        if pass_kind not in allowed_pass_kinds:
            fail(f"{rom_id}.pass_condition.kind is not allowed")
        if pass_kind == "serial_substring":
            expected_substring = pass_condition.get("expected_substring")
            expect_type(expected_substring, str, f"{rom_id}.pass_condition.expected_substring")
            if not expected_substring:
                fail(f"{rom_id}.pass_condition.expected_substring must not be empty")
            fail_substrings = expect_string_list(
                pass_condition.get("fail_substrings", []),
                f"{rom_id}.pass_condition.fail_substrings",
            )
            if not fail_substrings:
                fail(f"{rom_id}.pass_condition.fail_substrings must not be empty")
            if pass_condition.get("pass_label") is not None:
                fail(f"{rom_id}.pass_condition.pass_label must be null for serial_substring")
            if pass_condition.get("fail_label") is not None:
                fail(f"{rom_id}.pass_condition.fail_label must be null for serial_substring")
            if pass_condition.get("signature_block") is not None:
                fail(f"{rom_id}.pass_condition.signature_block must be null for serial_substring")
        else:
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
        if oracle_mode == "frame_semantic" and domains != ["frame_semantic"]:
            fail(f"{rom_id} must use compare_scope.domains [frame_semantic] with oracle_mode frame_semantic")
        if "frame_semantic" in domains and oracle_mode != "frame_semantic":
            fail(f"{rom_id} uses frame_semantic compare scope without oracle_mode frame_semantic")
        if oracle_mode == "serial_terminal" and domains != ["serial_output"]:
            fail(f"{rom_id} must use compare_scope.domains [serial_output] with oracle_mode serial_terminal")
        if "serial_output" in domains and oracle_mode != "serial_terminal":
            fail(f"{rom_id} uses serial_output compare scope without oracle_mode serial_terminal")
        if oracle_mode == "serial_terminal" and pass_kind != "serial_substring":
            fail(f"{rom_id} must use pass_condition.kind serial_substring with oracle_mode serial_terminal")
        if pass_kind == "serial_substring" and oracle_mode != "serial_terminal":
            fail(f"{rom_id} uses serial_substring pass condition without oracle_mode serial_terminal")

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
