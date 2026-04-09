#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

#include "Vsoc_rom_top_verilator_wrapper.h"
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
constexpr uint16_t LCDC_ADDR = 0xFF40;
constexpr uint16_t STAT_ADDR = 0xFF41;
constexpr uint16_t SCY_ADDR = 0xFF42;
constexpr uint16_t SCX_ADDR = 0xFF43;
constexpr uint16_t LY_ADDR = 0xFF44;
constexpr uint16_t LYC_ADDR = 0xFF45;
constexpr uint16_t BGP_ADDR = 0xFF47;
constexpr uint16_t OBP0_ADDR = 0xFF48;
constexpr uint16_t OBP1_ADDR = 0xFF49;
constexpr uint16_t WY_ADDR = 0xFF4A;
constexpr uint16_t WX_ADDR = 0xFF4B;
constexpr uint16_t IE_ADDR = 0xFFFF;

constexpr uint16_t VRAM_BASE = 0x8000;
constexpr uint16_t VRAM_SIZE = 0x2000;
constexpr uint16_t OAM_BASE = 0xFE00;
constexpr uint16_t OAM_SIZE = 0x00A0;

constexpr uint8_t BUS_REQ_IDLE = 0;
constexpr uint8_t BUS_REQ_READ = 1;
constexpr uint8_t BUS_REQ_WRITE = 2;

constexpr uint8_t TIMER_IF_BIT = 0x04;
constexpr uint8_t SERIAL_IF_BIT = 0x08;
constexpr uint8_t VBLANK_IF_BIT = 0x01;
constexpr uint8_t STAT_IF_BIT = 0x02;

constexpr uint64_t RESET_STIMULUS = 0x3;  // freeze_arch_time + cpu_hold_only

constexpr int SCREEN_WIDTH = 160;
constexpr int SCREEN_HEIGHT = 144;
constexpr uint8_t FRAME_SHADE_WHITE = 0xFF;

enum class PpuMode : uint8_t {
    LcdOff = 0,
    OamScan = 1,
    PixelTransfer = 2,
    HBlank = 3,
    VBlank = 4,
};

struct Observation {
    bool ppu_vblank_req_window = false;
    bool ppu_stat_req_window = false;
    bool ppu_scanout_valid = false;
    uint8_t ppu_scanout_kind = 0;
    uint8_t ppu_scanout_x = 0;
    uint8_t ppu_scanout_y = 0;
    uint8_t ppu_scanout_shade = 0;
    uint8_t ppu_scanout_source = 0;
    uint8_t ppu_blank_reason = 0;
    bool ppu_vblank_req = false;
    bool ppu_stat_req = false;
    uint8_t ppu_mode = 0;
    uint8_t ppu_ly = 0;
    uint8_t ppu_stat = 0;
    uint8_t cpu_ime_state = 0;
    uint8_t cpu_halt_state = 0;
    uint8_t cpu_phase_kind = 0;
    bool irq_ack_valid = false;
    uint8_t irq_ack_bit = 0;
    uint16_t pc = 0;
    uint8_t cpu_a = 0;
    uint8_t cpu_b = 0;
    uint8_t cpu_c = 0;
    uint8_t cpu_d = 0;
    uint8_t cpu_e = 0;
    uint8_t cpu_h = 0;
    uint8_t cpu_l = 0;
    uint8_t bus_req_kind = 0;
    uint16_t bus_req_addr = 0;
    uint8_t bus_req_data = 0;
    uint8_t t_index = 0;
    bool m_ce = false;
    uint8_t preview_bus_req_kind = 0;
    uint16_t preview_bus_req_addr = 0;
    uint8_t preview_bus_req_data = 0;
};

struct Config {
    std::string rom_path;
    std::string frame_capture_path;
    std::string trace_path;
    uint64_t max_mcycles = 1800000ULL;
    uint64_t progress_interval = 0;
    uint64_t stable_frames = 2;
    uint64_t completed_frames = 0;
};

struct StepResult {
    Observation post;
    uint8_t preview_kind = 0;
    uint16_t preview_addr = 0;
    uint8_t preview_data = 0;
    bool video_sample_valid = false;
    Observation video_sample;
    bool write_allowed_valid = false;
    bool write_allowed = false;
    std::vector<Observation> scanout_observations;
};

bool tac_enabled(uint8_t tac) {
    return (tac & 0x4U) == 0x4U;
}

