#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "Vicebreaker_alu_loop_top_verilator_wrapper.h"
#include "verilated.h"

namespace {

constexpr uint8_t BUS_REQ_IDLE = 0;
constexpr uint8_t BUS_REQ_READ = 1;

struct ExpectedCheckpoint {
    uint64_t seq = 0;
    std::string label;
    uint16_t pc = 0;
    uint8_t a = 0;
    uint8_t f = 0;
    uint8_t b = 0;
    uint8_t c = 0;
    uint8_t d = 0;
    uint8_t e = 0;
    uint8_t h = 0;
    uint8_t l = 0;
    uint16_t sp = 0;
    uint8_t ime_state = 0;
    uint8_t halt_state = 0;
};

struct Observation {
    uint64_t commit_seq = 0;
    uint16_t pc = 0;
    uint16_t sp = 0;
    uint8_t a = 0;
    uint8_t f = 0;
    uint8_t b = 0;
    uint8_t c = 0;
    uint8_t d = 0;
    uint8_t e = 0;
    uint8_t h = 0;
    uint8_t l = 0;
    uint8_t ime_state = 0;
    uint8_t halt_state = 0;
    uint8_t bus_req_kind = 0;
    uint16_t bus_req_addr = 0;
    uint8_t bus_req_data = 0;
    uint8_t preview_bus_req_kind = 0;
    uint16_t preview_bus_req_addr = 0;
    uint8_t preview_bus_req_data = 0;
    bool rst = false;
    bool dbg_pc0 = false;
    bool dbg_pc1 = false;
    bool dbg_pc2 = false;
    bool dbg_pc3 = false;
    bool dbg_mce = false;
    bool dbg_phase0 = false;
    bool dbg_phase1 = false;
    bool dbg_phase2 = false;
    bool ledr_n = false;
    bool ledg_n = false;
};

struct Config {
    std::string expected_trace_path;
    std::string trace_path;
    uint64_t max_mcycles = 300000ULL;
    uint64_t progress_interval = 0ULL;
    uint64_t reset_release_cycles = 60000ULL;
};

uint64_t extract_bits(const Vicebreaker_alu_loop_top_verilator_wrapper& top, int lsb, int width) {
    uint64_t value = 0;
    for (int bit = 0; bit < width; ++bit) {
        const int absolute = lsb + bit;
        const uint32_t word = top.output___05F[absolute / 32];
        const uint32_t one = (word >> (absolute % 32)) & 0x1U;
        value |= static_cast<uint64_t>(one) << bit;
    }
    return value;
}

Observation observe(const Vicebreaker_alu_loop_top_verilator_wrapper& top) {
    Observation obs;
    obs.commit_seq = extract_bits(top, 0, 64);
    obs.pc = static_cast<uint16_t>(extract_bits(top, 64, 16));
    obs.sp = static_cast<uint16_t>(extract_bits(top, 80, 16));
    obs.a = static_cast<uint8_t>(extract_bits(top, 96, 8));
    obs.f = static_cast<uint8_t>(extract_bits(top, 104, 8));
    obs.b = static_cast<uint8_t>(extract_bits(top, 112, 8));
    obs.c = static_cast<uint8_t>(extract_bits(top, 120, 8));
    obs.d = static_cast<uint8_t>(extract_bits(top, 128, 8));
    obs.e = static_cast<uint8_t>(extract_bits(top, 136, 8));
    obs.h = static_cast<uint8_t>(extract_bits(top, 144, 8));
    obs.l = static_cast<uint8_t>(extract_bits(top, 152, 8));
    obs.ime_state = static_cast<uint8_t>(extract_bits(top, 160, 2));
    obs.halt_state = static_cast<uint8_t>(extract_bits(top, 162, 2));
    obs.bus_req_kind = static_cast<uint8_t>(extract_bits(top, 164, 2));
    obs.bus_req_addr = static_cast<uint16_t>(extract_bits(top, 166, 16));
    obs.bus_req_data = static_cast<uint8_t>(extract_bits(top, 182, 8));
    obs.preview_bus_req_kind = static_cast<uint8_t>(extract_bits(top, 190, 2));
    obs.preview_bus_req_addr = static_cast<uint16_t>(extract_bits(top, 192, 16));
    obs.preview_bus_req_data = static_cast<uint8_t>(extract_bits(top, 208, 8));
    obs.rst = extract_bits(top, 216, 1) != 0;
    obs.dbg_pc0 = extract_bits(top, 217, 1) != 0;
    obs.dbg_pc1 = extract_bits(top, 218, 1) != 0;
    obs.dbg_pc2 = extract_bits(top, 219, 1) != 0;
    obs.dbg_pc3 = extract_bits(top, 220, 1) != 0;
    obs.dbg_mce = extract_bits(top, 221, 1) != 0;
    obs.dbg_phase0 = extract_bits(top, 222, 1) != 0;
    obs.dbg_phase1 = extract_bits(top, 223, 1) != 0;
    obs.dbg_phase2 = extract_bits(top, 224, 1) != 0;
    obs.ledr_n = extract_bits(top, 225, 1) != 0;
    obs.ledg_n = extract_bits(top, 226, 1) != 0;
    return obs;
}

Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int index = 1; index < argc; ++index) {
        const std::string arg(argv[index]);
        if (arg.rfind("--expected-trace=", 0) == 0) {
            cfg.expected_trace_path = arg.substr(sizeof("--expected-trace=") - 1);
        } else if (arg.rfind("--trace=", 0) == 0) {
            cfg.trace_path = arg.substr(sizeof("--trace=") - 1);
        } else if (arg.rfind("--max-mcycles=", 0) == 0) {
            cfg.max_mcycles = std::stoull(arg.substr(sizeof("--max-mcycles=") - 1));
        } else if (arg.rfind("--progress-interval=", 0) == 0) {
            cfg.progress_interval = std::stoull(arg.substr(sizeof("--progress-interval=") - 1));
        } else if (arg.rfind("--reset-release-cycles=", 0) == 0) {
            cfg.reset_release_cycles = std::stoull(arg.substr(sizeof("--reset-release-cycles=") - 1));
        } else {
            throw std::runtime_error("unsupported argument: " + arg);
        }
    }
    if (cfg.expected_trace_path.empty()) {
        throw std::runtime_error("--expected-trace is required");
    }
    return cfg;
}

