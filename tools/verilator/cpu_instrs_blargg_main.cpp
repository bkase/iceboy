#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "Vcpu_test_top_verilator_wrapper.h"
#include "verilated.h"

namespace {

constexpr uint16_t JOYP_ADDR = 0xFF00;
constexpr uint16_t SB_ADDR = 0xFF01;
constexpr uint16_t SC_ADDR = 0xFF02;
constexpr uint16_t DIV_ADDR = 0xFF04;
constexpr uint16_t TIMA_ADDR = 0xFF05;
constexpr uint16_t TMA_ADDR = 0xFF06;
constexpr uint16_t TAC_ADDR = 0xFF07;
constexpr uint16_t IF_ADDR = 0xFF0F;
constexpr uint16_t IE_ADDR = 0xFFFF;

constexpr uint8_t BUS_REQ_IDLE = 0;
constexpr uint8_t BUS_REQ_READ = 1;
constexpr uint8_t BUS_REQ_WRITE = 2;

constexpr uint8_t TIMER_IF_BIT = 0x04;
constexpr uint8_t SERIAL_IF_BIT = 0x08;

constexpr uint64_t RESET_STIMULUS = 0x3;  // freeze_arch_time + cpu_hold_only

struct Trace {
    uint8_t bus_req_kind = 0;
    uint16_t bus_req_addr = 0;
    uint8_t bus_req_data = 0;
    bool irq_ack_valid = false;
    uint8_t irq_ack_bit = 0;
};

struct Config {
    std::string rom_path;
    std::string serial_capture_path;
    uint64_t max_mcycles = 80000000ULL;
    uint64_t stop_at_serial_count = 0;
    uint64_t progress_interval = 0;
};

bool tac_enabled(uint8_t tac) {
    return (tac & 0x4) == 0x4;
}

bool timer_bit(uint32_t sys_counter, uint8_t tac) {
    const int shift = (tac & 0x3) == 0 ? 9 : (tac & 0x3) == 1 ? 3 : (tac & 0x3) == 2 ? 5 : 7;
    return ((sys_counter >> shift) & 0x1U) != 0;
}

uint8_t ack_mask(bool valid, uint8_t ack_bit) {
    return (valid && ack_bit < 5) ? static_cast<uint8_t>(1U << ack_bit) : 0;
}

uint64_t encode_stimulus(uint8_t if_set_bits) {
    return static_cast<uint64_t>(if_set_bits & 0x1F) << 31;
}

Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        const std::string arg(argv[i]);
        if (arg.rfind("--rom=", 0) == 0) {
            cfg.rom_path = arg.substr(sizeof("--rom=") - 1);
        } else if (arg.rfind("--serial-capture=", 0) == 0) {
            cfg.serial_capture_path = arg.substr(sizeof("--serial-capture=") - 1);
        } else if (arg.rfind("--max-mcycles=", 0) == 0) {
            cfg.max_mcycles = std::stoull(arg.substr(sizeof("--max-mcycles=") - 1));
        } else if (arg.rfind("--stop-at-serial-count=", 0) == 0) {
            cfg.stop_at_serial_count = std::stoull(arg.substr(sizeof("--stop-at-serial-count=") - 1));
        } else if (arg.rfind("--progress-interval=", 0) == 0) {
            cfg.progress_interval = std::stoull(arg.substr(sizeof("--progress-interval=") - 1));
        }
    }
    return cfg;
}

Trace observe(const Vcpu_test_top_verilator_wrapper& top) {
    auto extract_bits = [&](int lsb, int width) -> uint64_t {
        uint64_t value = 0;
        for (int bit = 0; bit < width; ++bit) {
            const int absolute = lsb + bit;
            const uint32_t word = top.output___05F[absolute / 32];
            const uint32_t one = (word >> (absolute % 32)) & 0x1U;
            value |= static_cast<uint64_t>(one) << bit;
        }
        return value;
    };
    Trace trace;
    trace.irq_ack_valid = extract_bits(132, 1) != 0;
    trace.irq_ack_bit = static_cast<uint8_t>(extract_bits(129, 3));
    trace.bus_req_kind = static_cast<uint8_t>(extract_bits(47, 2));
    trace.bus_req_addr = static_cast<uint16_t>(extract_bits(31, 16));
    trace.bus_req_data = static_cast<uint8_t>(extract_bits(23, 8));
    return trace;
}

