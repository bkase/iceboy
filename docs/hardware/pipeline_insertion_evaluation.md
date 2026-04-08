# Pipeline Insertion Evaluation

- Hardware baseline: `/Users/bkase/Documents/iceboy/docs/hardware/icebreaker_up5k_baseline.json`
- nextpnr log: `/Users/bkase/Documents/iceboy/build/hw_baseline/nextpnr.log`

## Summary

- Overall recommendation: keep current latency; no pipeline insertion recommended
- Achieved fmax: 15.17 MHz
- Target fmax: 12.00 MHz
- Timing margin: 3.17 MHz
- Classified critical-path cluster: `cpu_datapath`

## Candidate Decisions

### decode -> operand select -> ALU -> flag pack

- Recommendation: defer
- Recorded fmax is 15.17 MHz against a 12.00 MHz target (3.17 MHz margin).
- Observed critical-path cluster is `cpu_datapath`, but the measured slack does not justify execute-stage latency changes yet.

### pixel fetch -> shade/merge -> output

- Recommendation: defer
- The recorded timing report does not put a PPU pixel pipeline on the top path.
- Observed critical-path cluster is `cpu_datapath`.

### cartridge/PPU address pipelines

- Recommendation: defer
- The current top path is a broad bus/peripheral readback chain, not a clean request/response leaf where latency can be inserted safely.
- Adding a register here would change visible memory timing before the architecture has a dedicated latency contract.

## Critical Path Excerpt

```text
Info: Critical path report for clock 'CLK$SB_IO_IN_$glb_clk' (posedge -> posedge):
Info:       type curr  total name
Info:   clk-skew  0.93  0.93 Net CLK$SB_IO_IN_$glb_clk (14,4) -> (25,0)
Info:                          Sink hardware_core_0.membus_0.wram_spram_0.SB_SPRAM256KA_0_RAM.CLOCK
Info:   clk-to-q  1.39  2.32 Source hardware_core_0.cpu_core_0.visible_arch_SB_DFFESS_Q_18_D_SB_LUT4_O_LC.O
Info:    routing  4.79  7.11 Net hardware_core_0.cpu[187] (14,4) -> (20,13)
Info:                          Sink hardware_core_0.cpu_core_0.step_mcycle_0.handle_execute_0.execute_word_alu_delta_0.alu_1.rot_shift_result_0._e_13632_SB_LUT4_I3_LC.I1
Info:                          Defined in:
Info:                               /Users/bkase/Documents/iceboy/build/spade.sv:5986.22-5986.27
Info:      logic  0.68  7.78 Source hardware_core_0.cpu_core_0.step_mcycle_0.handle_execute_0.execute_word_alu_delta_0.alu_1.rot_shift_result_0._e_13632_SB_LUT4_I3_LC.COUT
Info:    routing  0.00  7.78 Net hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CO_CI (20,13) -> (20,13)
Info:                          Sink hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CO_CI_SB_LUT4_I3_LC.CIN
Info:                          Defined in:
Info:                               /Users/bkase/Documents/iceboy/build/spade.sv:43726.23-43726.42
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/arith_map.v:62.5-70.4
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/abc9_model.v:4.9-4.11
Info:      logic  0.28  8.06 Source hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CO_CI_SB_LUT4_I3_LC.COUT
Info:    routing  0.00  8.06 Net hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3 (20,13) -> (20,13)
Info:                          Sink hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_LC.CIN
Info:                          Defined in:
Info:                               /Users/bkase/Documents/iceboy/build/spade.sv:43726.23-43726.42
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/arith_map.v:62.5-70.4
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/abc9_model.v:4.9-4.11
Info:      logic  0.28  8.34 Source hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_LC.COUT
Info:    routing  0.00  8.34 Net hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CI_CO (20,13) -> (20,13)
Info:                          Sink hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CI_CO_SB_LUT4_I3_LC.CIN
Info:                          Defined in:
Info:                               /Users/bkase/Documents/iceboy/build/spade.sv:43726.23-43726.42
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/arith_map.v:62.5-70.4
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/abc9_model.v:4.9-4.11
Info:      logic  0.28  8.62 Source hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_23_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CI_CO_SB_LUT4_I3_LC.COUT
Info:    routing  0.00  8.62 Net hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_20_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CO_CI_SB_CARRY_CO_CI (20,13) -> (20,13)
Info:                          Sink hardware_core_0.cpu_core_0.step_mcycle_0.handle_read_mem_0.__n10_SB_LUT4_I0_O_SB_LUT4_O_1_I1_SB_LUT4_O_LC.CIN
Info:                          Defined in:
Info:                               /Users/bkase/Documents/iceboy/build/spade.sv:43726.23-43726.42
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/arith_map.v:62.5-70.4
Info:                               /Users/bkase/Documents/iceboy/build/oss-cad-suite/libexec/../share/yosys/ice40/abc9_model.v:4.9-4.11
Info:      logic  0.28  8.90 Source hardware_core_0.cpu_core_0.step_mcycle_0.handle_read_mem_0.__n10_SB_LUT4_I0_O_SB_LUT4_O_1_I1_SB_LUT4_O_LC.COUT
Info:    routing  0.00  8.90 Net hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_20_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CO_CI (20,13) -> (20,13)
Info:                          Sink hardware_core_0.cpu_core_0.micro_state_SB_DFFE_Q_20_D_SB_LUT4_O_I3_SB_LUT4_O_1_I1_SB_LUT4_O_I3_SB_CARRY_CO_CI_SB_LUT4_I3_LC.CIN
```