bool timer_bit(uint32_t sys_counter, uint8_t tac) {
    const int shift = (tac & 0x3U) == 0 ? 9 : (tac & 0x3U) == 1 ? 3 : (tac & 0x3U) == 2 ? 5 : 7;
    return ((sys_counter >> shift) & 0x1U) != 0;
}

uint8_t ack_mask(bool valid, uint8_t ack_bit) {
    return (valid && ack_bit < 5) ? static_cast<uint8_t>(1U << ack_bit) : 0;
}

Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        const std::string arg(argv[i]);
        if (arg.rfind("--rom=", 0) == 0) {
            cfg.rom_path = arg.substr(sizeof("--rom=") - 1);
        } else if (arg.rfind("--frame-capture=", 0) == 0) {
            cfg.frame_capture_path = arg.substr(sizeof("--frame-capture=") - 1);
        } else if (arg.rfind("--trace=", 0) == 0) {
            cfg.trace_path = arg.substr(sizeof("--trace=") - 1);
        } else if (arg.rfind("--max-mcycles=", 0) == 0) {
            cfg.max_mcycles = std::stoull(arg.substr(sizeof("--max-mcycles=") - 1));
        } else if (arg.rfind("--progress-interval=", 0) == 0) {
            cfg.progress_interval = std::stoull(arg.substr(sizeof("--progress-interval=") - 1));
        } else if (arg.rfind("--stable-frames=", 0) == 0) {
            cfg.stable_frames = std::stoull(arg.substr(sizeof("--stable-frames=") - 1));
        } else if (arg.rfind("--completed-frames=", 0) == 0) {
            cfg.completed_frames = std::stoull(arg.substr(sizeof("--completed-frames=") - 1));
        }
    }
    return cfg;
}

Observation observe(const Vsoc_rom_top_verilator_wrapper& top) {
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

    Observation obs;
    obs.ppu_vblank_req_window = extract_bits(186, 1) != 0;
    obs.ppu_stat_req_window = extract_bits(185, 1) != 0;
    obs.ppu_scanout_valid = extract_bits(184, 1) != 0;
    obs.ppu_scanout_kind = static_cast<uint8_t>(extract_bits(182, 2));
    obs.ppu_scanout_x = static_cast<uint8_t>(extract_bits(174, 8));
    obs.ppu_scanout_y = static_cast<uint8_t>(extract_bits(166, 8));
    obs.ppu_scanout_shade = static_cast<uint8_t>(extract_bits(164, 2));
    obs.ppu_scanout_source = static_cast<uint8_t>(extract_bits(162, 2));
    obs.ppu_blank_reason = static_cast<uint8_t>(extract_bits(160, 2));
    obs.ppu_vblank_req = extract_bits(159, 1) != 0;
    obs.ppu_stat_req = extract_bits(158, 1) != 0;
    obs.ppu_mode = static_cast<uint8_t>(extract_bits(155, 3));
    obs.ppu_ly = static_cast<uint8_t>(extract_bits(147, 8));
    obs.ppu_stat = static_cast<uint8_t>(extract_bits(139, 8));
    obs.cpu_ime_state = static_cast<uint8_t>(extract_bits(137, 2));
    obs.cpu_halt_state = static_cast<uint8_t>(extract_bits(135, 2));
    obs.cpu_phase_kind = static_cast<uint8_t>(extract_bits(131, 4));
    obs.irq_ack_valid = extract_bits(130, 1) != 0;
    obs.irq_ack_bit = static_cast<uint8_t>(extract_bits(127, 3));
    obs.pc = static_cast<uint16_t>(extract_bits(111, 16));
    obs.cpu_a = static_cast<uint8_t>(extract_bits(103, 8));
    obs.cpu_b = static_cast<uint8_t>(extract_bits(95, 8));
    obs.cpu_c = static_cast<uint8_t>(extract_bits(87, 8));
    obs.cpu_d = static_cast<uint8_t>(extract_bits(79, 8));
    obs.cpu_e = static_cast<uint8_t>(extract_bits(71, 8));
    obs.cpu_h = static_cast<uint8_t>(extract_bits(63, 8));
    obs.cpu_l = static_cast<uint8_t>(extract_bits(55, 8));
    obs.bus_req_kind = static_cast<uint8_t>(extract_bits(53, 2));
    obs.bus_req_addr = static_cast<uint16_t>(extract_bits(37, 16));
    obs.bus_req_data = static_cast<uint8_t>(extract_bits(29, 8));
    obs.t_index = static_cast<uint8_t>(extract_bits(27, 2));
    obs.m_ce = extract_bits(26, 1) != 0;
    obs.preview_bus_req_kind = static_cast<uint8_t>(extract_bits(24, 2));
    obs.preview_bus_req_addr = static_cast<uint16_t>(extract_bits(8, 16));
    obs.preview_bus_req_data = static_cast<uint8_t>(extract_bits(0, 8));
    return obs;
}

