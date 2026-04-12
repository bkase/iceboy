# top = ppu::rtl::regs_bg_window_test_top::regs_bg_window_test_top
import cocotb
from cocotb.triggers import Timer


def decode_output(value: int) -> tuple[int, bool]:
    return value & 0xFF, bool((value >> 8) & 0x1)


@cocotb.test()
async def test_bg_window_profile_forces_obj_enable_low_in_storage_and_readback(dut):
    for lcdc_value in range(256):
        dut.lcdc_value_i.value = lcdc_value
        await Timer(1, units="ns")
        readback, obj_enable = decode_output(int(dut.output__.value))
        assert obj_enable is False
        assert readback == (lcdc_value & 0xFD)
