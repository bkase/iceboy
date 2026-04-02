from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from test.harness.logging_std import (
    FailureArtifacts,
    TestLogger,
    add_logging_args,
    logger_from_args,
)


SWIM = Path.home() / ".cargo" / "bin" / "swim"
FST2VCD = ROOT / "build" / "oss-cad-suite" / "bin" / "fst2vcd"
TEST_FILTER = "spade_cocotb_integration"
VERILOG_PATH = ROOT / "build" / "spade.sv"
HARNESS_BUILD_DIR = ROOT / "build" / "harness"
SWIM_INDEX_LOCK = ROOT / "build" / "spade" / ".git" / "index.lock"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class StepResult:
    name: str
    duration_s: float
    exit_code: int
    output: str


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"[{utc_timestamp()}] {message}")


def combined_output(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def patch_cocotb_config_wrapper() -> None:
    bindir = ROOT / "build" / "oss-cad-suite" / "bin"
    config = bindir / "cocotb-config"
    config_py = bindir / "cocotb-config.py"
    if not config.exists():
        return

    config_py.write_text(
        "import re\n"
        "import sys\n"
        "from cocotb.config import main\n\n"
        "if __name__ == \"__main__\":\n"
        "    sys.argv[0] = re.sub(r\"(-script\\.pyw|\\.exe)?$\", \"\", sys.argv[0])\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    config.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "bindir=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "repo_root=\"$(cd \"$bindir/../..\" && pwd)\"\n"
        "case \"$PWD\" in\n"
        "  \"$repo_root\"/build/*) ln -sfn \"$bindir/../lib\" \"$PWD/lib\" ;;\n"
        "esac\n"
        "exec \"$bindir/tabbypy3\" \"$bindir/cocotb-config.py\" \"$@\"\n",
        encoding="utf-8",
    )
    config.chmod(0o755)
    config_py.chmod(0o755)


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"
    return env


def summarize_tree(path: Path) -> str:
    if not path.exists():
        return f"{path}: missing"
    if path.is_file():
        return f"{path}: file size={path.stat().st_size}"
    entries = sorted(child.name for child in path.iterdir())
    return f"{path}: {entries}"


def report_intermediate_state(logger: TestLogger) -> None:
    logger.context("verilog", summarize_tree(VERILOG_PATH))
    logger.context("harness", summarize_tree(HARNESS_BUILD_DIR))
    logger.context("fst2vcd", summarize_tree(FST2VCD))


def run_step(logger: TestLogger, name: str, command: list[str]) -> StepResult:
    logger.step(f"{utc_timestamp()} {name}: running {' '.join(command)}")
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=command_env(),
        capture_output=True,
        text=True,
    )
    duration_s = time.monotonic() - started
    output = combined_output(completed)
    logger.check(f"{name} exit code", expected=0, actual=completed.returncode)
    if output:
        print(output)
    if completed.returncode != 0:
        logger.fail_case(
            f"{name} failed",
            duration_s=duration_s,
            contexts={"command": " ".join(command), "stderr_or_stdout": output},
            artifacts=FailureArtifacts(divergent_field=name),
        )
        report_intermediate_state(logger)
        raise RuntimeError(
            f"{name} failed with exit code {completed.returncode}: {' '.join(command)}"
        )
    return StepResult(name=name, duration_s=duration_s, exit_code=completed.returncode, output=output)


def clear_old_artifacts() -> None:
    for path in HARNESS_BUILD_DIR.glob("test_spade_cocotb_integration_*"):
        shutil.rmtree(path)


def clear_stale_swim_lock() -> None:
    SWIM_INDEX_LOCK.unlink(missing_ok=True)


def locate_fst_waveform(*, started_at: float) -> Path:
    candidates = sorted(HARNESS_BUILD_DIR.glob("test_spade_cocotb_integration_*/*.fst"))
    if not candidates:
        raise FileNotFoundError("No FST waveform found for spade_cocotb_integration")
    waveform = candidates[-1]
    if waveform.stat().st_size == 0:
        raise AssertionError(f"FST waveform is empty: {waveform}")
    if waveform.stat().st_mtime < started_at:
        raise AssertionError(f"FST waveform was not refreshed by this run: {waveform}")
    return waveform


def locate_dump_vcd(*, fst_waveform: Path) -> Path:
    waveform = fst_waveform.with_name("dump.vcd")
    if not waveform.is_file():
        raise FileNotFoundError(f"No translated VCD found at {waveform}")
    if waveform.stat().st_size == 0:
        raise AssertionError(f"Translated VCD is empty: {waveform}")
    return waveform


def extract_case_count(output: str) -> str:
    clean = strip_ansi(output)
    summary_match = re.search(r"0/(\d+)\s+failed", clean)
    if summary_match:
        return f"{summary_match.group(1)}/{summary_match.group(1)}"
    passed_count = clean.count("PASSED")
    if passed_count:
        return f"{passed_count}/{passed_count}"
    return "unknown"


def run_smoke(*, logger: TestLogger | None = None) -> Path:
    if not SWIM.is_file():
        raise FileNotFoundError(f"Missing swim binary at {SWIM}")
    if not FST2VCD.is_file():
        raise FileNotFoundError(f"Missing fst2vcd binary at {FST2VCD}")

    clear_stale_swim_lock()
    suite_logger = logger or TestLogger(
        suite_name="test_spade_cocotb_integration.py",
        stream=sys.stdout,
    )
    suite_logger.suite()
    logger = suite_logger.bind_case("test_spade_cocotb_smoke_pipeline")
    clear_old_artifacts()
    started_at = time.time()
    build = run_step(logger, "spade_compile", [str(SWIM), "build"])

    if not VERILOG_PATH.is_file():
        raise FileNotFoundError(f"Expected generated Verilog at {VERILOG_PATH}")
    verilog_lines = len(VERILOG_PATH.read_text(encoding="utf-8").splitlines())
    logger.check("Generated Verilog", expected=True, actual=VERILOG_PATH.is_file())
    logger.context("verilog_lines", verilog_lines)

    patch_cocotb_config_wrapper()
    test = run_step(logger, "simulator_cocotb", [str(SWIM), "test", TEST_FILTER])

    fst_waveform = locate_fst_waveform(started_at=started_at)
    run_step(
        logger,
        "waveform_translate",
        [str(FST2VCD), "-f", str(fst_waveform), "-o", str(fst_waveform.with_name("dump.vcd"))],
    )
    waveform = locate_dump_vcd(fst_waveform=fst_waveform)
    cases = extract_case_count(test.output)
    logger.context("case_count", cases)
    logger.context("waveform_vcd", waveform)
    logger.context("waveform_fst", fst_waveform)
    logger.pass_case(build.duration_s + test.duration_s)
    suite_logger.summary(
        passed=1,
        failed=0,
        duration_s=build.duration_s + test.duration_s,
    )
    return waveform


def main() -> int:
    parser = add_logging_args(
        argparse.ArgumentParser(description="Run the Spade-to-Cocotb toolchain smoke test.")
    )
    args = parser.parse_args()
    run_smoke(
        logger=logger_from_args(
            args,
            suite_name="test_spade_cocotb_integration.py",
            stream=sys.stdout,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