uint8_t scanout_dmg_gray(uint8_t shade) {
    switch (shade & 0x3U) {
        case 0:
            return 0xFF;
        case 1:
            return 0xAA;
        case 2:
            return 0x55;
        default:
            return 0x00;
    }
}

class BusModel {
  public:
    explicit BusModel(std::vector<uint8_t> rom_bytes)
        : rom_(std::move(rom_bytes)) {}

    void sync_integrated_ppu(const Observation& observation) {
        integrated_ppu_mode_ = decode_integrated_ppu_mode(observation.ppu_mode);
        integrated_ppu_ly_ = observation.ppu_ly;
        integrated_ppu_stat_ = observation.ppu_stat;

        const bool vblank_window_high = observation.ppu_vblank_req_window || observation.ppu_vblank_req;
        const bool stat_window_high = observation.ppu_stat_req_window || observation.ppu_stat_req;
        integrated_ppu_if_bits_ = 0;
        if (vblank_window_high && !integrated_ppu_vblank_window_high_) {
            integrated_ppu_if_bits_ |= VBLANK_IF_BIT;
        }
        if (stat_window_high && !integrated_ppu_stat_window_high_) {
            integrated_ppu_if_bits_ |= STAT_IF_BIT;
        }
        integrated_ppu_vblank_window_high_ = vblank_window_high;
        integrated_ppu_stat_window_high_ = stat_window_high;
    }

    uint8_t integrated_ppu_mmio_read_from_observation(const Observation& observation, uint16_t addr) const {
        if (addr == STAT_ADDR) {
            return observation.ppu_stat;
        }
        if (addr == LY_ADDR) {
            return observation.ppu_ly;
        }
        return ppu_mmio_read(addr);
    }

    uint8_t integrated_ppu_cpu_read_from_observation(const Observation& observation, uint16_t addr) const {
        if (!integrated_ppu_cpu_access_allows_from_observation(observation, addr)) {
            return 0xFF;
        }
        return raw_read(addr);
    }

