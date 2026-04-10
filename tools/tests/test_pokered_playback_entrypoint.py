from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


def make_fake_tool(directory: Path, name: str, version: str) -> Path:
    path = directory / name
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "case \"$1\" in\n"
        "  --version|-V|-version)\n"
        f"    echo \"{version}\"\n"
        "    ;;\n"
        "  *)\n"
        f"    echo \"{version}\"\n"
        "    ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class PokeredPlaybackEntrypointTest(unittest.TestCase):
    def test_runner_dry_run_uses_native_runner_and_ffmpeg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bindir = Path(tmpdir)
            env = os.environ.copy()
            env.update(
                {
                    "ICEBOY_UV_BIN": str(make_fake_tool(bindir, "uv", "uv 0.0-test")),
                    "ICEBOY_SWIM_BIN": str(make_fake_tool(bindir, "swim", "swim v0.17.0-test")),
                    "ICEBOY_VERILATOR_BIN": str(make_fake_tool(bindir, "verilator", "Verilator 5.046")),
                    "ICEBOY_FFMPEG_BIN": str(make_fake_tool(bindir, "ffmpeg", "ffmpeg version test")),
                }
            )
            completed = subprocess.run(
                [str(TOOLS / "run_pokered_playback_verilator.sh"), "--dry-run", "--skip-build"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("tools/verilator/pokered_playback_main.cpp", completed.stdout)
            self.assertIn("tools/export_pokered_restore.py", completed.stdout)
            self.assertIn("tools/export_pokered_walk_script.py", completed.stdout)
            self.assertIn("tools/pokered_frame_artifacts.py", completed.stdout)
            self.assertIn("../gbxcule/Bulbasaur.state", completed.stdout)
            self.assertIn("../gbxcule/red.gb", completed.stdout)
            self.assertIn("tools/pokered_walk_script.yaml", completed.stdout)
            self.assertIn("ffmpeg", completed.stdout)
            self.assertIn("--target-frames=600", completed.stdout)


if __name__ == "__main__":
    unittest.main()
