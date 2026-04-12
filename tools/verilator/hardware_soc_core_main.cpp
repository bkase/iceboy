#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "Vhardware_soc_core_verilator_wrapper.h"
#include "verilated.h"

namespace {

constexpr int kScreenWidth = 160;
constexpr int kScreenHeight = 144;
constexpr int kFramePixels = kScreenWidth * kScreenHeight;

struct Config {
    std::string expected_raw_path;
    std::string frame_capture_path;
    std::string trace_path;
    std::string joypad_schedule_path;
    std::string rom_id = "bg_static";
    uint64_t max_cycles = 4'000'000ULL;
    uint64_t progress_interval = 0ULL;
    uint64_t completed_frames = 3ULL;
};

struct Observation {
    bool valid = false;
    uint8_t kind = 0;
    uint8_t x = 0;
    uint8_t y = 0;
    uint8_t shade = 0;
    uint8_t ly = 0;
    uint8_t mode = 0;
    bool rom_ready = false;
    bool m_ce = false;
    uint8_t t_index = 0;
    uint16_t pc = 0;
    uint8_t phase_bits = 0;
};

uint64_t extract_bits(const Vhardware_soc_core_verilator_wrapper& top, int lsb, int width) {
    uint64_t value = 0;
    for (int bit = 0; bit < width; ++bit) {
        value |= static_cast<uint64_t>((top.output___05F >> (lsb + bit)) & 1ULL) << bit;
    }
    return value;
}

Observation observe(const Vhardware_soc_core_verilator_wrapper& top) {
    Observation obs;
    obs.valid = extract_bits(top, 0, 1) != 0;
    obs.kind = static_cast<uint8_t>(extract_bits(top, 1, 2));
    obs.x = static_cast<uint8_t>(extract_bits(top, 3, 8));
    obs.y = static_cast<uint8_t>(extract_bits(top, 11, 8));
    obs.shade = static_cast<uint8_t>(extract_bits(top, 19, 2));
    obs.ly = static_cast<uint8_t>(extract_bits(top, 21, 8));
    obs.mode = static_cast<uint8_t>(extract_bits(top, 29, 3));
    obs.rom_ready = extract_bits(top, 32, 1) != 0;
    obs.m_ce = extract_bits(top, 33, 1) != 0;
    obs.t_index = static_cast<uint8_t>(extract_bits(top, 34, 2));
    obs.pc = static_cast<uint16_t>(extract_bits(top, 36, 16));
    obs.phase_bits = static_cast<uint8_t>(extract_bits(top, 52, 3));
    return obs;
}

Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int index = 1; index < argc; ++index) {
        const std::string arg(argv[index]);
        if (arg.rfind("--expected-raw=", 0) == 0) {
            cfg.expected_raw_path = arg.substr(sizeof("--expected-raw=") - 1);
        } else if (arg.rfind("--frame-capture=", 0) == 0) {
            cfg.frame_capture_path = arg.substr(sizeof("--frame-capture=") - 1);
        } else if (arg.rfind("--trace=", 0) == 0) {
            cfg.trace_path = arg.substr(sizeof("--trace=") - 1);
        } else if (arg.rfind("--joypad-schedule=", 0) == 0) {
            cfg.joypad_schedule_path = arg.substr(sizeof("--joypad-schedule=") - 1);
        } else if (arg.rfind("--rom-id=", 0) == 0) {
            cfg.rom_id = arg.substr(sizeof("--rom-id=") - 1);
        } else if (arg.rfind("--max-cycles=", 0) == 0) {
            cfg.max_cycles = std::stoull(arg.substr(sizeof("--max-cycles=") - 1));
        } else if (arg.rfind("--progress-interval=", 0) == 0) {
            cfg.progress_interval = std::stoull(arg.substr(sizeof("--progress-interval=") - 1));
        } else if (arg.rfind("--completed-frames=", 0) == 0) {
            cfg.completed_frames = std::stoull(arg.substr(sizeof("--completed-frames=") - 1));
        } else {
            throw std::runtime_error("unsupported argument: " + arg);
        }
    }
    if (cfg.expected_raw_path.empty()) {
        throw std::runtime_error("--expected-raw is required");
    }
    if (cfg.rom_id != "bg_static" && cfg.rom_id != "joypad_bg_smoke") {
        throw std::runtime_error("unsupported --rom-id: " + cfg.rom_id);
    }
    return cfg;
}

