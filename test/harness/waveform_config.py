from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
DEFAULT_ARTIFACT_ROOT = ROOT / "bench" / "artifacts" / "waves"
DEFAULT_HARNESS_ROOT = ROOT / "build" / "harness"
DEFAULT_SIGNAL_GROUPS = ("cpu_overview", "bus_activity", "interrupt_flow", "timer_detail", "power_signals")


@dataclass(frozen=True)
class WaveformCaptureConfig:
    enabled: bool
    capture_on_failure: bool
    signal_groups: tuple[str, ...]
    artifact_root: Path


@dataclass(frozen=True)
class ExportedWaveforms:
    test_name: str
    artifact_dir: Path
    fst_path: Path | None
    vcd_path: Path | None
    metadata_path: Path


def _env_flag(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def config_from_env(env: Mapping[str, str] | None = None, *, artifact_root: str | Path | None = None) -> WaveformCaptureConfig:
    source = dict(os.environ if env is None else env)
    groups_text = source.get("ICEBOY_WAVE_GROUPS", ",".join(DEFAULT_SIGNAL_GROUPS))
    groups = tuple(item.strip() for item in groups_text.split(",") if item.strip())
    return WaveformCaptureConfig(
        enabled=_env_flag(source.get("ICEBOY_WAVES"), default=False),
        capture_on_failure=_env_flag(source.get("ICEBOY_WAVES_ON_FAILURE"), default=True),
        signal_groups=groups or DEFAULT_SIGNAL_GROUPS,
        artifact_root=Path(artifact_root) if artifact_root is not None else DEFAULT_ARTIFACT_ROOT,
    )


def locate_waveforms(
    test_name: str,
    *,
    harness_root: str | Path = DEFAULT_HARNESS_ROOT,
) -> dict[str, Path]:
    root = Path(harness_root)
    case_dirs = sorted(root.glob(f"{test_name}_*"), key=lambda path: path.stat().st_mtime if path.exists() else 0)
    if not case_dirs:
        return {}
    case_dir = case_dirs[-1]
    found: dict[str, Path] = {}
    fst = sorted(case_dir.glob("*.fst"))
    if fst:
        found["fst"] = fst[-1]
    dump_vcd = case_dir / "dump.vcd"
    if dump_vcd.is_file():
        found["vcd"] = dump_vcd
    else:
        vcd = sorted(case_dir.glob("*.vcd"))
        if vcd:
            found["vcd"] = vcd[-1]
    return found


def export_waveforms(
    test_name: str,
    *,
    failed: bool = False,
    config: WaveformCaptureConfig | None = None,
    harness_root: str | Path = DEFAULT_HARNESS_ROOT,
) -> ExportedWaveforms | None:
    resolved = config or config_from_env()
    if not resolved.enabled and not (failed and resolved.capture_on_failure):
        return None

    sources = locate_waveforms(test_name, harness_root=harness_root)
    if not sources:
        return None

    artifact_dir = resolved.artifact_root / test_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    copied: dict[str, Path] = {}
    for kind, source in sources.items():
        destination = artifact_dir / source.name
        shutil.copy2(source, destination)
        copied[kind] = destination

    metadata_path = artifact_dir / "waveform_manifest.json"
    metadata_path.write_text(
        json.dumps(
            {
                "test_name": test_name,
                "failed": failed,
                "signal_groups": list(resolved.signal_groups),
                "sources": {kind: str(path) for kind, path in copied.items()},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return ExportedWaveforms(
        test_name=test_name,
        artifact_dir=artifact_dir,
        fst_path=copied.get("fst"),
        vcd_path=copied.get("vcd"),
        metadata_path=metadata_path,
    )


def write_divergence_window_metadata(
    test_name: str,
    mismatch_commit_index: int,
    *,
    before: int = 50,
    after: int = 10,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    waveform_path: str | Path | None = None,
) -> Path:
    destination = Path(artifact_root)
    destination.mkdir(parents=True, exist_ok=True)
    window_path = destination / f"{test_name}_divergence_window.json"
    payload = {
        "test_name": test_name,
        "mismatch_commit_index": mismatch_commit_index,
        "window_before_commits": before,
        "window_after_commits": after,
        "window_start_commit": max(0, mismatch_commit_index - before),
        "window_end_commit": mismatch_commit_index + after,
        "waveform_path": str(waveform_path) if waveform_path is not None else None,
    }
    window_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return window_path
