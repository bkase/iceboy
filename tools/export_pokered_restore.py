from __future__ import annotations

import argparse
from pathlib import Path

from pyboy import PyBoy

VRAM_SIZE = 0x2000
OAM_SIZE = 0xA0
WRAM_SIZE = 0x2000
HRAM_SIZE = 0x7F
MBC_RAM_BANK_SIZE = 0x2000
ROM_BANK_SIZE = 0x4000
LCD_SCANLINE_COUNT = 144
LCD_SCANLINE_PARAM_SIZE = 5
RENDERER_FRAME_BYTES = 160 * 144 * 4
RENDERER_ATTR_BYTES = 160 * 144
RAM_STATE_SIZE_DMG = 0x2000 + 0x60 + 0x4C + 0x7F + 0x34


def _read_u16le(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _parse_cpu_state_prefix(state_bytes: bytes) -> dict[str, int]:
    if len(state_bytes) < 23:
        raise ValueError("state file is too short to contain the CPU prefix")
    state_version = state_bytes[0]
    hl = _read_u16le(state_bytes, 11)
    ime_offset = 17
    ie = state_bytes[ime_offset + 3] if state_version >= 5 else 0
    if_reg = state_bytes[ime_offset + 5] if state_version >= 8 else 0
    return {
        "state_version": state_version,
        "a": state_bytes[5],
        "f": state_bytes[6],
        "b": state_bytes[7],
        "c": state_bytes[8],
        "d": state_bytes[9],
        "e": state_bytes[10],
        "h": (hl >> 8) & 0xFF,
        "l": hl & 0xFF,
        "sp": _read_u16le(state_bytes, 13),
        "pc": _read_u16le(state_bytes, 15),
        "ime": state_bytes[ime_offset],
        "halted": state_bytes[ime_offset + 1],
        "stopped": state_bytes[ime_offset + 2],
        "ie": ie,
        "if": if_reg,
    }


def _external_ram_bank_count(ram_size_code: int) -> int:
    return {
        0x00: 0,
        0x01: 0,
        0x02: 1,
        0x03: 4,
        0x04: 16,
        0x05: 8,
    }.get(ram_size_code, 0)


def _read_memory_range(memory, start: int, size: int, *, bank: int | None = None) -> bytes:
    if bank is None:
        return bytes(int(memory[address]) & 0xFF for address in range(start, start + size))
    return bytes(int(memory[bank, address]) & 0xFF for address in range(start, start + size))


def _infer_selected_rom_bank(memory, rom_bytes: bytes, external_rom_count: int) -> int:
    live_window = bytes(int(memory[address]) & 0xFF for address in range(0x4000, 0x4100))
    for bank_index in range(1, max(1, external_rom_count)):
        start = bank_index * ROM_BANK_SIZE
        if rom_bytes[start : start + len(live_window)] == live_window:
            return bank_index
    return 1


def _infer_selected_ram_bank(memory, cart_ram_banks: list[bytes]) -> int:
    if not cart_ram_banks:
        return 0
    live_window = _read_memory_range(memory, 0xA000, MBC_RAM_BANK_SIZE)
    for bank_index, bank_bytes in enumerate(cart_ram_banks):
        if bank_bytes == live_window:
            return bank_index
    return 0


def _bytes_from_iter(values) -> bytes:
    return bytes(int(value) & 0xFF for value in values)


def _cpu_state_size(state_version: int) -> int:
    size = 6 + 2 + 2 + 2 + 1 + 1 + 1
    if state_version >= 5:
        size += 1
    if state_version >= 8:
        size += 2
    if state_version >= 12:
        size += 8
    return size


def _scanline_param_offset(state_version: int) -> int:
    if state_version < 11:
        return -1
    header_size = 5
    lcd_prefix_size = VRAM_SIZE + OAM_SIZE + 4 + 1
    if state_version >= 5:
        lcd_prefix_size += 2
    lcd_prefix_size += 4
    return header_size + _cpu_state_size(state_version) + lcd_prefix_size


def _dominant_visible_restart_regs(state_bytes: bytes, state_version: int, *, fallback: dict[str, int]) -> dict[str, int]:
    offset = _scanline_param_offset(state_version)
    if offset < 0:
        return fallback
    end = offset + LCD_SCANLINE_COUNT * LCD_SCANLINE_PARAM_SIZE
    if end > len(state_bytes):
        return fallback

    counts: dict[tuple[int, int, int, int, int], int] = {}
    for line in range(8, LCD_SCANLINE_COUNT):
        entry_offset = offset + line * LCD_SCANLINE_PARAM_SIZE
        scx, scy, wx, wy, tiledata_select = state_bytes[entry_offset : entry_offset + LCD_SCANLINE_PARAM_SIZE]
        key = (scx, scy, wx, wy, tiledata_select)
        counts[key] = counts.get(key, 0) + 1

    if not counts:
        return fallback

    scx, scy, wx, wy, tiledata_select = max(counts.items(), key=lambda item: item[1])[0]
    restart_lcdc = (fallback["restart_lcdc"] & ~0x10) | (0x10 if tiledata_select else 0x00)
    return {
        "restart_lcdc": restart_lcdc,
        "restart_scx": scx,
        "restart_scy": scy,
        "restart_wx": wx,
        "restart_wy": wy,
    }


def _state_header_size(state_version: int) -> int:
    size = 2
    if state_version >= 8:
        size += 3
    return size


def _lcd_state_size(state_version: int) -> int:
    size = VRAM_SIZE + OAM_SIZE + 4
    if state_version >= 5:
        size += 3
    size += 4
    if state_version >= 11:
        size += LCD_SCANLINE_COUNT * LCD_SCANLINE_PARAM_SIZE
    if state_version >= 8:
        size += 1 + 1 + 8 + 8 + 1
        if state_version >= 13:
            size += 3
        if state_version >= 12:
            size += 8
    return size


def _sound_state_size(state_version: int) -> int:
    if state_version < 13:
        return 0
    if state_version == 13:
        return 16 + 77 + 57 + 62 + 65
    return 1955


def _renderer_state_size(state_version: int) -> int:
    size = 0
    if 2 <= state_version < 11:
        size += LCD_SCANLINE_COUNT * LCD_SCANLINE_PARAM_SIZE
    if state_version >= 6:
        size += RENDERER_FRAME_BYTES
        if state_version >= 10:
            size += RENDERER_ATTR_BYTES
    return size


def _timer_state_offset(state_version: int) -> int:
    return (
        _state_header_size(state_version)
        + _cpu_state_size(state_version)
        + _lcd_state_size(state_version)
        + _sound_state_size(state_version)
        + _renderer_state_size(state_version)
        + RAM_STATE_SIZE_DMG
    )


def _parse_timer_state(state_bytes: bytes, state_version: int) -> dict[str, int]:
    if state_version < 5:
        return {
            "timer_div": 0,
            "timer_tima": 0,
            "timer_div_counter": 0,
            "timer_tima_counter": 0,
            "timer_tma": 0,
            "timer_tac": 0,
        }

    offset = _timer_state_offset(state_version)
    if offset + 8 > len(state_bytes):
        raise ValueError("state file is too short to contain the timer state")

    return {
        "timer_div": state_bytes[offset],
        "timer_tima": state_bytes[offset + 1],
        "timer_div_counter": _read_u16le(state_bytes, offset + 2),
        "timer_tima_counter": _read_u16le(state_bytes, offset + 4),
        "timer_tma": state_bytes[offset + 6],
        "timer_tac": state_bytes[offset + 7],
    }


def _parse_lcd_timing_state(state_bytes: bytes, state_version: int) -> dict[str, int]:
    if state_version < 8:
        return {
            "lcd_clock": 0,
            "lcd_clock_target": 0,
            "next_stat_mode": 0,
        }

    # LCD timing in PyBoy v8+ savestates sits after:
    # VRAM, OAM, 11 LCD registers, and 2 LCD mode-flag bytes.
    offset = _state_header_size(state_version) + _cpu_state_size(state_version) + VRAM_SIZE + OAM_SIZE + 13
    if state_version >= 13:
        offset += 8
    if offset + 17 > len(state_bytes):
        raise ValueError("state file is too short to contain the LCD timing state")

    return {
        "lcd_clock": int.from_bytes(state_bytes[offset : offset + 8], "little"),
        "lcd_clock_target": int.from_bytes(state_bytes[offset + 8 : offset + 16], "little"),
        "next_stat_mode": state_bytes[offset + 16],
    }


def export_restore_manifest(*, rom_path: Path, state_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    state_bytes = state_path.read_bytes()
    if not state_bytes:
        raise ValueError(f"{state_path} is empty")
    cpu_state = _parse_cpu_state_prefix(state_bytes)
    state_version = cpu_state["state_version"]
    timer_state = _parse_timer_state(state_bytes, state_version)
    lcd_timing_state = _parse_lcd_timing_state(state_bytes, state_version)
    rom_bytes = rom_path.read_bytes()
    cart_type = rom_bytes[0x147]
    external_rom_count = max(1, len(rom_bytes) // ROM_BANK_SIZE)
    external_ram_count = _external_ram_bank_count(rom_bytes[0x149])

    pyboy = PyBoy(
        str(rom_path),
        window="null",
        sound_emulated=False,
        no_input=True,
        log_level="ERROR",
        cgb=False,
    )
    try:
        pyboy.set_emulation_speed(0)
        with state_path.open("rb") as handle:
            pyboy.load_state(handle)

        memory = pyboy.memory
        registers = pyboy.register_file

        vram_path = out_dir / "restore.vram.bin"
        oam_path = out_dir / "restore.oam.bin"
        wram_path = out_dir / "restore.wram.bin"
        hram_path = out_dir / "restore.hram.bin"
        cartram_path = out_dir / "restore.cartram.bin"
        vram_path.write_bytes(_read_memory_range(memory, 0x8000, VRAM_SIZE))
        oam_path.write_bytes(_read_memory_range(memory, 0xFE00, OAM_SIZE))
        wram_path.write_bytes(_read_memory_range(memory, 0xC000, WRAM_SIZE))
        hram_path.write_bytes(_read_memory_range(memory, 0xFF80, HRAM_SIZE))

        cartram = bytearray()
        cart_ram_banks: list[bytes] = []
        for bank_index in range(external_ram_count):
            bank_bytes = _read_memory_range(memory, 0xA000, MBC_RAM_BANK_SIZE, bank=bank_index)
            cart_ram_banks.append(bank_bytes)
            cartram.extend(bank_bytes)
        cartram_path.write_bytes(bytes(cartram))
        rombank_selected = _infer_selected_rom_bank(memory, rom_bytes, external_rom_count)
        rambank_selected = _infer_selected_ram_bank(memory, cart_ram_banks)
        rambank_enabled = external_ram_count > 0
        restart_regs = _dominant_visible_restart_regs(
            state_bytes,
            state_version,
            fallback={
                "restart_lcdc": int(memory[0xFF40]),
                "restart_scx": int(memory[0xFF43]),
                "restart_scy": int(memory[0xFF42]),
                "restart_wx": int(memory[0xFF4B]),
                "restart_wy": int(memory[0xFF4A]),
            },
        )

        manifest_lines = [
            f"state_version={state_version}",
            f"title={pyboy.cartridge_title.strip()}",
            f"cart_type={cart_type}",
            f"external_rom_count={external_rom_count}",
            f"external_ram_count={external_ram_count}",
            f"a={int(registers.A)}",
            f"f={int(registers.F)}",
            f"b={int(registers.B)}",
            f"c={int(registers.C)}",
            f"d={int(registers.D)}",
            f"e={int(registers.E)}",
            f"h={(int(registers.HL) >> 8) & 0xFF}",
            f"l={int(registers.HL) & 0xFF}",
            f"sp={int(registers.SP)}",
            f"pc={int(registers.PC)}",
            f"ime={cpu_state['ime']}",
            f"halted={int(cpu_state['halted'] != 0)}",
            f"stopped={int(cpu_state['stopped'] != 0)}",
            f"ie={int(memory[0xFFFF])}",
            f"if={int(memory[0xFF0F])}",
            f"joyp_select={(int(memory[0xFF00]) >> 4) & 0x3}",
            f"lcdc={int(memory[0xFF40])}",
            f"stat={int(memory[0xFF41])}",
            f"scy={int(memory[0xFF42])}",
            f"scx={int(memory[0xFF43])}",
            f"ly={int(memory[0xFF44])}",
            f"lyc={int(memory[0xFF45])}",
            f"bgp={int(memory[0xFF47])}",
            f"obp0={int(memory[0xFF48])}",
            f"obp1={int(memory[0xFF49])}",
            f"wy={int(memory[0xFF4A])}",
            f"wx={int(memory[0xFF4B])}",
            f"restart_lcdc={restart_regs['restart_lcdc']}",
            f"restart_scx={restart_regs['restart_scx']}",
            f"restart_scy={restart_regs['restart_scy']}",
            f"restart_wx={restart_regs['restart_wx']}",
            f"restart_wy={restart_regs['restart_wy']}",
            f"timer_div={timer_state['timer_div']}",
            f"timer_div_counter={timer_state['timer_div_counter']}",
            f"timer_tima={timer_state['timer_tima']}",
            f"timer_tma={timer_state['timer_tma']}",
            f"timer_tac={timer_state['timer_tac']}",
            f"lcd_clock={lcd_timing_state['lcd_clock']}",
            f"lcd_clock_target={lcd_timing_state['lcd_clock_target']}",
            f"next_stat_mode={lcd_timing_state['next_stat_mode']}",
            f"serial_sb={int(memory[0xFF01])}",
            f"serial_sc={int(memory[0xFF02])}",
            f"rombank_selected={rombank_selected}",
            f"rombank_selected_low=0",
            f"rambank_selected={rambank_selected}",
            f"rambank_enabled={int(rambank_enabled)}",
            f"rtc_enabled=0",
            f"vram={vram_path.name}",
            f"oam={oam_path.name}",
            f"wram={wram_path.name}",
            f"hram={hram_path.name}",
            f"cartram={cartram_path.name}",
        ]
        manifest_path = out_dir / "restore.manifest"
        manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        return manifest_path
    finally:
        pyboy.stop(save=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest_path = export_restore_manifest(rom_path=args.rom, state_path=args.state, out_dir=args.out_dir)
    print(f"exported restore manifest {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