uint16_t parse_u16_hex(const std::string& text) {
    return static_cast<uint16_t>(std::stoul(text, nullptr, 0));
}

uint8_t parse_u8_hex(const std::string& text) {
    return static_cast<uint8_t>(std::stoul(text, nullptr, 0));
}

std::vector<ExpectedCheckpoint> load_expected_trace(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("failed to open expected trace: " + path);
    }
    std::vector<ExpectedCheckpoint> checkpoints;
    std::string line;
    while (std::getline(stream, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        std::stringstream parser(line);
        std::string field;
        ExpectedCheckpoint checkpoint;
        std::getline(parser, field, '\t');
        checkpoint.seq = std::stoull(field);
        std::getline(parser, checkpoint.label, '\t');
        std::getline(parser, field, '\t');
        checkpoint.pc = parse_u16_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.a = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.f = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.b = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.c = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.d = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.e = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.h = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.l = parse_u8_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.sp = parse_u16_hex(field);
        std::getline(parser, field, '\t');
        checkpoint.ime_state = static_cast<uint8_t>(std::stoul(field, nullptr, 0));
        std::getline(parser, field, '\t');
        checkpoint.halt_state = static_cast<uint8_t>(std::stoul(field, nullptr, 0));
        checkpoints.push_back(checkpoint);
    }
    if (checkpoints.empty()) {
        throw std::runtime_error("expected trace is empty: " + path);
    }
    return checkpoints;
}

void eval_step(Vicebreaker_alu_loop_top_verilator_wrapper& top) {
    top.eval();
}

void set_inputs(
    Vicebreaker_alu_loop_top_verilator_wrapper& top,
    bool btn_n,
    bool btn_d_up = false,
    bool btn_d_down = false,
    bool btn_d_left = false,
    bool btn_d_right = false,
    bool dip_a = false,
    bool dip_b = false,
    bool dip_start = false,
    bool dip_select = false
) {
    top.BTN_N = btn_n;
    top.BTN_D_UP = btn_d_up;
    top.BTN_D_DOWN = btn_d_down;
    top.BTN_D_LEFT = btn_d_left;
    top.BTN_D_RIGHT = btn_d_right;
    top.DIP_A = dip_a;
    top.DIP_B = dip_b;
    top.DIP_START = dip_start;
    top.DIP_SELECT = dip_select;
}

