# Multi-Top iCEBreaker Build

`swim build` emits every reachable `#[no_mangle(all)]` entity into `build/spade.sv`, not just the module named by `swim.toml`'s `[synthesis].top`.

## Empirical result

Gate `bd-28kj` was checked by adding `src/board/dummy_top.spade` as a second board-level `#[no_mangle(all)]` entity while leaving `swim.toml` unchanged:

- `swim.toml` still declares `top = "icebreaker_top"`
- `~/.cargo/bin/swim build` succeeded
- `rg -n "module (dummy_top|icebreaker_top)" build/spade.sv` reported both modules

That means multi-top emission is free. The shared Spade-to-Verilog step stays fixed, and downstream hardware wrappers can choose the desired top at Yosys time with `synth_ice40 -top <name>`.

## Worked examples

Build the canonical hardware top without editing `swim.toml`:

```bash
tools/build_icebreaker_variant.sh \
  --top board::icebreaker_top::icebreaker_top \
  --module icebreaker_top \
  --board-top src/board/icebreaker_top.spade
```

Build the regression probe top from the same source tree and the same `build/spade.sv` flow:

```bash
tools/build_icebreaker_variant.sh --top dummy_top
```

Both commands share the same front-end build. The helper runs `swim build` once, then asks Yosys to synthesize the requested top from the generated `build/spade.sv`.

The verification flow uses the same variant contract, but stops after synthesis and resource checks:

```bash
tools/verify_icebreaker_variant.sh \
  --top board::icebreaker_top::icebreaker_top \
  --module icebreaker_top \
  --board-top src/board/icebreaker_top.spade \
  --enforce-budget
```

## Follow-on rule

Future iCEBreaker variant wrappers should treat `swim.toml` as stable and switch variants by selecting a different Yosys `-top`, never by editing the canonical `swim.toml` in place.