class BusModel {
  public:
    explicit BusModel(std::vector<uint8_t> rom_bytes)
        : rom_(std::move(rom_bytes)),
          rom_bank_count_(std::max<size_t>(1, rom_.size() / 0x4000)),
          is_mbc1_(rom_.size() >= 0x150 && (rom_[0x147] == 0x01 || rom_[0x147] == 0x02 || rom_[0x147] == 0x03)) {}

    uint8_t read(uint16_t addr) const {
        if (addr < 0x8000) {
            return cart_rom_read(addr);
        }
        if (addr >= 0xC000 && addr <= 0xDFFF) {
            return wram_[addr - 0xC000];
        }
        if (addr == JOYP_ADDR) {
            return joyp_visible();
        }
        if (addr == SB_ADDR) {
            return serial_sb_;
        }
        if (addr == SC_ADDR) {
            return serial_sc_;
        }
        if (addr == DIV_ADDR) {
            return static_cast<uint8_t>((sys_counter_ >> 8) & 0xFF);
        }
        if (addr == TIMA_ADDR) {
            return tima_;
        }
        if (addr == TMA_ADDR) {
            return tma_;
        }
        if (addr == TAC_ADDR) {
            return static_cast<uint8_t>(tac_ & 0x7);
        }
        if (addr == IF_ADDR) {
            return static_cast<uint8_t>(if_reg_ & 0x1F);
        }
        if (addr >= 0xFF80 && addr <= 0xFFFE) {
            return hram_[addr - 0xFF80];
        }
        if (addr == IE_ADDR) {
            return static_cast<uint8_t>(ie_reg_ & 0x1F);
        }
        return 0xFF;
    }

    void write(uint16_t addr, uint8_t value, std::ofstream& capture) {
        if (is_mbc1_ && addr < 0x8000) {
            cart_write(addr, value);
            return;
        }
        if (addr >= 0xC000 && addr <= 0xDFFF) {
            wram_[addr - 0xC000] = value;
        } else if (addr == JOYP_ADDR) {
            joyp_select_ = static_cast<uint8_t>((value >> 4) & 0x3);
        } else if (addr == SB_ADDR) {
            serial_sb_ = value;
        } else if (addr == SC_ADDR) {
            serial_sc_ = static_cast<uint8_t>(value & 0x83);
            if ((serial_sc_ & 0x81) == 0x81) {
                serial_cycles_left_ = 8;
                serial_capture_.push_back(serial_sb_);
                capture.put(static_cast<char>(serial_sb_));
            }
        } else if (addr >= 0xFF80 && addr <= 0xFFFE) {
            hram_[addr - 0xFF80] = value;
        }
    }

    uint8_t next_if_set_bits(bool write_en, uint16_t write_addr, uint8_t write_data) const {
        const bool write_div = write_en && write_addr == DIV_ADDR;
        const bool write_tima = write_en && write_addr == TIMA_ADDR;
        const bool write_tma = write_en && write_addr == TMA_ADDR;
        const bool write_tac = write_en && write_addr == TAC_ADDR;

        const uint32_t effective_sys_counter = write_div ? 0 : sys_counter_;
        const uint8_t next_tma = write_tma ? write_data : tma_;
        const uint8_t next_tac = write_tac ? static_cast<uint8_t>(write_data & 0x7) : tac_;
        const bool next_sampled_timer_enabled = tac_enabled(next_tac);
        const bool next_sampled_timer_bit = timer_bit(effective_sys_counter, next_tac);
        const bool timer_tick =
            sampled_timer_enabled_ && next_sampled_timer_enabled && sampled_timer_bit_ && !next_sampled_timer_bit;

        bool next_timer_irq = false;
        if (write_tima) {
            next_timer_irq = false;
        } else if (overflow_delay_ == 1) {
            next_timer_irq = true;
        } else if (overflow_delay_ == 0 && timer_tick && tima_ == 0xFF) {
            next_timer_irq = false;
        }

        const bool next_serial_irq = serial_cycles_left_ == 1 && (serial_sc_ & 0x81) == 0x81;
        return static_cast<uint8_t>((next_timer_irq ? TIMER_IF_BIT : 0) | (next_serial_irq ? SERIAL_IF_BIT : 0));
    }

