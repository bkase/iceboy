from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cocotb.triggers import ReadOnly, Timer


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "bench" / "artifacts" / "power_metrics"


@dataclass(frozen=True)
class PowerMetrics:
    total_cycles: int
    bus_active_cycles: int
    alu_active_cycles: int
    halted_cycles: int
    halt_quiescent_cycles: int
    reg_a_we_cycles: int
    reg_f_we_cycles: int
    reg_b_we_cycles: int
    reg_c_we_cycles: int
    reg_d_we_cycles: int
    reg_e_we_cycles: int
    reg_h_we_cycles: int
    reg_l_we_cycles: int
    reg_sp_we_cycles: int
    reg_pc_we_cycles: int

    def subtract(self, earlier: "PowerMetrics") -> "PowerMetrics":
        return PowerMetrics(**{field: getattr(self, field) - getattr(earlier, field) for field in self.__dataclass_fields__})

    def ratio(self, numerator: int, denominator: int | None = None) -> float:
        base = self.total_cycles if denominator is None else denominator
        return 0.0 if base == 0 else numerator / base

    def summary_lines(self) -> list[str]:
        lines = [
            f"total_cycles={self.total_cycles}",
            f"bus_active={self.bus_active_cycles}/{self.total_cycles} ({self.ratio(self.bus_active_cycles):.3f})",
            f"alu_active={self.alu_active_cycles}/{self.total_cycles} ({self.ratio(self.alu_active_cycles):.3f})",
        ]
        if self.halted_cycles > 0:
            lines.append(
                "halt_quiescent="
                f"{self.halt_quiescent_cycles}/{self.halted_cycles} "
                f"({self.ratio(self.halt_quiescent_cycles, self.halted_cycles):.3f})"
            )
        for label in ("a", "f", "b", "c", "d", "e", "h", "l", "sp", "pc"):
            value = getattr(self, f"reg_{label}_we_cycles")
            lines.append(f"{label}_we={value}/{self.total_cycles} ({self.ratio(value):.3f})")
        return lines

    def anomaly_lines(self) -> list[str]:
        anomalies: list[str] = []
        if self.total_cycles > 0 and self.reg_pc_we_cycles * 2 > self.total_cycles:
            anomalies.append("pc_write_enable duty cycle exceeds 50%")
        if self.halted_cycles > 0 and self.halt_quiescent_cycles < self.halted_cycles:
            anomalies.append("halted window includes non-quiescent cycles")
        return anomalies


async def read_power_metrics(dut) -> PowerMetrics:
    await ReadOnly()
    metrics = PowerMetrics(
        total_cycles=int(dut.metric_total_cycles.value),
        bus_active_cycles=int(dut.metric_bus_active_cycles.value),
        alu_active_cycles=int(dut.metric_alu_active_cycles.value),
        halted_cycles=int(dut.metric_halted_cycles.value),
        halt_quiescent_cycles=int(dut.metric_halt_quiescent_cycles.value),
        reg_a_we_cycles=int(dut.metric_reg_a_we_cycles.value),
        reg_f_we_cycles=int(dut.metric_reg_f_we_cycles.value),
        reg_b_we_cycles=int(dut.metric_reg_b_we_cycles.value),
        reg_c_we_cycles=int(dut.metric_reg_c_we_cycles.value),
        reg_d_we_cycles=int(dut.metric_reg_d_we_cycles.value),
        reg_e_we_cycles=int(dut.metric_reg_e_we_cycles.value),
        reg_h_we_cycles=int(dut.metric_reg_h_we_cycles.value),
        reg_l_we_cycles=int(dut.metric_reg_l_we_cycles.value),
        reg_sp_we_cycles=int(dut.metric_reg_sp_we_cycles.value),
        reg_pc_we_cycles=int(dut.metric_reg_pc_we_cycles.value),
    )
    await Timer(1, units="ps")
    return metrics


def append_metrics_artifact(suite_label: str, case_name: str, metrics: PowerMetrics) -> Path:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    target = ARTIFACT_ROOT / f"{suite_label}.json"
    payload: dict[str, object]
    if target.exists():
        payload = json.loads(target.read_text(encoding="utf-8"))
    else:
        payload = {"suite": suite_label, "cases": []}
    payload.setdefault("suite", suite_label)
    payload.setdefault("cases", [])
    payload["cases"].append(
        {
            "case": case_name,
            "metrics": asdict(metrics),
            "summary": metrics.summary_lines(),
            "anomalies": metrics.anomaly_lines(),
        }
    )
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