void clock_cycle(Vicebreaker_alu_loop_top_verilator_wrapper& top) {
    top.CLK = 0;
    eval_step(top);
    top.CLK = 1;
    eval_step(top);
}

void reset_dut(Vicebreaker_alu_loop_top_verilator_wrapper& top, uint64_t release_cycles) {
    top.CLK = 0;
    set_inputs(top, false);
    eval_step(top);
    for (int index = 0; index < 4; ++index) {
        clock_cycle(top);
    }
    set_inputs(top, true);
    eval_step(top);
    for (uint64_t index = 0; index < release_cycles; ++index) {
        const Observation obs = observe(top);
        if (obs.commit_seq != 0) {
            return;
        }
        clock_cycle(top);
    }
    throw std::runtime_error("board top did not begin committing before reset timeout");
}

uint8_t debug_pc_nibble(const Observation& obs) {
    return static_cast<uint8_t>(
        (static_cast<uint8_t>(obs.dbg_pc3) << 3)
        | (static_cast<uint8_t>(obs.dbg_pc2) << 2)
        | (static_cast<uint8_t>(obs.dbg_pc1) << 1)
        | static_cast<uint8_t>(obs.dbg_pc0)
    );
}

uint8_t debug_phase_bits(const Observation& obs) {
    return static_cast<uint8_t>(
        (static_cast<uint8_t>(obs.dbg_phase2) << 2)
        | (static_cast<uint8_t>(obs.dbg_phase1) << 1)
        | static_cast<uint8_t>(obs.dbg_phase0)
    );
}

void emit_trace_line(
    std::ofstream& trace,
    uint64_t mcycles,
    const Observation& obs,
    const std::string& label
) {
    trace
        << "{"
        << "\"mcycle\":" << mcycles
        << ",\"commit_seq\":" << obs.commit_seq
        << ",\"pc\":\"0x" << std::hex << obs.pc
        << "\",\"sp\":\"0x" << obs.sp
        << "\",\"a\":\"0x" << static_cast<unsigned>(obs.a)
        << "\",\"f\":\"0x" << static_cast<unsigned>(obs.f)
        << "\",\"b\":\"0x" << static_cast<unsigned>(obs.b)
        << "\",\"c\":\"0x" << static_cast<unsigned>(obs.c)
        << "\",\"d\":\"0x" << static_cast<unsigned>(obs.d)
        << "\",\"e\":\"0x" << static_cast<unsigned>(obs.e)
        << "\",\"h\":\"0x" << static_cast<unsigned>(obs.h)
        << "\",\"l\":\"0x" << static_cast<unsigned>(obs.l)
        << "\",\"ime_state\":" << std::dec << static_cast<unsigned>(obs.ime_state)
        << ",\"halt_state\":" << static_cast<unsigned>(obs.halt_state)
        << ",\"bus_req_kind\":" << static_cast<unsigned>(obs.bus_req_kind)
        << ",\"bus_req_addr\":\"0x" << std::hex << obs.bus_req_addr
        << "\",\"bus_req_data\":\"0x" << static_cast<unsigned>(obs.bus_req_data)
        << "\",\"preview_bus_req_kind\":" << std::dec << static_cast<unsigned>(obs.preview_bus_req_kind)
        << ",\"preview_bus_req_addr\":\"0x" << std::hex << obs.preview_bus_req_addr
        << "\",\"preview_bus_req_data\":\"0x" << static_cast<unsigned>(obs.preview_bus_req_data)
        << "\",\"dbg_pc_nibble\":\"0x" << static_cast<unsigned>(debug_pc_nibble(obs))
        << "\",\"dbg_phase\":\"0x" << static_cast<unsigned>(debug_phase_bits(obs))
        << "\",\"le_dr_n\":" << std::dec << (obs.ledr_n ? 1 : 0)
        << ",\"le_dg_n\":" << (obs.ledg_n ? 1 : 0);
    if (!label.empty()) {
        trace << ",\"label\":\"" << label << "\"";
    }
    trace << "}\n";
}