std::vector<uint8_t> load_joypad_schedule(const std::string& path) {
    std::ifstream schedule_stream(path);
    if (!schedule_stream) {
        throw std::runtime_error("failed to open joypad schedule: " + path);
    }
    std::vector<uint8_t> schedule;
    std::string token;
    while (schedule_stream >> token) {
        const unsigned long raw = std::stoul(token, nullptr, 0);
        if (raw > 0xFFUL) {
            throw std::runtime_error("joypad schedule entry exceeds 8 bits: " + token);
        }
        schedule.push_back(static_cast<uint8_t>(raw));
    }
    return schedule;
}

std::vector<uint8_t> read_exact_file(const std::string& path, size_t expected_size) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("failed to open " + path);
    }
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
    if (data.size() != expected_size) {
        throw std::runtime_error(
            "expected " + std::to_string(expected_size) + " bytes in " + path + ", got " + std::to_string(data.size())
        );
    }
    return data;
}

void write_file(const std::string& path, const std::vector<uint8_t>& data) {
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("failed to write " + path);
    }
    stream.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()));
}

uint8_t dmg_shade_value(uint8_t shade) {
    switch (shade & 0x3U) {
        case 0:
            return 0xFFU;
        case 1:
            return 0xAAU;
        case 2:
            return 0x55U;
        default:
            return 0x00U;
    }
}

void eval_step(Vhardware_soc_core_verilator_wrapper& top) {
    top.eval();
}

void clock_cycle(Vhardware_soc_core_verilator_wrapper& top) {
    top.clk_i = 0;
    eval_step(top);
    top.clk_i = 1;
    eval_step(top);
}

void reset_dut(Vhardware_soc_core_verilator_wrapper& top) {
    top.clk_i = 0;
    top.rst_i = 1;
    top.rom_select_i = 0;
    top.joypad_buttons_i = 0;
    for (int index = 0; index < 8; ++index) {
        clock_cycle(top);
    }
    top.rst_i = 0;
}

