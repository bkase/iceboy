import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class BusDecodeAssetsTest(unittest.TestCase):
    def test_shared_bus_decode_modules_are_pure_and_wired_into_consumers(self) -> None:
        address_text = (ROOT / "src" / "bus" / "address_decode.spade").read_text(encoding="utf-8")
        io_text = (ROOT / "src" / "bus" / "io_decode.spade").read_text(encoding="utf-8")
        membus_text = (ROOT / "src" / "bus" / "membus.spade").read_text(encoding="utf-8")
        membus_alu_loop_text = (ROOT / "src" / "bus" / "membus_alu_loop.spade").read_text(encoding="utf-8")
        bus_main_text = (ROOT / "src" / "bus" / "main.spade").read_text(encoding="utf-8")

        self.assertIn("pub mod address_decode;", bus_main_text)
        self.assertIn("pub mod io_decode;", bus_main_text)
        self.assertIn("use lib::bus::address_decode::", membus_text)
        self.assertIn("use lib::bus::io_decode::", membus_text)
        self.assertIn("use lib::bus::address_decode::", membus_alu_loop_text)
        self.assertIn("use lib::bus::io_decode::", membus_alu_loop_text)
        self.assertIn("pub fn decode_region(", address_text)
        self.assertIn("pub fn dma_start(", io_text)

        for text in (address_text, io_text):
            self.assertNotIn("entity ", text)
            self.assertNotIn("reg(", text)
            self.assertNotIn("decl ", text)


if __name__ == "__main__":
    unittest.main()