    void write_video_direct(uint16_t addr, uint8_t value) {
        if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) {
            vram_[addr - VRAM_BASE] = value;
            return;
        }
        if (addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE) {
            oam_[addr - OAM_BASE] = value;
        }
    }

    void write(uint16_t addr, uint8_t value) {
        if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) {
            vram_[addr - VRAM_BASE] = value;
            return;
        }
        if (addr >= 0xC000 && addr <= 0xDFFF) {
            wram_[addr - 0xC000] = value;
            return;
        }
        if (addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE) {
            oam_[addr - OAM_BASE] = value;
            return;
        }
        if (addr == JOYP_ADDR) {
            joyp_select_ = static_cast<uint8_t>((value >> 4) & 0x3U);
            return;
        }
        if (addr == SB_ADDR) {
            serial_sb_ = value;
            return;
        }
        if (addr == SC_ADDR) {
            serial_sc_ = static_cast<uint8_t>(value & 0x83U);
            if ((serial_sc_ & 0x81U) == 0x81U) {
                serial_cycles_left_ = 8;
            }
            return;
        }
        if (addr == TIMA_ADDR) {
            tima_ = value;
            return;
        }
        if (addr == TMA_ADDR) {
            tma_ = value;
            return;
        }
        if (addr == TAC_ADDR) {
            tac_ = static_cast<uint8_t>(value & 0x7U);
            return;
        }
        if (addr == IF_ADDR) {
            if_reg_ = static_cast<uint8_t>(value & 0x1FU);
            return;
        }
        if (addr >= 0xFF80 && addr <= 0xFFFE) {
            hram_[addr - 0xFF80] = value;
            return;
        }
        if (addr == IE_ADDR) {
            ie_reg_ = static_cast<uint8_t>(value & 0x1FU);
            return;
        }
        apply_ppu_shadow_write(addr, value);
    }

    uint8_t next_if_set_bits(bool write_en, uint16_t write_addr, uint8_t write_data) const {
        const bool write_div = write_en && write_addr == DIV_ADDR;
        const bool write_tima = write_en && write_addr == TIMA_ADDR;
        const bool write_tma = write_en && write_addr == TMA_ADDR;
        const bool write_tac = write_en && write_addr == TAC_ADDR;

        const uint32_t effective_sys_counter = write_div ? 0 : sys_counter_;
        const uint8_t next_tma = write_tma ? write_data : tma_;
        const uint8_t next_tac = write_tac ? static_cast<uint8_t>(write_data & 0x7U) : tac_;
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

        const bool next_serial_irq = serial_cycles_left_ == 1 && (serial_sc_ & 0x81U) == 0x81U;
        return static_cast<uint8_t>((next_timer_irq ? TIMER_IF_BIT : 0) | (next_serial_irq ? SERIAL_IF_BIT : 0));
    }

    void advance_cycle(
        bool write_en,
        uint16_t write_addr,
        uint8_t write_data,
        uint8_t if_set_bits,
        bool irq_ack_valid,
        uint8_t irq_ack_bit
    ) {
        const bool write_div = write_en && write_addr == DIV_ADDR;
        const bool write_tima = write_en && write_addr == TIMA_ADDR;
        const bool write_tma = write_en && write_addr == TMA_ADDR;
        const bool write_tac = write_en && write_addr == TAC_ADDR;
        const bool write_if = write_en && write_addr == IF_ADDR;
        const bool write_ie = write_en && write_addr == IE_ADDR;

        const uint32_t effective_sys_counter = write_div ? 0 : sys_counter_;
        const uint8_t next_tma = write_tma ? write_data : tma_;
        const uint8_t next_tac = write_tac ? static_cast<uint8_t>(write_data & 0x7U) : tac_;
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
        if (serial_cycles_left_ > 0 && (serial_sc_ & 0x81U) == 0x81U) {
            --serial_cycles_left_;
            if (serial_cycles_left_ == 0) {
                serial_sb_ = 0xFF;
                serial_sc_ &= 0x7FU;
            }
        }
        sampled_timer_enabled_ = next_sampled_timer_enabled;
        sampled_timer_bit_ = next_sampled_timer_bit;
        overflow_delay_ = next_overflow_delay;
        sys_counter_ = write_div ? 4 : (sys_counter_ + 4);

        const uint8_t ack = ack_mask(irq_ack_valid, irq_ack_bit);
        ie_reg_ = static_cast<uint8_t>((write_ie ? write_data : ie_reg_) & 0x1FU);
        const uint8_t cpu_written_if = static_cast<uint8_t>((write_if ? write_data : if_reg_) & 0x1FU);
        if_reg_ = static_cast<uint8_t>(((cpu_written_if & ~ack) | if_set_bits) & 0x1FU);
    }

    uint8_t if_reg() const { return if_reg_; }
    uint8_t ie_reg() const { return ie_reg_; }
    uint8_t integrated_ppu_if_bits() const { return integrated_ppu_if_bits_; }
    uint8_t read(uint16_t addr) const { return raw_read(addr); }
    std::array<uint8_t, 11> ppu_debug_regs() const {
        return {lcdc_, integrated_ppu_stat_, scy_, scx_, integrated_ppu_ly_, lyc_, bgp_, obp0_, obp1_, wy_, wx_};
    }

  private:
    static PpuMode decode_integrated_ppu_mode(uint8_t mode_code) {
        switch (mode_code) {
            case 1:
                return PpuMode::OamScan;
            case 2:
                return PpuMode::PixelTransfer;
            case 3:
                return PpuMode::HBlank;
            case 4:
                return PpuMode::VBlank;
            default:
                return PpuMode::LcdOff;
        }
    }

    bool ppu_lcd_enabled() const {
        return (lcdc_ & 0x80U) != 0;
    }

    uint8_t joyp_visible() const {
        return static_cast<uint8_t>(0xC0U | ((joyp_select_ & 0x3U) << 4) | 0x0FU);
    }

    uint8_t ppu_mmio_read(uint16_t addr) const {
        switch (addr) {
            case LCDC_ADDR:
                return lcdc_;
            case STAT_ADDR:
                return integrated_ppu_stat_;
            case SCY_ADDR:
                return scy_;
            case SCX_ADDR:
                return scx_;
            case LY_ADDR:
                return integrated_ppu_ly_;
            case LYC_ADDR:
                return lyc_;
            case BGP_ADDR:
                return bgp_;
            case OBP0_ADDR:
                return obp0_;
            case OBP1_ADDR:
                return obp1_;
            case WY_ADDR:
                return wy_;
            case WX_ADDR:
                return wx_;
            default:
                return 0xFF;
        }
    }

    bool integrated_ppu_cpu_access_allows_from_observation(const Observation& observation, uint16_t addr) const {
        const PpuMode mode = decode_integrated_ppu_mode(observation.ppu_mode);
        if (ppu_lcd_enabled()) {
            if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE && mode == PpuMode::PixelTransfer) {
                return false;
            }
            if (addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE &&
                (mode == PpuMode::OamScan || mode == PpuMode::PixelTransfer)) {
                return false;
            }
        }
        return true;
    }

    uint8_t raw_read(uint16_t addr) const {
        if (addr < 0x8000) {
            return addr < rom_.size() ? rom_[addr] : 0xFF;
        }
        if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) {
            return vram_[addr - VRAM_BASE];
        }
        if (addr >= 0xC000 && addr <= 0xDFFF) {
            return wram_[addr - 0xC000];
        }
        if (addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE) {
            return oam_[addr - OAM_BASE];
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
            return static_cast<uint8_t>((sys_counter_ >> 8) & 0xFFU);
        }
        if (addr == TIMA_ADDR) {
            return tima_;
        }
        if (addr == TMA_ADDR) {
            return tma_;
        }
        if (addr == TAC_ADDR) {
            return static_cast<uint8_t>(tac_ & 0x7U);
        }
        if (addr >= LCDC_ADDR && addr <= WX_ADDR) {
            return ppu_mmio_read(addr);
        }
        if (addr == IF_ADDR) {
            return static_cast<uint8_t>(if_reg_ & 0x1FU);
        }
        if (addr >= 0xFF80 && addr <= 0xFFFE) {
            return hram_[addr - 0xFF80];
        }
        if (addr == IE_ADDR) {
            return static_cast<uint8_t>(ie_reg_ & 0x1FU);
        }
        return 0xFF;
    }

    void apply_ppu_shadow_write(uint16_t addr, uint8_t value) {
        switch (addr) {
            case LCDC_ADDR:
                lcdc_ = value;
                break;
            case SCY_ADDR:
                scy_ = value;
                break;
            case SCX_ADDR:
                scx_ = value;
                break;
            case LYC_ADDR:
                lyc_ = value;
                break;
            case BGP_ADDR:
                bgp_ = value;
                break;
            case OBP0_ADDR:
                obp0_ = value;
                break;
            case OBP1_ADDR:
                obp1_ = value;
                break;
            case WY_ADDR:
                wy_ = value;
                break;
            case WX_ADDR:
                wx_ = value;
                break;
            default:
                break;
        }
    }

    std::vector<uint8_t> rom_;
    std::array<uint8_t, 0x2000> wram_{};
    std::array<uint8_t, VRAM_SIZE> vram_{};
    std::array<uint8_t, OAM_SIZE> oam_{};
    std::array<uint8_t, 0x7F> hram_{};
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
    bool sampled_timer_enabled_ = false;
    bool sampled_timer_bit_ = false;
    uint8_t overflow_delay_ = 0;

    uint8_t lcdc_ = 0x91;
    uint8_t scy_ = 0x00;
    uint8_t scx_ = 0x00;
    uint8_t lyc_ = 0x00;
    uint8_t bgp_ = 0xFC;
    uint8_t obp0_ = 0xFF;
    uint8_t obp1_ = 0xFF;
    uint8_t wy_ = 0x00;
    uint8_t wx_ = 0x00;

    PpuMode integrated_ppu_mode_ = PpuMode::OamScan;
    uint8_t integrated_ppu_ly_ = 0;
    uint8_t integrated_ppu_stat_ = 0x82;
    uint8_t integrated_ppu_if_bits_ = 0;
    bool integrated_ppu_vblank_window_high_ = false;
    bool integrated_ppu_stat_window_high_ = false;
};

