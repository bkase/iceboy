#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "Vsoc_rom_top_verilator_wrapper.h"
#include "Vsoc_rom_top_verilator_wrapper___024root.h"
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
constexpr uint16_t WRAM_BASE = 0xC000;
constexpr uint16_t WRAM_SIZE = 0x2000;
constexpr uint16_t HRAM_BASE = 0xFF80;
constexpr uint16_t HRAM_SIZE = 0x007F;
constexpr uint16_t CART_RAM_BASE = 0xA000;
constexpr uint16_t CART_RAM_SIZE = 0x2000;

constexpr uint8_t BUS_REQ_IDLE = 0;
constexpr uint8_t BUS_REQ_READ = 1;
constexpr uint8_t BUS_REQ_WRITE = 2;

constexpr uint8_t VBLANK_IF_BIT = 0x01;
constexpr uint8_t STAT_IF_BIT = 0x02;
constexpr uint8_t TIMER_IF_BIT = 0x04;
constexpr uint8_t SERIAL_IF_BIT = 0x08;
constexpr uint8_t JOYPAD_IF_BIT = 0x10;

constexpr uint64_t RESET_STIMULUS = 0x3;
constexpr uint8_t CPU_PHASE_FETCH = 0;
constexpr uint8_t CPU_PHASE_HALTED = 9;

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
    bool ppu_vblank_req = false;
    bool ppu_stat_req = false;
    uint8_t ppu_mode = 0;
    uint8_t ppu_ly = 0;
    uint8_t ppu_stat = 0;
    bool irq_ack_valid = false;
    uint8_t irq_ack_bit = 0;
    uint16_t pc = 0;
    uint8_t bus_req_kind = 0;
    uint16_t bus_req_addr = 0;
    uint8_t bus_req_data = 0;
    uint8_t t_index = 0;
    bool m_ce = false;
    uint8_t preview_bus_req_kind = 0;
    uint16_t preview_bus_req_addr = 0;
    uint8_t preview_bus_req_data = 0;
};

struct StepResult {
    Observation post;
    uint8_t preview_kind = 0;
    uint16_t preview_addr = 0;
    uint8_t supplied_bus_read_data = 0;
    bool write_allowed_valid = false;
    bool write_allowed = false;
    std::vector<Observation> scanout_observations;
};

struct Config {
    std::string rom_path;
    std::string restore_manifest_path;
    std::string script_schedule_path;
    std::string frames_raw_path;
    uint64_t max_mcycles = 11000000ULL;
    uint64_t target_frames = 600;
    uint64_t progress_interval = 0;
};

struct RestoreImage {
    int state_version = 0;
    std::string title;
    int cart_type = 0;
    int external_rom_count = 0;
    int external_ram_count = 0;
    uint8_t a = 0;
    uint8_t f = 0;
    uint8_t b = 0;
    uint8_t c = 0;
    uint8_t d = 0;
    uint8_t e = 0;
    uint8_t h = 0;
    uint8_t l = 0;
    uint16_t sp = 0;
    uint16_t pc = 0;
    uint8_t ime = 0;
    uint8_t halted = 0;
    uint8_t stopped = 0;
    uint8_t ie = 0;
    uint8_t if_reg = 0;
    uint8_t joyp_select = 0x3;
    uint8_t lcdc = 0x91;
    uint8_t stat = 0x82;
    uint8_t scy = 0;
    uint8_t scx = 0;
    uint8_t ly = 0;
    uint8_t lyc = 0;
    uint8_t bgp = 0xFC;
    uint8_t obp0 = 0xFF;
    uint8_t obp1 = 0xFF;
    uint8_t wy = 0;
    uint8_t wx = 0;
    uint8_t restart_lcdc = 0x91;
    uint8_t restart_scy = 0;
    uint8_t restart_scx = 0;
    uint8_t restart_wy = 0;
    uint8_t restart_wx = 0;
    uint8_t timer_div = 0;
    uint16_t timer_div_counter = 0;
    uint8_t timer_tima = 0;
    uint8_t timer_tma = 0;
    uint8_t timer_tac = 0;
    uint8_t serial_sb = 0xFF;
    uint8_t serial_sc = 0;
    uint8_t rombank_selected = 1;
    uint8_t rombank_selected_low = 0;
    uint8_t rambank_selected = 0;
    bool rambank_enabled = false;
    bool rtc_enabled = false;
    std::vector<uint8_t> vram;
    std::vector<uint8_t> oam;
    std::vector<uint8_t> wram;
    std::vector<uint8_t> hram;
    std::vector<uint8_t> cartram;
};

struct ScriptSpan {
    uint64_t start_frame = 0;
    uint64_t end_frame = 0;
    uint8_t mask = 0;
};

struct WalkScript {
    uint64_t fps = 60;
    uint64_t duration_frames = 600;
    std::vector<ScriptSpan> spans;