    void advance_cycle(bool write_en, uint16_t write_addr, uint8_t write_data, uint8_t if_set_bits, bool irq_ack_valid, uint8_t irq_ack_bit) {
        const bool write_div = write_en && write_addr == DIV_ADDR;
        const bool write_tima = write_en && write_addr == TIMA_ADDR;
        const bool write_tma = write_en && write_addr == TMA_ADDR;
        const bool write_tac = write_en && write_addr == TAC_ADDR;
        const bool write_if = write_en && write_addr == IF_ADDR;
        const bool write_ie = write_en && write_addr == IE_ADDR;

        const uint32_t effective_sys_counter = write_div ? 0 : sys_counter_;
        const uint8_t next_tma = write_tma ? write_data : tma_;
        const uint8_t next_tac = write_tac ? static_cast<uint8_t>(write_data & 0x7) : tac_;
        const bool next_sampled_timer_enabled = tac_enabled(next_tac);
        const bool next_sampled_timer_bit = timer_bit(effective_sys_counter, next_tac);
        const bool timer_tick =
            sampled_timer_enabled_ && next_sampled_timer_enabled && sampled_timer_bit_ && !next_sampled_timer_bit;

        uint8_t next_tima = tima_;
        uint8_t next_overflow_delay = 0;
        if (write_tima) {
            next_tima = write_data;
        } else if (overflow_delay_ == 1) {
            next_tima = next_tma;
        } else if (overflow_delay_ > 1) {
            next_tima = tima_;
            next_overflow_delay = static_cast<uint8_t>(overflow_delay_ - 1);
        } else if (timer_tick) {
            if (tima_ == 0xFF) {
                next_tima = 0;
                next_overflow_delay = 4;
            } else {
                next_tima = static_cast<uint8_t>(tima_ + 1);
            }
        }

        tima_ = next_tima;
        tma_ = next_tma;
        tac_ = next_tac;
        if (serial_cycles_left_ > 0 && (serial_sc_ & 0x81) == 0x81) {
            --serial_cycles_left_;
            if (serial_cycles_left_ == 0) {
                serial_sb_ = serial_inject_value_;
                serial_sc_ &= 0x7F;
            }
        }
        sampled_timer_enabled_ = next_sampled_timer_enabled;
        sampled_timer_bit_ = next_sampled_timer_bit;
        overflow_delay_ = next_overflow_delay;
        sys_counter_ = write_div ? 4 : (sys_counter_ + 4);

        const uint8_t ack = ack_mask(irq_ack_valid, irq_ack_bit);
        ie_reg_ = static_cast<uint8_t>((write_ie ? write_data : ie_reg_) & 0x1F);
        const uint8_t cpu_written_if = static_cast<uint8_t>((write_if ? write_data : if_reg_) & 0x1F);
        if_reg_ = static_cast<uint8_t>(((cpu_written_if & ~ack) | if_set_bits) & 0x1F);
    }

    size_t serial_count() const { return serial_capture_.size(); }

  private:
    uint8_t joyp_visible() const {
        return static_cast<uint8_t>(0xC0 | ((joyp_select_ & 0x3) << 4) | 0x0F);
    }

    int rom_bank_value() const {
        const int bank = mbc1_rom_bank_low5_ & 0x1F;
        return bank == 0 ? 1 : bank;
    }

    int rom_bank_index(int bank) const {
        return static_cast<int>(bank % static_cast<int>(rom_bank_count_));
    }

    uint8_t cart_rom_read(uint16_t addr) const {
        if (!is_mbc1_) {
            return addr < rom_.size() ? rom_[addr] : 0xFF;
        }
        size_t rom_addr = 0;
        if (addr < 0x4000) {
            rom_addr = addr;
        } else {
            const int bank = rom_bank_index(rom_bank_value());
            rom_addr = static_cast<size_t>(bank) * 0x4000 + (addr - 0x4000);
        }
        return rom_addr < rom_.size() ? rom_[rom_addr] : 0xFF;
    }

    void cart_write(uint16_t addr, uint8_t value) {
        if (!is_mbc1_) {
            return;
        }
        if (addr >= 0x2000 && addr <= 0x3FFF) {
            mbc1_rom_bank_low5_ = static_cast<uint8_t>(value & 0x1F);
        }
    }