void eval_step(Vsoc_rom_top_verilator_wrapper& top) {
    top.eval();
}

void set_bus_inputs(
    Vsoc_rom_top_verilator_wrapper& top,
    uint8_t bus_read_data,
    uint8_t irq_pending,
    uint8_t if_reg,
    uint8_t ie_reg
) {
    top.bus_read_data_i = bus_read_data;
    top.irq_pending_i = irq_pending & 0x1F;
    top.if_reg_i = if_reg & 0x1F;
    top.ie_reg_i = ie_reg & 0x1F;
}

void set_idle_inputs(
    Vsoc_rom_top_verilator_wrapper& top,
    uint8_t bus_read_data,
    uint8_t if_reg,
    uint8_t ie_reg
) {
    top.stimulus_i = 0;
    set_bus_inputs(top, bus_read_data, 0, if_reg, ie_reg);
}

void clock_cycle(Vsoc_rom_top_verilator_wrapper& top) {
    top.clk_i = 0;
    eval_step(top);
    top.clk_i = 1;
    eval_step(top);
}

void reset_dut(Vsoc_rom_top_verilator_wrapper& top) {
    top.clk_i = 0;
    top.rst_i = 1;
    top.profiles_i = 0;
    top.stimulus_i = RESET_STIMULUS;
    set_bus_inputs(top, 0, 0, 0, 0);
    eval_step(top);
    clock_cycle(top);
    clock_cycle(top);
    top.rst_i = 0;
    eval_step(top);
    clock_cycle(top);
    top.stimulus_i = 0;
    set_bus_inputs(top, 0, 0, 0, 0);
    eval_step(top);
}

