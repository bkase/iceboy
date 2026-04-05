This directory vendors a minimal offline subset of the pinned
`mooneye-test-suite` acceptance ROMs used by `bd-1s1z`.

Source repository:
- `https://github.com/Gekkio/mooneye-test-suite`
- pinned revision: `443f6e1f2a8d83ad9da051cbb960311c5aaaea66`

Binary origin:
- `https://gekkio.fi/files/mooneye-test-suite/mts-20240926-1737-443f6e1/`
- archive: `mts-20240926-1737-443f6e1.zip`

Vendored ROMs:
- `acceptance/ppu/vblank_stat_intr-GS.gb`
- `acceptance/ppu/stat_lyc_onoff.gb`
- `acceptance/ppu/stat_irq_blocking.gb`
- `acceptance/ppu/lcdon_timing-GS.gb`
- `acceptance/ppu/lcdon_write_timing-GS.gb`

These files are kept local so the PPU Wave A acceptance tests remain deterministic
and do not fetch network artifacts during pre-commit or CI.
