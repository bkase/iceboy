# PPU Readback Matrix

This matrix defines what a CPU read observes. Readback semantics are distinct
from write visibility so debugger-friendly behavior does not silently become the
architectural contract.

| CPU-readable target | Readback rule | Contract |
| --- | --- | --- |
| `LY` | Live derived | `LY` is read-only and always reflects timing state, never a writable byte shadow. |
| `STAT` | Mixed stored + derived | Bits `6:3` are stored `StatSelect`, bit `2` is live `LY == LYC`, bits `1:0` are `visible_mode()`. |
| `STAT` while LCD disabled | Derived override | Mode bits report `0` when LCD is disabled. |
| `LCDC`, `SCY`, `SCX`, `LYC`, `WY`, `WX`, `BGP`, `OBP0`, `OBP1` | Stored byte | Reads return the current stored programmer-visible byte. |
| VRAM CPU reads | Access-policy mediated | Reads are allowed when not blocked; mode-3 reads become `UndefinedRead` by default. |
| OAM CPU reads | Access-policy mediated | Modes 2 and 3 block CPU OAM reads; LCD-off restores access. |
| LCD-off video memory | Fully accessible | With LCD off, VRAM/OAM reads are unblocked and STAT mode bits report `0`. |

The implementation anchors for this matrix are:

- `src/ppu/rtl/regs.spade` for register readback composition
- `src/ppu/sem/memory.spade` for blocked/undefined video-memory reads
- `src/ppu/sem/types.spade` and `src/ppu/rtl/timing.spade` for `visible_mode()`