Observation choose_video_sample(
    const Observation& obs_t0,
    const Observation* mid_observation,
    uint8_t kind,
    uint16_t addr
) {
    if (obs_t0.ppu_ly == 0 || mid_observation == nullptr) {
        return obs_t0;
    }
    if (kind == BUS_REQ_READ) {
        if (addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE && obs_t0.ppu_mode == 0) {
            return *mid_observation;
        }
        if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE && obs_t0.ppu_mode == 1) {
            return *mid_observation;
        }
    }
    if (kind == BUS_REQ_WRITE) {
        if (addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE && obs_t0.ppu_mode == 1) {
            return *mid_observation;
        }
    }
    return obs_t0;
}

std::pair<bool, bool> video_write_allowed(
    const Observation& obs_t0,
    const Observation* mid_observation,
    uint16_t addr
) {
    if (!(addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) &&
        !(addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE)) {
        return {false, false};
    }
    const uint8_t mode_t0 = obs_t0.ppu_mode;
    const uint8_t ly_t0 = obs_t0.ppu_ly;
    const uint8_t mode_mid = mid_observation == nullptr ? mode_t0 : mid_observation->ppu_mode;
    if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) {
        return {true, mode_t0 != 2};
    }
    if (ly_t0 == 0) {
        return {true, mode_t0 == 0 || mode_t0 == 3};
    }
    if (mode_t0 == 0 || mode_t0 == 3) {
        return {true, true};
    }
    if (mode_t0 == 1) {
        return {true, mode_mid == 2};
    }
    return {true, false};
}

StepResult step_to_commit(Vsoc_rom_top_verilator_wrapper& top, BusModel& memory) {
    StepResult result;
    const Observation obs_t0 = observe(top);
    result.scanout_observations.push_back(obs_t0);
    memory.sync_integrated_ppu(obs_t0);

    auto pending_inputs = [&](const Observation& observation, const Observation* mid_observation) {
        result.video_sample_valid = false;
        result.write_allowed_valid = false;
        result.write_allowed = false;
        result.preview_kind = observation.preview_bus_req_kind;
        result.preview_addr = observation.preview_bus_req_addr;
        result.preview_data = observation.preview_bus_req_data;

        uint8_t bus_read_data = 0;
        if (result.preview_kind == BUS_REQ_READ) {
            if (result.preview_addr == IF_ADDR) {
                bus_read_data = static_cast<uint8_t>((memory.if_reg() | memory.integrated_ppu_if_bits()) & 0x1F);
            } else if (result.preview_addr >= LCDC_ADDR && result.preview_addr <= WX_ADDR) {
                bus_read_data = memory.integrated_ppu_mmio_read_from_observation(obs_t0, result.preview_addr);
            } else if ((result.preview_addr >= VRAM_BASE && result.preview_addr < VRAM_BASE + VRAM_SIZE) ||
                       (result.preview_addr >= OAM_BASE && result.preview_addr < OAM_BASE + OAM_SIZE)) {
                result.video_sample_valid = true;
                result.video_sample = choose_video_sample(obs_t0, mid_observation, result.preview_kind, result.preview_addr);
                bus_read_data =
                    memory.integrated_ppu_cpu_read_from_observation(result.video_sample, result.preview_addr);
            } else {
                bus_read_data = memory.read(result.preview_addr);
            }
        } else if ((result.preview_addr >= VRAM_BASE && result.preview_addr < VRAM_BASE + VRAM_SIZE) ||
                   (result.preview_addr >= OAM_BASE && result.preview_addr < OAM_BASE + OAM_SIZE)) {
            const auto write_allowed = video_write_allowed(obs_t0, mid_observation, result.preview_addr);
            result.write_allowed_valid = write_allowed.first;
            result.write_allowed = write_allowed.second;
            result.video_sample_valid = true;
            result.video_sample = choose_video_sample(obs_t0, mid_observation, result.preview_kind, result.preview_addr);
        }
        return bus_read_data;
    };

    const int skip_to_prefinal = obs_t0.m_ce ? 3 : std::max(0, 2 - static_cast<int>(obs_t0.t_index));
    uint8_t bus_read_data = pending_inputs(obs_t0, nullptr);
    Observation mid_observation{};
    bool have_mid = false;
    Observation prefinal_observation = obs_t0;

    if (skip_to_prefinal > 0) {
        set_idle_inputs(top, bus_read_data, memory.if_reg(), memory.ie_reg());
        clock_cycle(top);
        mid_observation = observe(top);
        have_mid = true;
        result.scanout_observations.push_back(mid_observation);
        if (skip_to_prefinal > 1) {
            for (int index = 0; index < skip_to_prefinal - 1; ++index) {
                clock_cycle(top);
            }
            prefinal_observation = observe(top);
            result.scanout_observations.push_back(prefinal_observation);
        } else {
            prefinal_observation = mid_observation;
        }
        bus_read_data = pending_inputs(prefinal_observation, have_mid ? &mid_observation : nullptr);
    }

    set_idle_inputs(top, bus_read_data, memory.if_reg(), memory.ie_reg());
    clock_cycle(top);
    result.post = observe(top);
    result.scanout_observations.push_back(result.post);
    memory.sync_integrated_ppu(result.post);
    return result;
}

