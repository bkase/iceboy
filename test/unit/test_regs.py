# top = cpu::regs_test_top::regs_test_top
import cocotb
from cocotb.triggers import Timer


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "masked_f": (output_value >> 308) & 0xFF,
        "decoded_z": bool((output_value >> 307) & 0x1),
        "decoded_n": bool((output_value >> 306) & 0x1),
        "decoded_h": bool((output_value >> 305) & 0x1),
        "decoded_c": bool((output_value >> 304) & 0x1),
        "packed_f": (output_value >> 296) & 0xFF,
        "roundtrip_f": (output_value >> 288) & 0xFF,
        "r8_selected": (output_value >> 280) & 0xFF,
        "r8_a": (output_value >> 272) & 0xFF,
        "r8_b": (output_value >> 264) & 0xFF,
        "r8_c": (output_value >> 256) & 0xFF,
        "r8_d": (output_value >> 248) & 0xFF,
        "r8_e": (output_value >> 240) & 0xFF,
        "r8_h": (output_value >> 232) & 0xFF,
        "r8_l": (output_value >> 224) & 0xFF,
        "r8_bc": (output_value >> 208) & 0xFFFF,
        "r8_de": (output_value >> 192) & 0xFFFF,
        "r8_hl": (output_value >> 176) & 0xFFFF,
        "r8_af": (output_value >> 160) & 0xFFFF,
        "r16_selected": (output_value >> 144) & 0xFFFF,
        "r16_a": (output_value >> 136) & 0xFF,
        "r16_f": (output_value >> 128) & 0xFF,
        "r16_b": (output_value >> 120) & 0xFF,
        "r16_c": (output_value >> 112) & 0xFF,
        "r16_d": (output_value >> 104) & 0xFF,
        "r16_e": (output_value >> 96) & 0xFF,
        "r16_h": (output_value >> 88) & 0xFF,
        "r16_l": (output_value >> 80) & 0xFF,
        "r16_bc": (output_value >> 64) & 0xFFFF,
        "r16_de": (output_value >> 48) & 0xFFFF,
        "r16_hl": (output_value >> 32) & 0xFFFF,
        "r16_sp": (output_value >> 16) & 0xFFFF,
        "r16_af": output_value & 0xFFFF,
    }


R8_NAMES = ("a", "b", "c", "d", "e", "h", "l")
PAIR_NAMES = ("bc", "de", "hl", "sp", "af")


async def sample(dut, *, f: int, z: bool, n: bool, h: bool, c: bool, r8_sel: int, r8_val: int, pair_sel: int, pair_val: int) -> dict[str, int | bool]:
    dut.f_i.value = f & 0xFF
    dut.z_i.value = int(z)
    dut.n_i.value = int(n)
    dut.h_i.value = int(h)
    dut.c_i.value = int(c)
    dut.r8_sel_i.value = r8_sel & 0x7
    dut.r8_val_i.value = r8_val & 0xFF
    dut.pair_sel_i.value = pair_sel & 0x7
    dut.pair_val_i.value = pair_val & 0xFFFF
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_mask_and_roundtrip_cover_all_f_values(dut):
    for value in range(256):
        snapshot = await sample(dut, f=value, z=False, n=False, h=False, c=False, r8_sel=0, r8_val=0, pair_sel=0, pair_val=0)
        assert snapshot["masked_f"] == (value & 0xF0)
        assert snapshot["roundtrip_f"] == (value & 0xF0)


@cocotb.test()
async def test_decode_extracts_znhc_bits(dut):
    cases = [
        (0x00, (False, False, False, False)),
        (0x80, (True, False, False, False)),
        (0xF0, (True, True, True, True)),
        (0x5F, (False, True, False, True)),
    ]
    for f_value, expected in cases:
        snapshot = await sample(dut, f=f_value, z=False, n=False, h=False, c=False, r8_sel=0, r8_val=0, pair_sel=0, pair_val=0)
        assert (
            snapshot["decoded_z"],
            snapshot["decoded_n"],
            snapshot["decoded_h"],
            snapshot["decoded_c"],
        ) == expected