    std::vector<uint8_t> rom_;
    std::array<uint8_t, 0x2000> wram_{};
    std::array<uint8_t, 0x7F> hram_{};
    size_t rom_bank_count_ = 1;
    bool is_mbc1_ = false;
    uint8_t mbc1_rom_bank_low5_ = 1;
    uint8_t ie_reg_ = 0;
    uint8_t if_reg_ = 0;
    uint8_t joyp_select_ = 0x3;
    uint32_t sys_counter_ = 0;
    uint8_t tima_ = 0;
    uint8_t tma_ = 0;
    uint8_t tac_ = 0;
    uint8_t serial_sb_ = 0;
    uint8_t serial_sc_ = 0;
    uint8_t serial_cycles_left_ = 0;
    uint8_t serial_inject_value_ = 0xFF;
    bool sampled_timer_enabled_ = false;
    bool sampled_timer_bit_ = false;
    uint8_t overflow_delay_ = 0;
    std::vector<uint8_t> serial_capture_;
};

std::vector<uint8_t> load_rom(const std::string& path) {
    std::ifstream handle(path, std::ios::binary);
    if (!handle) {
        throw std::runtime_error("failed to open ROM: " + path);
    }
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(handle), std::istreambuf_iterator<char>());
}

void tick(Vcpu_test_top_verilator_wrapper& top) {
    top.clk_i = 0;
    top.eval();
    top.clk_i = 1;
    top.eval();
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    const Config cfg = parse_args(argc, argv);
    if (cfg.rom_path.empty() || cfg.serial_capture_path.empty()) {
        std::cerr << "missing --rom=<path> or --serial-capture=<path>\n";
        return 2;
    }

    std::ofstream capture(cfg.serial_capture_path, std::ios::binary | std::ios::trunc);
    if (!capture) {
        std::cerr << "failed to open serial capture path: " << cfg.serial_capture_path << "\n";
        return 2;
    }

    BusModel memory(load_rom(cfg.rom_path));
    Vcpu_test_top_verilator_wrapper top;
    top.bus_read_data_i = 0;
    top.irq_pending_i = 0;
    top.stimulus_i = RESET_STIMULUS;
    top.rst_i = 1;
    for (int i = 0; i < 2; ++i) {
        tick(top);
    }
    top.rst_i = 0;
    tick(top);

    uint64_t completed_mcycles = 0;
    while (completed_mcycles < cfg.max_mcycles && !Verilated::gotFinish()) {
        top.clk_i = 0;
        top.eval();

        const Trace trace = observe(top);
        const bool write_en = trace.bus_req_kind == BUS_REQ_WRITE;
        const uint8_t bus_read_data = trace.bus_req_kind == BUS_REQ_READ ? memory.read(trace.bus_req_addr) : 0;
        const uint8_t if_set_bits = memory.next_if_set_bits(write_en, trace.bus_req_addr, trace.bus_req_data);

        top.bus_read_data_i = bus_read_data;
        top.irq_pending_i = 0;
        top.stimulus_i = encode_stimulus(if_set_bits);

        top.eval();
        top.clk_i = 1;
        top.eval();

        if (write_en && !(trace.bus_req_addr >= DIV_ADDR && trace.bus_req_addr <= TAC_ADDR) && trace.bus_req_addr != IF_ADDR && trace.bus_req_addr != IE_ADDR) {
            memory.write(trace.bus_req_addr, trace.bus_req_data, capture);
        }
        memory.advance_cycle(write_en, trace.bus_req_addr, trace.bus_req_data, if_set_bits, trace.irq_ack_valid, trace.irq_ack_bit);

        ++completed_mcycles;
        if (cfg.progress_interval != 0 && (completed_mcycles % cfg.progress_interval) == 0) {
            std::cerr << "progress mcycles=" << completed_mcycles << " serial_count=" << memory.serial_count() << "\n";
        }
        if (cfg.stop_at_serial_count != 0 && memory.serial_count() >= cfg.stop_at_serial_count) {
            break;
        }
    }

    capture.flush();
    std::cout << "completed_mcycles=" << completed_mcycles << "\n";
    std::cout << "serial_count=" << memory.serial_count() << "\n";

    if (cfg.stop_at_serial_count != 0 && memory.serial_count() < cfg.stop_at_serial_count) {
        return 1;
    }
    if (completed_mcycles >= cfg.max_mcycles) {
        return 1;
    }
    return 0;
}