bool compare_checkpoint(
    const Observation& obs,
    const ExpectedCheckpoint& expected,
    std::ostream& errors
) {
    bool matched = true;
    auto diff_u16 = [&](const char* name, uint16_t actual, uint16_t exp) {
        if (actual == exp) {
            return;
        }
        matched = false;
        errors << "  " << name << ": expected=0x" << std::hex << exp << " actual=0x" << actual << std::dec << "\n";
    };
    auto diff_u8 = [&](const char* name, uint8_t actual, uint8_t exp) {
        if (actual == exp) {
            return;
        }
        matched = false;
        errors << "  " << name << ": expected=0x" << std::hex << static_cast<unsigned>(exp)
               << " actual=0x" << static_cast<unsigned>(actual) << std::dec << "\n";
    };

    diff_u16("pc", obs.pc, expected.pc);
    diff_u16("sp", obs.sp, expected.sp);
    diff_u8("a", obs.a, expected.a);
    diff_u8("f", obs.f, expected.f);
    diff_u8("b", obs.b, expected.b);
    diff_u8("c", obs.c, expected.c);
    diff_u8("d", obs.d, expected.d);
    diff_u8("e", obs.e, expected.e);
    diff_u8("h", obs.h, expected.h);
    diff_u8("l", obs.l, expected.l);
    diff_u8("ime_state", obs.ime_state, expected.ime_state);
    diff_u8("halt_state", obs.halt_state, expected.halt_state);
    return matched;
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    try {
        const Config cfg = parse_args(argc, argv);
        const std::vector<ExpectedCheckpoint> expected = load_expected_trace(cfg.expected_trace_path);

        Vicebreaker_alu_loop_top_verilator_wrapper top;
        top.CLK = 0;
        set_inputs(top, true);
        eval_step(top);
        reset_dut(top, cfg.reset_release_cycles);

        std::ofstream trace;
        if (!cfg.trace_path.empty()) {
            trace.open(cfg.trace_path, std::ios::out | std::ios::trunc);
            if (!trace) {
                throw std::runtime_error("failed to open trace output: " + cfg.trace_path);
            }
        }

        size_t expected_index = 0;
        for (uint64_t mcycles = 0; mcycles < cfg.max_mcycles;) {
            const Observation obs = observe(top);
            std::string matched_label;
            if (obs.dbg_mce) {
                ++mcycles;
                if (expected_index < expected.size()
                    && obs.bus_req_kind == BUS_REQ_READ
                    && obs.bus_req_addr == expected[expected_index].pc) {
                    matched_label = expected[expected_index].label;
                    std::ostringstream mismatch;
                    if (!compare_checkpoint(obs, expected[expected_index], mismatch)) {
                        std::cerr
                            << "icebreaker_alu_loop mismatch at checkpoint " << expected_index
                            << " label=" << expected[expected_index].label
                            << " commit_seq=" << obs.commit_seq
                            << " mcycles=" << mcycles << "\n"
                            << mismatch.str();
                        return 1;
                    }
                    ++expected_index;
                    if (expected_index == expected.size()) {
                        if (trace.is_open()) {
                            emit_trace_line(trace, mcycles, obs, matched_label);
                        }
                        std::cout
                            << "matched " << expected.size()
                            << " checkpoints in " << mcycles
                            << " mcycles\n";
                        return 0;
                    }
                }
                if (trace.is_open()) {
                    emit_trace_line(trace, mcycles, obs, matched_label);
                }
                if (cfg.progress_interval != 0 && (mcycles % cfg.progress_interval) == 0) {
                    std::cout
                        << "progress mcycles=" << mcycles
                        << " checkpoints=" << expected_index << "/" << expected.size()
                        << " pc=0x" << std::hex << obs.pc
                        << " bus_req_addr=0x" << obs.bus_req_addr
                        << std::dec << "\n";
                }
            }
            clock_cycle(top);
        }

        std::cerr
            << "timeout after " << cfg.max_mcycles
            << " mcycles with checkpoints=" << expected_index
            << "/" << expected.size() << "\n";
        return 2;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