@cocotb.test()
async def test_pack_flags_zeroes_low_nibble_and_covers_all_patterns(dut):
    seen = set()
    for z in [False, True]:
        for n in [False, True]:
            for h in [False, True]:
                for c in [False, True]:
                    snapshot = await sample(dut, f=0x00, z=z, n=n, h=h, c=c, r8_sel=0, r8_val=0, pair_sel=0, pair_val=0)
                    packed = int(snapshot["packed_f"])
                    assert packed & 0x0F == 0
                    assert snapshot["roundtrip_f"] == 0
                    seen.add(packed)
    assert len(seen) == 16


@cocotb.test()
async def test_set_r8_roundtrip_isolation_and_pair_projection(dut):
    pair_projection = {
        "a": ("r8_af", lambda value: value << 8),
        "b": ("r8_bc", lambda value: value << 8),
        "c": ("r8_bc", lambda value: value),
        "d": ("r8_de", lambda value: value << 8),
        "e": ("r8_de", lambda value: value),
        "h": ("r8_hl", lambda value: value << 8),
        "l": ("r8_hl", lambda value: value),
    }
    for sel, name in enumerate(R8_NAMES):
        for value in (0x00, 0x42, 0xFF):
            snapshot = await sample(dut, f=0x00, z=False, n=False, h=False, c=False, r8_sel=sel, r8_val=value, pair_sel=0, pair_val=0)
            assert snapshot["r8_selected"] == value
            for other in R8_NAMES:
                expected = value if other == name else 0
                assert snapshot[f"r8_{other}"] == expected
            pair_name, projector = pair_projection[name]
            assert snapshot[pair_name] == projector(value)
            for other_pair in ("r8_bc", "r8_de", "r8_hl", "r8_af"):
                if other_pair == pair_name:
                    continue
                assert snapshot[other_pair] == 0


@cocotb.test()
async def test_set_r16_roundtrip_byte_order_and_isolation(dut):
    expected_bytes = {
        "bc": ("r16_b", "r16_c"),
        "de": ("r16_d", "r16_e"),
        "hl": ("r16_h", "r16_l"),
        "af": ("r16_a", "r16_f"),
    }
    for sel, name in enumerate(PAIR_NAMES):
        for value in (0x0000, 0x1234, 0xFFFF):
            snapshot = await sample(dut, f=0x00, z=False, n=False, h=False, c=False, r8_sel=0, r8_val=0, pair_sel=sel, pair_val=value)
            masked_value = value & 0xFFF0 if name == "af" else value
            assert snapshot["r16_selected"] == masked_value
            for pair_name in PAIR_NAMES:
                expected = masked_value if pair_name == name else 0
                assert snapshot[f"r16_{pair_name}"] == expected
            if name in expected_bytes:
                hi_field, lo_field = expected_bytes[name]
                assert snapshot[hi_field] == ((masked_value >> 8) & 0xFF)
                assert snapshot[lo_field] == (masked_value & 0xFF)
            elif name == "sp":
                assert snapshot["r16_sp"] == masked_value


@cocotb.test()
async def test_flag_helper_roundtrip_and_all_flag_combinations(dut):
    for z in [False, True]:
        for n in [False, True]:
            for h in [False, True]:
                for c in [False, True]:
                    packed = ((int(z) << 7) | (int(n) << 6) | (int(h) << 5) | (int(c) << 4)) & 0xF0
                    snapshot = await sample(dut, f=packed, z=z, n=n, h=h, c=c, r8_sel=0, r8_val=0, pair_sel=0, pair_val=0)
                    assert snapshot["packed_f"] == packed
                    assert snapshot["roundtrip_f"] == packed
                    assert (
                        snapshot["decoded_z"],
                        snapshot["decoded_n"],
                        snapshot["decoded_h"],
                        snapshot["decoded_c"],
                    ) == (z, n, h, c)