void capture_shade_pixel(std::array<uint8_t, SCREEN_WIDTH * SCREEN_HEIGHT>& frame, const Observation& observation) {
    if (!observation.ppu_scanout_valid || observation.ppu_scanout_kind != 0) {
        return;
    }
    const uint8_t x = observation.ppu_scanout_x;
    const uint8_t y = observation.ppu_scanout_y;
    if (x < SCREEN_WIDTH && y < SCREEN_HEIGHT) {
        frame[y * SCREEN_WIDTH + x] = scanout_dmg_gray(observation.ppu_scanout_shade);
    }
}

void write_trace_line(std::ofstream& trace, uint64_t cycle, const Observation& observation) {
    if (!trace.is_open()) {
        return;
    }
    trace << "{"
          << "\"cycle\":" << cycle << ","
          << "\"pc\":" << observation.pc << ","
          << "\"ppu_mode\":" << static_cast<int>(observation.ppu_mode) << ","
          << "\"ppu_ly\":" << static_cast<int>(observation.ppu_ly) << ","
          << "\"ppu_stat\":" << static_cast<int>(observation.ppu_stat) << ","
          << "\"scanout_kind\":" << static_cast<int>(observation.ppu_scanout_kind) << ","
          << "\"scanout_valid\":" << (observation.ppu_scanout_valid ? "true" : "false")
          << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
    const Config cfg = parse_args(argc, argv);
    if (cfg.rom_path.empty() || cfg.frame_capture_path.empty()) {
        std::cerr << "missing required --rom or --frame-capture argument\n";
        return 2;
    }

    std::ifstream rom_stream(cfg.rom_path, std::ios::binary);
    if (!rom_stream) {
        std::cerr << "failed to open ROM: " << cfg.rom_path << "\n";
        return 2;
    }
    std::vector<uint8_t> rom_bytes((std::istreambuf_iterator<char>(rom_stream)), std::istreambuf_iterator<char>());

    Verilated::commandArgs(argc, argv);
    Vsoc_rom_top_verilator_wrapper top;
    BusModel memory(std::move(rom_bytes));
    std::array<uint8_t, SCREEN_WIDTH * SCREEN_HEIGHT> current_frame{};
    current_frame.fill(FRAME_SHADE_WHITE);
    std::array<uint8_t, SCREEN_WIDTH * SCREEN_HEIGHT> last_completed_frame{};
    last_completed_frame.fill(FRAME_SHADE_WHITE);
    bool have_last_completed_frame = false;
    uint64_t stable_completed_frames = 0;
    bool seen_frame_start = false;
    bool frame_start_active = false;
    uint64_t completed_mcycles = 0;
    uint64_t completed_frames = 0;
    Observation last_post{};

    std::ofstream trace;
    if (!cfg.trace_path.empty()) {
        trace.open(cfg.trace_path, std::ios::out | std::ios::trunc);
    }

    reset_dut(top);

    while (completed_mcycles < cfg.max_mcycles) {
        StepResult step = step_to_commit(top, memory);
        ++completed_mcycles;
        last_post = step.post;

        const bool write_en = step.post.bus_req_kind == BUS_REQ_WRITE;
        const uint16_t write_addr = write_en ? step.post.bus_req_addr : 0;
        const uint8_t write_data = write_en ? step.post.bus_req_data : 0;
        if (write_en && !(write_addr >= DIV_ADDR && write_addr <= TAC_ADDR) && write_addr != IF_ADDR && write_addr != IE_ADDR) {
            if (step.write_allowed_valid) {
                if (step.write_allowed) {
                    memory.write_video_direct(write_addr, write_data);
                }
            } else {
                memory.write(write_addr, write_data);
            }
        }
        memory.advance_cycle(
            write_en,
            write_addr,
            write_data,
            0,
            step.post.irq_ack_valid,
            step.post.irq_ack_bit
        );

        for (const Observation& observation : step.scanout_observations) {
            write_trace_line(trace, completed_mcycles, observation);
            if (!observation.ppu_scanout_valid) {
                continue;
            }
            if (observation.ppu_scanout_kind == 2) {
                if (!frame_start_active && seen_frame_start) {
                    ++completed_frames;
                    if (cfg.completed_frames != 0 && completed_frames >= cfg.completed_frames) {
                        const auto regs = memory.ppu_debug_regs();
                        std::ofstream raw_out(cfg.frame_capture_path, std::ios::binary | std::ios::trunc);
                        raw_out.write(reinterpret_cast<const char*>(current_frame.data()), current_frame.size());
                        raw_out.close();
                        std::cout << "dmg-acid2 frame captured"
                                  << " mcycles=" << completed_mcycles
                                  << " completed_frames=" << completed_frames
                                  << " last_pc=0x" << std::hex << step.post.pc << std::dec
                                  << " lcdc=0x" << std::hex << static_cast<int>(regs[0])
                                  << " stat=0x" << static_cast<int>(regs[1])
                                  << " scy=0x" << static_cast<int>(regs[2])
                                  << " scx=0x" << static_cast<int>(regs[3])
                                  << " ly=0x" << static_cast<int>(regs[4])
                                  << " lyc=0x" << static_cast<int>(regs[5])
                                  << " bgp=0x" << static_cast<int>(regs[6])
                                  << " obp0=0x" << static_cast<int>(regs[7])
                                  << " obp1=0x" << static_cast<int>(regs[8])
                                  << " wy=0x" << static_cast<int>(regs[9])
                                  << " wx=0x" << static_cast<int>(regs[10])
                                  << std::dec
                                  << "\n";
                        return 0;
                    }
                    if (have_last_completed_frame && current_frame == last_completed_frame) {
                        ++stable_completed_frames;
                    } else {
                        last_completed_frame = current_frame;
                        have_last_completed_frame = true;
                        stable_completed_frames = 1;
                    }
                    if (cfg.completed_frames == 0 && stable_completed_frames >= cfg.stable_frames) {
                        std::ofstream raw_out(cfg.frame_capture_path, std::ios::binary | std::ios::trunc);
                        raw_out.write(reinterpret_cast<const char*>(current_frame.data()), current_frame.size());
                        raw_out.close();
                        std::cout << "dmg-acid2 frame stabilized"
                                  << " mcycles=" << completed_mcycles
                                  << " stable_frames=" << stable_completed_frames
                                  << " last_pc=0x" << std::hex << step.post.pc << std::dec
                                  << "\n";
                        return 0;
                    }
                }
                if (!frame_start_active) {
                    current_frame.fill(FRAME_SHADE_WHITE);
                    seen_frame_start = true;
                }
                frame_start_active = true;
                continue;
            }
            frame_start_active = false;
            capture_shade_pixel(current_frame, observation);
        }

        if (cfg.progress_interval != 0 && (completed_mcycles % cfg.progress_interval) == 0) {
            std::cout << "progress mcycles=" << completed_mcycles
                      << " pc=0x" << std::hex << step.post.pc << std::dec
                      << " ppu_mode=" << static_cast<int>(step.post.ppu_mode)
                      << " ly=" << static_cast<int>(step.post.ppu_ly)
                      << "\n";
        }
    }

    std::cerr << "dmg-acid2 did not reach target frame capture within " << cfg.max_mcycles
              << " M-cycles"
              << " last_pc=0x" << std::hex << last_post.pc << std::dec << "\n";
    return 1;
}