    uint8_t mask_for_frame(uint64_t frame_index) const {
        for (const ScriptSpan& span : spans) {
            if (frame_index >= span.start_frame && frame_index < span.end_frame) {
                return span.mask;
            }
        }
        return 0;
    }
};

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

std::vector<uint8_t> read_binary_file(const std::string& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("failed to open binary file: " + path);
    }
    return std::vector<uint8_t>((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
}

std::unordered_map<std::string, std::string> parse_key_value_file(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("failed to open manifest: " + path);
    }
    std::unordered_map<std::string, std::string> values;
    std::string line;
    while (std::getline(stream, line)) {
        if (line.empty()) {
            continue;
        }
        const size_t eq = line.find('=');
        if (eq == std::string::npos) {
            throw std::runtime_error("invalid manifest line: " + line);
        }
        values.emplace(line.substr(0, eq), line.substr(eq + 1));
    }
    return values;
}

int parse_int_value(const std::unordered_map<std::string, std::string>& values, const char* key) {
    auto it = values.find(key);
    if (it == values.end()) {
        throw std::runtime_error(std::string("missing manifest key: ") + key);
    }
    return std::stoi(it->second, nullptr, 0);
}

std::string parse_string_value(const std::unordered_map<std::string, std::string>& values, const char* key) {
    auto it = values.find(key);
    if (it == values.end()) {
        throw std::runtime_error(std::string("missing manifest key: ") + key);
    }
    return it->second;
}

RestoreImage load_restore_image(const std::string& manifest_path) {
    const auto values = parse_key_value_file(manifest_path);
    const std::string manifest_dir =
        manifest_path.substr(0, manifest_path.find_last_of("/\\") == std::string::npos ? 0 : manifest_path.find_last_of("/\\"));
    const auto join = [&](const std::string& name) -> std::string {
        if (name.empty() || (!manifest_dir.empty() && name.front() == '/')) {
            return name;
        }
        if (manifest_dir.empty()) {
            return name;
        }
        return manifest_dir + "/" + name;
    };

    RestoreImage image;
    image.state_version = parse_int_value(values, "state_version");
    image.title = parse_string_value(values, "title");
    image.cart_type = parse_int_value(values, "cart_type");
    image.external_rom_count = parse_int_value(values, "external_rom_count");
    image.external_ram_count = parse_int_value(values, "external_ram_count");
    image.a = static_cast<uint8_t>(parse_int_value(values, "a"));
    image.f = static_cast<uint8_t>(parse_int_value(values, "f"));
    image.b = static_cast<uint8_t>(parse_int_value(values, "b"));
    image.c = static_cast<uint8_t>(parse_int_value(values, "c"));
    image.d = static_cast<uint8_t>(parse_int_value(values, "d"));
    image.e = static_cast<uint8_t>(parse_int_value(values, "e"));
    image.h = static_cast<uint8_t>(parse_int_value(values, "h"));
    image.l = static_cast<uint8_t>(parse_int_value(values, "l"));
    image.sp = static_cast<uint16_t>(parse_int_value(values, "sp"));
    image.pc = static_cast<uint16_t>(parse_int_value(values, "pc"));
    image.ime = static_cast<uint8_t>(parse_int_value(values, "ime"));
    image.halted = static_cast<uint8_t>(parse_int_value(values, "halted"));
    image.stopped = static_cast<uint8_t>(parse_int_value(values, "stopped"));
    image.ie = static_cast<uint8_t>(parse_int_value(values, "ie"));
    image.if_reg = static_cast<uint8_t>(parse_int_value(values, "if"));
    image.joyp_select = static_cast<uint8_t>(parse_int_value(values, "joyp_select"));
    image.lcdc = static_cast<uint8_t>(parse_int_value(values, "lcdc"));
    image.stat = static_cast<uint8_t>(parse_int_value(values, "stat"));
    image.scy = static_cast<uint8_t>(parse_int_value(values, "scy"));
    image.scx = static_cast<uint8_t>(parse_int_value(values, "scx"));
    image.ly = static_cast<uint8_t>(parse_int_value(values, "ly"));
    image.lyc = static_cast<uint8_t>(parse_int_value(values, "lyc"));
    image.bgp = static_cast<uint8_t>(parse_int_value(values, "bgp"));
    image.obp0 = static_cast<uint8_t>(parse_int_value(values, "obp0"));
    image.obp1 = static_cast<uint8_t>(parse_int_value(values, "obp1"));
    image.wy = static_cast<uint8_t>(parse_int_value(values, "wy"));
    image.wx = static_cast<uint8_t>(parse_int_value(values, "wx"));
    image.restart_lcdc = static_cast<uint8_t>(parse_int_value(values, "restart_lcdc"));
    image.restart_scy = static_cast<uint8_t>(parse_int_value(values, "restart_scy"));
    image.restart_scx = static_cast<uint8_t>(parse_int_value(values, "restart_scx"));
    image.restart_wy = static_cast<uint8_t>(parse_int_value(values, "restart_wy"));
    image.restart_wx = static_cast<uint8_t>(parse_int_value(values, "restart_wx"));
    image.timer_div = static_cast<uint8_t>(parse_int_value(values, "timer_div"));
    image.timer_div_counter = static_cast<uint16_t>(parse_int_value(values, "timer_div_counter"));
    image.timer_tima = static_cast<uint8_t>(parse_int_value(values, "timer_tima"));
    image.timer_tma = static_cast<uint8_t>(parse_int_value(values, "timer_tma"));
    image.timer_tac = static_cast<uint8_t>(parse_int_value(values, "timer_tac"));
    image.serial_sb = static_cast<uint8_t>(parse_int_value(values, "serial_sb"));
    image.serial_sc = static_cast<uint8_t>(parse_int_value(values, "serial_sc"));
    image.rombank_selected = static_cast<uint8_t>(parse_int_value(values, "rombank_selected"));
    image.rombank_selected_low = static_cast<uint8_t>(parse_int_value(values, "rombank_selected_low"));
    image.rambank_selected = static_cast<uint8_t>(parse_int_value(values, "rambank_selected"));
    image.rambank_enabled = parse_int_value(values, "rambank_enabled") != 0;
    image.rtc_enabled = parse_int_value(values, "rtc_enabled") != 0;
    image.vram = read_binary_file(join(parse_string_value(values, "vram")));
    image.oam = read_binary_file(join(parse_string_value(values, "oam")));
    image.wram = read_binary_file(join(parse_string_value(values, "wram")));
    image.hram = read_binary_file(join(parse_string_value(values, "hram")));
    image.cartram = read_binary_file(join(parse_string_value(values, "cartram")));
    return image;
}