void maybe_trace(std::ofstream* trace, uint64_t cycle, const Observation& obs) {
    if (trace == nullptr || !obs.valid) {
        return;
    }
    (*trace) << "{\"cycle\":" << cycle
             << ",\"kind\":" << static_cast<unsigned>(obs.kind)
             << ",\"x\":" << static_cast<unsigned>(obs.x)
             << ",\"y\":" << static_cast<unsigned>(obs.y)
             << ",\"shade\":" << static_cast<unsigned>(obs.shade)
             << ",\"ly\":" << static_cast<unsigned>(obs.ly)
             << ",\"mode\":" << static_cast<unsigned>(obs.mode)
             << ",\"rom_ready\":" << (obs.rom_ready ? "true" : "false")
             << ",\"m_ce\":" << (obs.m_ce ? "true" : "false")
             << ",\"t_index\":" << static_cast<unsigned>(obs.t_index)
             << ",\"pc\":" << static_cast<unsigned>(obs.pc)
             << ",\"phase_bits\":" << static_cast<unsigned>(obs.phase_bits)
             << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    try {
        const Config cfg = parse_args(argc, argv);
        const std::vector<uint8_t> expected = read_exact_file(cfg.expected_raw_path, kFramePixels);
        const std::vector<uint8_t> joypad_schedule =
            cfg.joypad_schedule_path.empty() ? std::vector<uint8_t>() : load_joypad_schedule(cfg.joypad_schedule_path);
        std::ofstream trace_stream;
        std::ofstream* trace = nullptr;
        if (!cfg.trace_path.empty()) {
            trace_stream.open(cfg.trace_path, std::ios::out | std::ios::trunc);
            if (!trace_stream) {
                throw std::runtime_error("failed to open trace output: " + cfg.trace_path);
            }
            trace = &trace_stream;
        }

        Vhardware_soc_core_verilator_wrapper top;
        reset_dut(top);
        top.rom_select_i = cfg.rom_id == "joypad_bg_smoke" ? 1 : 0;
        top.joypad_buttons_i = joypad_schedule.empty() ? 0 : joypad_schedule[0];

        std::vector<uint8_t> current_frame(kFramePixels, 0xFFU);
        std::vector<uint8_t> completed_frame(kFramePixels, 0xFFU);
        bool saw_frame_start = false;
        uint64_t pixels_in_current_frame = 0;
        uint64_t completed_frames = 0;

        for (uint64_t cycle = 0; cycle < cfg.max_cycles; ++cycle) {
            clock_cycle(top);
            const Observation obs = observe(top);
            maybe_trace(trace, cycle, obs);

            if (cfg.progress_interval != 0 && ((cycle + 1) % cfg.progress_interval) == 0) {
                std::cout << "progress cycle=" << (cycle + 1)
                          << " completed_frames=" << completed_frames
                          << " pixels_in_frame=" << pixels_in_current_frame
                          << " ly=" << static_cast<unsigned>(obs.ly)
                          << " mode=" << static_cast<unsigned>(obs.mode)
                          << "\n";
            }

            if (!obs.valid) {
                continue;
            }

            if (obs.kind == 1U) {
                if (saw_frame_start && pixels_in_current_frame == static_cast<uint64_t>(kFramePixels)) {
                    completed_frame = current_frame;
                    ++completed_frames;
                    if (completed_frames >= cfg.completed_frames) {
                        if (!cfg.frame_capture_path.empty()) {
                            write_file(cfg.frame_capture_path, completed_frame);
                        }

                        int mismatches = 0;
                        int first_x = -1;
                        int first_y = -1;
                        uint8_t first_actual = 0;
                        uint8_t first_expected = 0;
                        for (int index = 0; index < kFramePixels; ++index) {
                            if (completed_frame[index] != expected[index]) {
                                ++mismatches;
                                if (first_x < 0) {
                                    first_x = index % kScreenWidth;
                                    first_y = index / kScreenWidth;
                                    first_actual = completed_frame[index];
                                    first_expected = expected[index];
                                }
                            }
                        }

                        if (mismatches != 0) {
                            std::cerr << "hardware_soc_core mismatch first-diff=("
                                      << first_x << ", " << first_y << ", expected=0x"
                                      << std::hex << static_cast<unsigned>(first_expected)
                                      << ", actual=0x" << static_cast<unsigned>(first_actual)
                                      << std::dec << ") mismatches=" << mismatches << "\n";
                            return 1;
                        }

                        std::cout << "matched " << completed_frames
                                  << " completed frames; final frame pixel-perfect\n";
                        return 0;
                    }
                }
                std::fill(current_frame.begin(), current_frame.end(), 0xFFU);
                pixels_in_current_frame = 0;
                if (saw_frame_start && !joypad_schedule.empty()) {
                    const uint8_t next_buttons =
                        completed_frames < joypad_schedule.size() ? joypad_schedule[completed_frames] : 0U;
                    top.joypad_buttons_i = next_buttons;
                }
                saw_frame_start = true;
                continue;
            }

            if (obs.kind == 2U && obs.x < kScreenWidth && obs.y < kScreenHeight) {
                current_frame[(static_cast<size_t>(obs.y) * kScreenWidth) + obs.x] = dmg_shade_value(obs.shade);
                ++pixels_in_current_frame;
            }
        }

        std::cerr << "hardware_soc_core did not reach " << cfg.completed_frames
                  << " completed frames within max-cycles=" << cfg.max_cycles << "\n";
        return 2;
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << "\n";
        return 2;
    }
}
