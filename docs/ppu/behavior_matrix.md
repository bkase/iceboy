# PPU Write Visibility Matrix

This matrix is the architectural contract for when a CPU write becomes visible to
the renderer. It is intentionally separate from raw register storage.

| Register / bits | Visibility point | Contract |
| --- | --- | --- |
| `LYC` | Immediate / continuous | `LY == LYC` is evaluated against the current live `LY` value with no scanline-delay shadow. |
| `STAT[6:3]` | Immediate / continuous | Interrupt select bits feed STAT-line evaluation as soon as the write is accepted. |
| `SCX[2:0]` | Mode-2 boundary sample | Low scroll bits are sampled at mode-2 start for initial pixel discard. |
| `SCX[7:3]` | Tile-fetch live sample | High scroll bits are re-read on background/window tile fetches. |
| `SCY` | Tile-fetch live sample | Vertical scroll is re-read on tile fetches instead of being frozen for the whole line. |
| `WX` | Live compare | The window trigger checks live `WX` against rendered `X + 7`. |
| `WY` | Mode-2 boundary sample | Window Y arming is decided only at the start of mode 2 for the line. |
| `BGP` | Pixel-pop sample | Background palette application observes the palette byte at the pop boundary. |
| `OBP0`, `OBP1` | Pixel-pop sample | Object palette application observes the palette byte at the pop boundary. |
| `LCDC.7` | Immediate control transition | LCD off enters `Disabled` immediately; LCD on enters `WarmupBlankFrame` immediately. |
| `LCDC.6` | Window tile-fetch live sample | Window map selection is read when window tile fetches occur. |
| `LCDC.5` | Mode-2 boundary sample | Window enable is captured at mode-2 start for the line. |
| `LCDC.4` | Tile-fetch live sample | BG/window tile data region selection is read on tile fetch. |
| `LCDC.3` | Tile-fetch live sample | BG tilemap selection is read on background tile fetch. |
| `LCDC.2` | Object metadata sample | Object size is consumed when object row metadata is resolved. |
| `LCDC.1` | Object pipeline live sample | Object enable gates object selection/fetch/mix work when that work is reached. |
| `LCDC.0` | Pixel-mix live sample | BG enable affects background/window contribution at mix/pop time. |

The implementation anchors for this matrix are:

- `src/ppu/sem/sample.spade` for mode-2 and fetch/pop sampling
- `src/ppu/rtl/regs.spade` for immediate programmer-visible storage
- `src/ppu/rtl/timing.spade` for LCDC.7 run-state transitions