WalkScript load_walk_script(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("failed to open script schedule: " + path);
    }
    WalkScript script;
    std::string line;
    while (std::getline(stream, line)) {
        if (line.empty()) {
            continue;
        }
        if (line.rfind("fps=", 0) == 0) {
            script.fps = std::stoull(line.substr(4));
            continue;
        }
        if (line.rfind("duration_frames=", 0) == 0) {
            script.duration_frames = std::stoull(line.substr(16));
            continue;
        }
        std::istringstream iss(line);
        ScriptSpan span;
        int mask = 0;
        if (!(iss >> span.start_frame >> span.end_frame >> mask)) {
            throw std::runtime_error("invalid schedule line: " + line);
        }
        span.mask = static_cast<uint8_t>(mask & 0xFF);
        script.spans.push_back(span);
    }
    if (script.spans.empty()) {
        throw std::runtime_error("walk schedule contains no spans");
    }
    return script;
}

Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        const std::string arg(argv[i]);
        if (arg.rfind("--rom=", 0) == 0) {
            cfg.rom_path = arg.substr(sizeof("--rom=") - 1);
        } else if (arg.rfind("--restore-manifest=", 0) == 0) {
            cfg.restore_manifest_path = arg.substr(sizeof("--restore-manifest=") - 1);
        } else if (arg.rfind("--script-schedule=", 0) == 0) {
            cfg.script_schedule_path = arg.substr(sizeof("--script-schedule=") - 1);
        } else if (arg.rfind("--frames-raw=", 0) == 0) {
            cfg.frames_raw_path = arg.substr(sizeof("--frames-raw=") - 1);
        } else if (arg.rfind("--max-mcycles=", 0) == 0) {
            cfg.max_mcycles = std::stoull(arg.substr(sizeof("--max-mcycles=") - 1));
        } else if (arg.rfind("--target-frames=", 0) == 0) {
            cfg.target_frames = std::stoull(arg.substr(sizeof("--target-frames=") - 1));
        } else if (arg.rfind("--progress-interval=", 0) == 0) {
            cfg.progress_interval = std::stoull(arg.substr(sizeof("--progress-interval=") - 1));
        } else {
            throw std::runtime_error("unsupported argument: " + arg);
        }
    }
    if (cfg.rom_path.empty() || cfg.restore_manifest_path.empty() || cfg.script_schedule_path.empty() || cfg.frames_raw_path.empty()) {
        throw std::runtime_error("missing required runner arguments");
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
    obs.ppu_vblank_req = extract_bits(159, 1) != 0;
    obs.ppu_stat_req = extract_bits(158, 1) != 0;
    obs.ppu_mode = static_cast<uint8_t>(extract_bits(155, 3));
    obs.ppu_ly = static_cast<uint8_t>(extract_bits(147, 8));
    obs.ppu_stat = static_cast<uint8_t>(extract_bits(139, 8));
    obs.irq_ack_valid = extract_bits(130, 1) != 0;
    obs.irq_ack_bit = static_cast<uint8_t>(extract_bits(127, 3));
    obs.pc = static_cast<uint16_t>(extract_bits(111, 16));
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

template <std::size_t N>
void clear_wide(VlWide<N>& value) {
    for (std::size_t index = 0; index < N; ++index) {
        value[index] = 0;
    }
}

template <std::size_t N>
void set_wide_bits(VlWide<N>& value, int lsb, int width, uint64_t payload) {
    for (int bit = 0; bit < width; ++bit) {
        const int absolute = lsb + bit;
        const std::size_t word_index = static_cast<std::size_t>(absolute / 32);
        const uint32_t mask = 1U << (absolute % 32);
        if (((payload >> bit) & 1ULL) != 0) {
            value[word_index] |= mask;
        } else {
            value[word_index] &= ~mask;
        }
    }
}

void apply_restore_visible_ppu_regs(VlWide<36>& state_reg, const RestoreImage& image) {
    // Packed PpuState layout in generated Verilog is {visible, status, sampled, render},
    // so PpuVisibleState lives in the high 84 bits, not the low 84 bits.
    // Within visible, the layout is {regs, ly}, and within regs it is
    // {lcdc, stat_sel, scy, scx, lyc, wy, wx, bgp, obp0, obp1}.
    constexpr int LY_LSB = 1064;
    constexpr int OBP1_LSB = 1072;
    constexpr int OBP0_LSB = 1080;
    constexpr int BGP_LSB = 1088;
    constexpr int WX_LSB = 1096;
    constexpr int WY_LSB = 1104;
    constexpr int LYC_LSB = 1112;
    constexpr int SCX_LSB = 1120;
    constexpr int SCY_LSB = 1128;
    constexpr int STAT_SEL_LSB = 1136;
    constexpr int LCDC_LSB = 1140;

    // PyBoy v9 does not restore the per-scanline LCD restart parameters on load.
    // For savestate playback we want the live MMIO viewport PyBoy exposes after load.
    set_wide_bits(state_reg, LY_LSB, 8, 0);
    set_wide_bits(state_reg, OBP1_LSB, 8, image.obp1);
    set_wide_bits(state_reg, OBP0_LSB, 8, image.obp0);
    set_wide_bits(state_reg, BGP_LSB, 8, image.bgp);
    set_wide_bits(state_reg, WX_LSB, 8, image.wx);
    set_wide_bits(state_reg, WY_LSB, 8, image.wy);
    set_wide_bits(state_reg, LYC_LSB, 8, image.lyc);
    set_wide_bits(state_reg, SCX_LSB, 8, image.scx);
    set_wide_bits(state_reg, SCY_LSB, 8, image.scy);
    set_wide_bits(state_reg, STAT_SEL_LSB, 4, static_cast<uint64_t>((image.stat >> 3) & 0x0FU));
    set_wide_bits(state_reg, LCDC_LSB, 8, image.lcdc);
}

class BusModel {
  public:
    explicit BusModel(std::vector<uint8_t> rom_bytes)
        : rom_(std::move(rom_bytes)) {
        external_rom_count_ = std::max<std::size_t>(1, rom_.size() / 0x4000);
    }

    void seed_restore(const RestoreImage& image) {
        std::copy_n(image.vram.begin(), std::min<std::size_t>(image.vram.size(), vram_.size()), vram_.begin());
        std::copy_n(image.oam.begin(), std::min<std::size_t>(image.oam.size(), oam_.size()), oam_.begin());
        std::copy_n(image.wram.begin(), std::min<std::size_t>(image.wram.size(), wram_.size()), wram_.begin());
        std::copy_n(image.hram.begin(), std::min<std::size_t>(image.hram.size(), hram_.size()), hram_.begin());
        cart_ram_.assign(image.cartram.begin(), image.cartram.end());
        external_ram_count_ = image.external_ram_count;
        ie_reg_ = static_cast<uint8_t>(image.ie & 0x1FU);
        if_reg_ = static_cast<uint8_t>(image.if_reg & 0x1FU);
        joyp_select_ = static_cast<uint8_t>(image.joyp_select & 0x3U);
        lcdc_ = image.lcdc;
        scy_ = image.scy;
        scx_ = image.scx;
        lyc_ = image.lyc;
        bgp_ = image.bgp;
        obp0_ = image.obp0;
        obp1_ = image.obp1;
        wy_ = image.wy;
        wx_ = image.wx;
        integrated_ppu_ly_ = image.ly;
        integrated_ppu_stat_ = image.stat;
        sys_counter_ = (static_cast<uint32_t>(image.timer_div) << 8) | image.timer_div_counter;
        tima_ = image.timer_tima;
        tma_ = image.timer_tma;
        tac_ = static_cast<uint8_t>(image.timer_tac & 0x7U);
        sampled_timer_enabled_ = tac_enabled(tac_);
        sampled_timer_bit_ = timer_bit(sys_counter_, tac_);
        serial_sb_ = image.serial_sb;
        serial_sc_ = image.serial_sc;
        rombank_selected_ = image.rombank_selected == 0 ? 1 : image.rombank_selected;
        rombank_selected_low_ = image.rombank_selected_low;
        rambank_selected_ = image.rambank_selected;
        rambank_enabled_ = image.rambank_enabled;
        rtc_enabled_ = image.rtc_enabled;
        prev_buttons_ = current_buttons_;
    }

    void set_buttons(uint8_t mask) {
        current_buttons_ = static_cast<uint8_t>(mask & 0xFFU);
    }

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

    void clear_integrated_ppu_if_bits() {
        integrated_ppu_if_bits_ = 0;
    }

    uint8_t integrated_ppu_if_bits() const {
        return integrated_ppu_if_bits_;
    }

    uint8_t irq_pending() const {
        return static_cast<uint8_t>(if_reg_ & ie_reg_ & 0x1FU);
    }

    uint8_t if_reg() const { return if_reg_; }
    uint8_t ie_reg() const { return ie_reg_; }

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
        if (addr < 0x8000) {
            write_mbc3(addr, value);
            return;
        }
        if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) {
            vram_[addr - VRAM_BASE] = value;
            return;
        }
        if (addr >= CART_RAM_BASE && addr < CART_RAM_BASE + CART_RAM_SIZE) {
            write_cart_ram(addr, value);
            return;
        }
        if (addr >= WRAM_BASE && addr < WRAM_BASE + WRAM_SIZE) {
            wram_[addr - WRAM_BASE] = value;
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
        if (addr == TIMA_ADDR || addr == TMA_ADDR || addr == TAC_ADDR || addr == IF_ADDR || addr == IE_ADDR) {
            return;
        }
        if (addr >= HRAM_BASE && addr <= 0xFFFE) {
            hram_[addr - HRAM_BASE] = value;
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
        const uint8_t fresh_pressed = static_cast<uint8_t>(current_buttons_ & ~prev_buttons_);
        const bool next_joypad_irq = fresh_pressed != 0;

        return static_cast<uint8_t>(
            (next_timer_irq ? TIMER_IF_BIT : 0) |
            (next_serial_irq ? SERIAL_IF_BIT : 0) |
            (next_joypad_irq ? JOYPAD_IF_BIT : 0)
        );
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
        prev_buttons_ = current_buttons_;

        const uint8_t ack = ack_mask(irq_ack_valid, irq_ack_bit);
        ie_reg_ = static_cast<uint8_t>((write_ie ? write_data : ie_reg_) & 0x1FU);
        const uint8_t cpu_written_if = static_cast<uint8_t>((write_if ? write_data : if_reg_) & 0x1FU);
        if_reg_ = static_cast<uint8_t>(((cpu_written_if & ~ack) | if_set_bits) & 0x1FU);
    }

    uint8_t read(uint16_t addr) const { return raw_read(addr); }

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

    uint8_t action_pressed_nibble() const {
        return static_cast<uint8_t>(((current_buttons_ >> 7) & 0x1U) << 3 |
                                    ((current_buttons_ >> 6) & 0x1U) << 2 |
                                    ((current_buttons_ >> 5) & 0x1U) << 1 |
                                    ((current_buttons_ >> 4) & 0x1U));
    }

    uint8_t dpad_pressed_nibble() const {
        return static_cast<uint8_t>(((current_buttons_ >> 3) & 0x1U) << 3 |
                                    ((current_buttons_ >> 2) & 0x1U) << 2 |
                                    ((current_buttons_ >> 1) & 0x1U) << 1 |
                                    ((current_buttons_ >> 0) & 0x1U));
    }

    uint8_t selected_pressed_nibble() const {
        // joyp_select_ stores FF00 bits 5:4 right-shifted by 4. Bit 0 is P14
        // (d-pad select) and bit 1 is P15 (action select). We previously
        // swapped these and made scripted movement invisible to the game.
        const bool dpad_selected = (joyp_select_ & 0x1U) == 0;
        const bool action_selected = (joyp_select_ & 0x2U) == 0;
        uint8_t pressed = 0;
        if (action_selected) {
            pressed |= action_pressed_nibble();
        }
        if (dpad_selected) {
            pressed |= dpad_pressed_nibble();
        }
        return static_cast<uint8_t>(pressed & 0x0FU);
    }

    uint8_t joyp_visible() const {
        const uint8_t low_nibble = static_cast<uint8_t>(0x0FU & ~selected_pressed_nibble());
        return static_cast<uint8_t>(0xC0U | ((joyp_select_ & 0x3U) << 4) | low_nibble);
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

    uint8_t read_cart_ram(uint16_t addr) const {
        if (!rambank_enabled_) {
            return 0xFF;
        }
        if (rtc_enabled_ && rambank_selected_ >= 0x08 && rambank_selected_ <= 0x0C) {
            return 0xFF;
        }
        const std::size_t bank = external_ram_count_ == 0 ? 0 : (rambank_selected_ % external_ram_count_);
        const std::size_t offset = bank * CART_RAM_SIZE + (addr - CART_RAM_BASE);
        return offset < cart_ram_.size() ? cart_ram_[offset] : 0xFF;
    }

    void write_cart_ram(uint16_t addr, uint8_t value) {
        if (!rambank_enabled_) {
            return;
        }
        if (rtc_enabled_ && rambank_selected_ >= 0x08 && rambank_selected_ <= 0x0C) {
            return;
        }
        const std::size_t bank = external_ram_count_ == 0 ? 0 : (rambank_selected_ % external_ram_count_);
        const std::size_t offset = bank * CART_RAM_SIZE + (addr - CART_RAM_BASE);
        if (offset < cart_ram_.size()) {
            cart_ram_[offset] = value;
        }
    }

    void write_mbc3(uint16_t addr, uint8_t value) {
        if (addr < 0x2000) {
            rambank_enabled_ = (value & 0x0FU) == 0x0AU;
            return;
        }
        if (addr < 0x4000) {
            value &= 0x7FU;
            if (value == 0) {
                value = 1;
            }
            rombank_selected_ = static_cast<uint8_t>(value % std::max<std::size_t>(1, external_rom_count_));
            return;
        }
        if (addr < 0x6000) {
            if (value >= 0x08 && value <= 0x0C) {
                rambank_selected_ = value;
            } else {
                rambank_selected_ = external_ram_count_ == 0 ? 0 : static_cast<uint8_t>(value % external_ram_count_);
            }
            return;
        }
        if (addr < 0x8000) {
            return;
        }
    }

    uint8_t raw_read(uint16_t addr) const {
        if (addr < 0x4000) {
            return addr < rom_.size() ? rom_[addr] : 0xFF;
        }
        if (addr < 0x8000) {
            const std::size_t bank = rombank_selected_ == 0 ? 1 : rombank_selected_;
            const std::size_t offset = bank * 0x4000 + (addr - 0x4000);
            return offset < rom_.size() ? rom_[offset] : 0xFF;
        }
        if (addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) {
            return vram_[addr - VRAM_BASE];
        }
        if (addr >= CART_RAM_BASE && addr < CART_RAM_BASE + CART_RAM_SIZE) {
            return read_cart_ram(addr);
        }
        if (addr >= WRAM_BASE && addr < WRAM_BASE + WRAM_SIZE) {
            return wram_[addr - WRAM_BASE];
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
        if (addr >= HRAM_BASE && addr <= 0xFFFE) {
            return hram_[addr - HRAM_BASE];
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
    std::vector<uint8_t> cart_ram_;
    std::array<uint8_t, WRAM_SIZE> wram_{};
    std::array<uint8_t, VRAM_SIZE> vram_{};
    std::array<uint8_t, OAM_SIZE> oam_{};
    std::array<uint8_t, HRAM_SIZE> hram_{};
    std::size_t external_rom_count_ = 1;
    std::size_t external_ram_count_ = 0;

    uint8_t ie_reg_ = 0;
    uint8_t if_reg_ = 0;
    uint8_t joyp_select_ = 0x3;
    uint8_t current_buttons_ = 0;
    uint8_t prev_buttons_ = 0;
    uint32_t sys_counter_ = 0;
    uint8_t tima_ = 0;
    uint8_t tma_ = 0;
    uint8_t tac_ = 0;
    uint8_t serial_sb_ = 0xFF;
    uint8_t serial_sc_ = 0;
    uint8_t serial_cycles_left_ = 0;
    bool sampled_timer_enabled_ = false;
    bool sampled_timer_bit_ = false;
    uint8_t overflow_delay_ = 0;

    uint8_t lcdc_ = 0x91;
    uint8_t scy_ = 0;
    uint8_t scx_ = 0;
    uint8_t lyc_ = 0;
    uint8_t bgp_ = 0xFC;
    uint8_t obp0_ = 0xFF;
    uint8_t obp1_ = 0xFF;
    uint8_t wy_ = 0;
    uint8_t wx_ = 0;

    uint8_t rombank_selected_ = 1;
    uint8_t rombank_selected_low_ = 0;
    uint8_t rambank_selected_ = 0;
    bool rambank_enabled_ = false;
    bool rtc_enabled_ = false;

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
    uint8_t irq_pending,
    uint8_t if_reg,
    uint8_t ie_reg
) {
    top.stimulus_i = 0;
    set_bus_inputs(top, bus_read_data, irq_pending, if_reg, ie_reg);
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

Observation choose_video_sample(const Observation& obs_t0, const Observation* mid_observation, uint8_t kind, uint16_t addr) {
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

std::pair<bool, bool> video_write_allowed(const Observation& obs_t0, const Observation* mid_observation, uint16_t addr) {
    if (!(addr >= VRAM_BASE && addr < VRAM_BASE + VRAM_SIZE) && !(addr >= OAM_BASE && addr < OAM_BASE + OAM_SIZE)) {
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
        result.write_allowed_valid = false;
        result.write_allowed = false;
        result.preview_kind = observation.preview_bus_req_kind;
        result.preview_addr = observation.preview_bus_req_addr;

        uint8_t bus_read_data = 0;
        if (result.preview_kind == BUS_REQ_READ) {
            if (result.preview_addr == IF_ADDR) {
                bus_read_data = static_cast<uint8_t>((memory.if_reg() | memory.integrated_ppu_if_bits()) & 0x1F);
            } else if (result.preview_addr >= LCDC_ADDR && result.preview_addr <= WX_ADDR) {
                bus_read_data = memory.integrated_ppu_mmio_read_from_observation(observation, result.preview_addr);
            } else if ((result.preview_addr >= VRAM_BASE && result.preview_addr < VRAM_BASE + VRAM_SIZE) ||
                       (result.preview_addr >= OAM_BASE && result.preview_addr < OAM_BASE + OAM_SIZE)) {
                const Observation video_sample =
                    choose_video_sample(obs_t0, mid_observation, result.preview_kind, result.preview_addr);
                bus_read_data = memory.integrated_ppu_cpu_read_from_observation(video_sample, result.preview_addr);
            } else {
                bus_read_data = memory.read(result.preview_addr);
            }
        } else if ((result.preview_addr >= VRAM_BASE && result.preview_addr < VRAM_BASE + VRAM_SIZE) ||
                   (result.preview_addr >= OAM_BASE && result.preview_addr < OAM_BASE + OAM_SIZE)) {
            const auto write_allowed = video_write_allowed(obs_t0, mid_observation, result.preview_addr);
            result.write_allowed_valid = write_allowed.first;
            result.write_allowed = write_allowed.second;
        }
        result.supplied_bus_read_data = bus_read_data;
        return bus_read_data;
    };

    const int skip_to_prefinal = obs_t0.m_ce ? 3 : std::max(0, 2 - static_cast<int>(obs_t0.t_index));
    uint8_t bus_read_data = pending_inputs(obs_t0, nullptr);
    const bool preview_targets_video =
        (result.preview_addr >= VRAM_BASE && result.preview_addr < VRAM_BASE + VRAM_SIZE) ||
        (result.preview_addr >= OAM_BASE && result.preview_addr < OAM_BASE + OAM_SIZE);
    Observation mid_observation{};
    bool have_mid = false;
    Observation prefinal_observation = obs_t0;

    if (skip_to_prefinal > 0) {
        set_idle_inputs(top, bus_read_data, memory.irq_pending(), memory.if_reg(), memory.ie_reg());
        for (int index = 0; index < skip_to_prefinal; ++index) {
            clock_cycle(top);
            const Observation subcycle_observation = observe(top);
            result.scanout_observations.push_back(subcycle_observation);
            if (index == 0) {
                mid_observation = subcycle_observation;
                have_mid = true;
            }
            if (index == skip_to_prefinal - 1) {
                prefinal_observation = subcycle_observation;
            }
        }
        if (preview_targets_video) {
            bus_read_data = pending_inputs(prefinal_observation, have_mid ? &mid_observation : nullptr);
        }
    }

    set_idle_inputs(top, bus_read_data, memory.irq_pending(), memory.if_reg(), memory.ie_reg());
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

void apply_restore_to_dut(Vsoc_rom_top_verilator_wrapper& top, const RestoreImage& image) {
    auto* root = top.rootp;
    for (std::size_t index = 0; index < std::min<std::size_t>(image.vram.size(), VRAM_SIZE); ++index) {
        root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__vram_mem[index] = image.vram[index];
    }
    for (std::size_t index = 0; index < std::min<std::size_t>(image.oam.size(), OAM_SIZE); ++index) {
        root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__oam_mem[index] = image.oam[index];
    }
    for (std::size_t index = 0; index < std::min<std::size_t>(image.wram.size(), WRAM_SIZE); ++index) {
        root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__wram_shadow[index] = image.wram[index];
    }
    for (std::size_t index = 0; index < std::min<std::size_t>(image.hram.size(), HRAM_SIZE); ++index) {
        root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__hram_shadow[index] = image.hram[index];
    }
    apply_restore_visible_ppu_regs(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__ppu_core_0__DOT__state_reg, image);
    clear_wide(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state);
    clear_wide(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__micro_state);
    set_wide_bits(
        root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state,
        0,
        2,
        image.halted ? 1U : 0U
    );
    set_wide_bits(
        root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state,
        2,
        2,
        image.ime ? 2U : 0U
    );
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 4, 16, image.pc);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 20, 16, image.sp);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 36, 8, image.l);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 44, 8, image.h);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 52, 8, image.e);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 60, 8, image.d);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 68, 8, image.c);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 76, 8, image.b);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 84, 8, image.f & 0xF0U);
    set_wide_bits(root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__arch_state, 92, 8, image.a);
    // CpuMicroState is reset to Fetch in hardware. Savestate replay must also restore the
    // control phase; otherwise a halted save resumes with the right registers but the wrong
    // execution pipeline.
    set_wide_bits(
        root->soc_rom_top_verilator_wrapper__DOT__impl__DOT__cpu_core_0__DOT__micro_state,
        194,
        4,
        image.halted ? CPU_PHASE_HALTED : CPU_PHASE_FETCH
    );
    top.eval();
}

