# top = cpu::regs_test_top::flag_helpers_test_top
import cocotb
from cocotb.triggers import Timer


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "masked_f": (output_value >> 20) & 0xFF,
        "decoded_z": bool((output_value >> 19) & 0x1),
        "decoded_n": bool((output_value >> 18) & 0x1),
        "decoded_h": bool((output_value >> 17) & 0x1),
        "decoded_c": bool((output_value >> 16) & 0x1),
        "packed_f": (output_value >> 8) & 0xFF,
        "roundtrip_f": output_value & 0xFF,
    }


async def sample(dut, *, f: int, z: bool, n: bool, h: bool, c: bool) -> dict[str, int | bool]:
    dut.f_i.value = f & 0xFF
    dut.z_i.value = int(z)
    dut.n_i.value = int(n)
    dut.h_i.value = int(h)
    dut.c_i.value = int(c)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_mask_and_roundtrip_cover_all_f_values(dut):
    for value in range(256):
        snapshot = await sample(dut, f=value, z=False, n=False, h=False, c=False)
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
        snapshot = await sample(dut, f=f_value, z=False, n=False, h=False, c=False)
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
                    snapshot = await sample(dut, f=0x00, z=z, n=n, h=h, c=c)
                    packed = int(snapshot["packed_f"])
                    assert packed & 0x0F == 0
                    assert snapshot["roundtrip_f"] == 0
                    seen.add(packed)
    assert len(seen) == 16