int run_main(int argc, char** argv) {
    try {
        const Config cfg = parse_args(argc, argv);
        const RestoreImage restore = load_restore_image(cfg.restore_manifest_path);
        const WalkScript script = load_walk_script(cfg.script_schedule_path);
        std::ifstream rom_stream(cfg.rom_path, std::ios::binary);
        if (!rom_stream) {
            throw std::runtime_error("failed to open ROM: " + cfg.rom_path);
        }
        std::vector<uint8_t> rom_bytes((std::istreambuf_iterator<char>(rom_stream)), std::istreambuf_iterator<char>());

        Verilated::commandArgs(argc, argv);
        Vsoc_rom_top_verilator_wrapper top;
        BusModel memory(std::move(rom_bytes));
        memory.seed_restore(restore);
        memory.set_buttons(script.mask_for_frame(0));

        std::array<uint8_t, SCREEN_WIDTH * SCREEN_HEIGHT> current_frame{};
        current_frame.fill(FRAME_SHADE_WHITE);
        bool seen_frame_start = false;
        bool frame_start_active = false;
        uint64_t completed_mcycles = 0;
        uint64_t completed_frames = 0;
        Observation last_post{};

        std::ofstream frames_raw(cfg.frames_raw_path, std::ios::binary | std::ios::trunc);
        if (!frames_raw) {
            throw std::runtime_error("failed to open frame stream for writing: " + cfg.frames_raw_path);
        }

        reset_dut(top);
        apply_restore_to_dut(top, restore);
        top.stimulus_i = 1;
        set_bus_inputs(top, 0, memory.irq_pending(), memory.if_reg(), memory.ie_reg());
        eval_step(top);

        uint64_t bootstrap_mcycles = 0;
        while (bootstrap_mcycles < 262144) {
            StepResult bootstrap = step_to_commit(top, memory);
            ++bootstrap_mcycles;
            last_post = bootstrap.post;
            for (const Observation& observation : bootstrap.scanout_observations) {
                if (observation.ppu_ly == restore.ly && observation.ppu_mode == 4) {
                    bootstrap_mcycles = 262144;
                    break;
                }
            }
        }
        top.stimulus_i = 0;
        set_idle_inputs(top, 0, memory.irq_pending(), memory.if_reg(), memory.ie_reg());
        eval_step(top);

        while (completed_mcycles < cfg.max_mcycles && completed_frames < cfg.target_frames) {
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

            const uint8_t if_set_bits = static_cast<uint8_t>(memory.next_if_set_bits(write_en, write_addr, write_data) |
                                                             memory.integrated_ppu_if_bits());
            memory.advance_cycle(write_en, write_addr, write_data, if_set_bits, step.post.irq_ack_valid, step.post.irq_ack_bit);
            memory.clear_integrated_ppu_if_bits();

            for (const Observation& observation : step.scanout_observations) {
                if (!observation.ppu_scanout_valid) {
                    continue;
                }
                if (observation.ppu_scanout_kind == 2) {
                    if (!frame_start_active && seen_frame_start) {
                        frames_raw.write(reinterpret_cast<const char*>(current_frame.data()), current_frame.size());
                        ++completed_frames;
                        memory.set_buttons(script.mask_for_frame(completed_frames));
                        if (completed_frames >= cfg.target_frames) {
                            break;
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
                          << " frames=" << completed_frames
                          << " pc=0x" << std::hex << step.post.pc << std::dec
                          << " ly=" << static_cast<int>(step.post.ppu_ly)
                          << " mode=" << static_cast<int>(step.post.ppu_mode)
                          << "\n";
            }
        }

        frames_raw.close();

        std::cout << "pokered playback complete"
                  << " mcycles=" << completed_mcycles
                  << " frames=" << completed_frames
                  << " last_pc=0x" << std::hex << last_post.pc << std::dec
                  << " state_version=" << restore.state_version
                  << " title=\"" << restore.title << "\""
                  << " cart_type=0x" << std::hex << restore.cart_type
                  << " rombank=0x" << static_cast<int>(restore.rombank_selected)
                  << " rambank=0x" << static_cast<int>(restore.rambank_selected)
                  << std::dec
                  << " sp=0x" << std::hex << restore.sp
                  << " pc=0x" << restore.pc
                  << std::dec
                  << "\n";

        if (completed_frames < cfg.target_frames) {
            std::cerr << "playback stopped before target frames: completed=" << completed_frames
                      << " target=" << cfg.target_frames
                      << " max_mcycles=" << cfg.max_mcycles << "\n";
            return 1;
        }
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << "\n";
        return 2;
    }
}

}  // namespace

int main(int argc, char** argv) {
    return run_main(argc, argv);
}
