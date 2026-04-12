#include <algorithm>
#include <array>
#include <cstdint>
#include <cerrno>
#include <fstream>
#include <iostream>
#include <limits>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <stdexcept>
#include <string>
#include <vector>

#include "Vicebreaker_visible_top_verilator_wrapper.h"
#include "icebreaker_visible_palette.h"
#include "verilated.h"

namespace {

constexpr int kPanelWidth = 320;
constexpr int kPanelHeight = 240;
constexpr int kFrameWidth = 160;
constexpr int kFrameHeight = 144;
constexpr int kFramePixels = kFrameWidth * kFrameHeight;
constexpr int kWindowX0 = 80;
constexpr int kWindowY0 = 48;
constexpr int kWindowX1 = kWindowX0 + kFrameWidth - 1;
constexpr int kWindowY1 = kWindowY0 + kFrameHeight - 1;

struct Config {
    std::string expected_raw_path;
    std::string captured_raw_path;
    std::string captured_png_path;
    std::string reference_png_path;
    std::string diff_png_path;
    std::string joypad_schedule_path;
    uint64_t max_cycles = 80'000'000ULL;
    uint64_t progress_interval = 0ULL;
    uint64_t completed_frames = 1ULL;
    uint64_t reset_release_cycles = 70'000ULL;
};

struct Snapshot {
    bool ledr_n = false;
    bool ledg_n = false;
    bool lcd_sck = false;
    bool lcd_mosi = false;
    bool lcd_cs = true;
    bool lcd_dc = false;
    bool lcd_res = false;
    bool lcd_bl = false;
    bool debug_gpio0 = false;
    bool debug_gpio1 = false;
    bool dbg_pc0 = false;
    bool dbg_pc1 = false;
    bool dbg_pc2 = false;
    bool dbg_pc3 = false;
    bool dbg_mce = false;
    bool dbg_phase0 = false;
    bool dbg_phase1 = false;
    bool dbg_phase2 = false;
};

struct WindowBounds {
    int x0 = 0;
    int x1 = kPanelWidth - 1;
    int y0 = 0;
    int y1 = kPanelHeight - 1;
};

struct SpiDecoder {
    WindowBounds window;
    uint8_t current_command = 0;
    std::array<uint8_t, 4> params = {0, 0, 0, 0};
    int param_count = 0;
    bool ramwr_active = false;
    bool pixel_hi_pending = false;
    uint8_t pixel_hi = 0;
    int write_x = 0;
    int write_y = 0;
    uint32_t frame_pixels_written = 0;
    uint64_t completed_frames = 0;
    std::vector<uint16_t> panel = std::vector<uint16_t>(kPanelWidth * kPanelHeight, iceboy::visible::kRgb565Palette[0]);
};

Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int index = 1; index < argc; ++index) {
        const std::string arg(argv[index]);
        if (arg.rfind("--expected-raw=", 0) == 0) {
            cfg.expected_raw_path = arg.substr(sizeof("--expected-raw=") - 1);
        } else if (arg.rfind("--captured-raw=", 0) == 0) {
            cfg.captured_raw_path = arg.substr(sizeof("--captured-raw=") - 1);
        } else if (arg.rfind("--captured-png=", 0) == 0) {
            cfg.captured_png_path = arg.substr(sizeof("--captured-png=") - 1);
        } else if (arg.rfind("--reference-png=", 0) == 0) {
            cfg.reference_png_path = arg.substr(sizeof("--reference-png=") - 1);
        } else if (arg.rfind("--diff-png=", 0) == 0) {
            cfg.diff_png_path = arg.substr(sizeof("--diff-png=") - 1);
        } else if (arg.rfind("--joypad-schedule=", 0) == 0) {
            cfg.joypad_schedule_path = arg.substr(sizeof("--joypad-schedule=") - 1);
        } else if (arg.rfind("--max-cycles=", 0) == 0) {
            cfg.max_cycles = std::stoull(arg.substr(sizeof("--max-cycles=") - 1));
        } else if (arg.rfind("--progress-interval=", 0) == 0) {
            cfg.progress_interval = std::stoull(arg.substr(sizeof("--progress-interval=") - 1));
        } else if (arg.rfind("--completed-frames=", 0) == 0) {
            cfg.completed_frames = std::stoull(arg.substr(sizeof("--completed-frames=") - 1));
        } else if (arg.rfind("--reset-release-cycles=", 0) == 0) {
            cfg.reset_release_cycles = std::stoull(arg.substr(sizeof("--reset-release-cycles=") - 1));
        } else {
            throw std::runtime_error("unsupported argument: " + arg);
        }
    }
    if (cfg.expected_raw_path.empty()) {
        throw std::runtime_error("--expected-raw is required");
    }
    return cfg;
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

void ensure_parent_dir(const std::string& path) {
    if (path.empty()) {
        return;
    }
    const size_t slash = path.find_last_of('/');
    if (slash == std::string::npos) {
        return;
    }
    const std::string parent = path.substr(0, slash);
    if (parent.empty()) {
        return;
    }

    std::string current;
    if (!parent.empty() && parent[0] == '/') {
        current = "/";
    }

    size_t offset = current.empty() ? 0 : 1;
    while (offset <= parent.size()) {
        const size_t next = parent.find('/', offset);
        const std::string component = parent.substr(offset, next == std::string::npos ? std::string::npos : next - offset);
        if (!component.empty()) {
            if (!current.empty() && current.back() != '/') {
                current.push_back('/');
            }
            current += component;
            if (::mkdir(current.c_str(), 0755) != 0 && errno != EEXIST) {
                throw std::runtime_error("failed to create directory " + current + ": " + std::string(strerror(errno)));
            }
        }
        if (next == std::string::npos) {
            break;
        }
        offset = next + 1;
    }
}

void write_file(const std::string& path, const std::vector<uint8_t>& data) {
    ensure_parent_dir(path);
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("failed to write " + path);
    }
    stream.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()));
}

uint32_t crc32_update(uint32_t crc, uint8_t byte) {
    crc ^= static_cast<uint32_t>(byte);
    for (int bit = 0; bit < 8; ++bit) {
        const uint32_t mask = static_cast<uint32_t>(-(static_cast<int32_t>(crc & 1U)));
        crc = (crc >> 1) ^ (0xEDB88320U & mask);
    }
    return crc;
}

uint32_t crc32_bytes(const std::vector<uint8_t>& data) {
    uint32_t crc = 0xFFFFFFFFU;
    for (uint8_t byte : data) {
        crc = crc32_update(crc, byte);
    }
    return crc ^ 0xFFFFFFFFU;
}

uint32_t adler32_bytes(const std::vector<uint8_t>& data) {
    uint32_t s1 = 1U;
    uint32_t s2 = 0U;
    for (uint8_t byte : data) {
        s1 = (s1 + static_cast<uint32_t>(byte)) % 65521U;
        s2 = (s2 + s1) % 65521U;
    }
    return (s2 << 16) | s1;
}

void append_be32(std::vector<uint8_t>& out, uint32_t value) {
    out.push_back(static_cast<uint8_t>((value >> 24) & 0xFFU));
    out.push_back(static_cast<uint8_t>((value >> 16) & 0xFFU));
    out.push_back(static_cast<uint8_t>((value >> 8) & 0xFFU));
    out.push_back(static_cast<uint8_t>(value & 0xFFU));
}

void append_chunk(std::vector<uint8_t>& png, const char* tag, const std::vector<uint8_t>& payload) {
    append_be32(png, static_cast<uint32_t>(payload.size()));
    const size_t tag_offset = png.size();
    png.push_back(static_cast<uint8_t>(tag[0]));
    png.push_back(static_cast<uint8_t>(tag[1]));
    png.push_back(static_cast<uint8_t>(tag[2]));
    png.push_back(static_cast<uint8_t>(tag[3]));
    png.insert(png.end(), payload.begin(), payload.end());
    std::vector<uint8_t> crc_input;
    crc_input.reserve(4 + payload.size());
    crc_input.insert(crc_input.end(), png.begin() + static_cast<std::ptrdiff_t>(tag_offset), png.end());
    append_be32(png, crc32_bytes(crc_input));
}

std::vector<uint8_t> zlib_store(const std::vector<uint8_t>& raw) {
    std::vector<uint8_t> out;
    out.reserve(raw.size() + (raw.size() / 65535U + 1U) * 5U + 6U);
    out.push_back(0x78U);
    out.push_back(0x01U);

    size_t offset = 0;
    while (offset < raw.size()) {
        const size_t remaining = raw.size() - offset;
        const uint16_t block_len =
            static_cast<uint16_t>(std::min<size_t>(remaining, std::numeric_limits<uint16_t>::max()));
        const bool final_block = (offset + block_len) == raw.size();
        out.push_back(final_block ? 0x01U : 0x00U);
        out.push_back(static_cast<uint8_t>(block_len & 0xFFU));
        out.push_back(static_cast<uint8_t>((block_len >> 8) & 0xFFU));
        const uint16_t nlen = static_cast<uint16_t>(~block_len);
        out.push_back(static_cast<uint8_t>(nlen & 0xFFU));
        out.push_back(static_cast<uint8_t>((nlen >> 8) & 0xFFU));
        out.insert(out.end(), raw.begin() + static_cast<std::ptrdiff_t>(offset), raw.begin() + static_cast<std::ptrdiff_t>(offset + block_len));
        offset += block_len;
    }

    append_be32(out, adler32_bytes(raw));
    return out;
}

std::vector<uint8_t> encode_png_grayscale(const std::vector<uint8_t>& frame, int width, int height) {
    if (static_cast<int>(frame.size()) != width * height) {
        throw std::runtime_error("frame size mismatch while encoding PNG");
    }
    std::vector<uint8_t> rows;
    rows.reserve(frame.size() + static_cast<size_t>(height));
    for (int row = 0; row < height; ++row) {
        rows.push_back(0U);
        rows.insert(
            rows.end(),
            frame.begin() + static_cast<std::ptrdiff_t>(row * width),
            frame.begin() + static_cast<std::ptrdiff_t>((row + 1) * width)
        );
    }

    std::vector<uint8_t> png = {
        0x89U, 0x50U, 0x4EU, 0x47U, 0x0DU, 0x0AU, 0x1AU, 0x0AU,
    };

    std::vector<uint8_t> ihdr;
    ihdr.reserve(13);
    append_be32(ihdr, static_cast<uint32_t>(width));
    append_be32(ihdr, static_cast<uint32_t>(height));
    ihdr.push_back(8U);
    ihdr.push_back(0U);
    ihdr.push_back(0U);
    ihdr.push_back(0U);
    ihdr.push_back(0U);
    append_chunk(png, "IHDR", ihdr);
    append_chunk(png, "IDAT", zlib_store(rows));
    append_chunk(png, "IEND", {});
    return png;
}

Snapshot sample(const Vicebreaker_visible_top_verilator_wrapper& top) {
    Snapshot snap;
    snap.ledr_n = top.ledr_n_o;
    snap.ledg_n = top.ledg_n_o;
    snap.lcd_sck = top.lcd_sck_o;
    snap.lcd_mosi = top.lcd_mosi_o;
    snap.lcd_cs = top.lcd_cs_o;
    snap.lcd_dc = top.lcd_dc_o;
    snap.lcd_res = top.lcd_res_o;
    snap.lcd_bl = top.lcd_bl_o;
    snap.debug_gpio0 = top.debug_gpio0_o;
    snap.debug_gpio1 = top.debug_gpio1_o;
    snap.dbg_pc0 = top.dbg_pc0_o;
    snap.dbg_pc1 = top.dbg_pc1_o;
    snap.dbg_pc2 = top.dbg_pc2_o;
    snap.dbg_pc3 = top.dbg_pc3_o;
    snap.dbg_mce = top.dbg_mce_o;
    snap.dbg_phase0 = top.dbg_phase0_o;
    snap.dbg_phase1 = top.dbg_phase1_o;
    snap.dbg_phase2 = top.dbg_phase2_o;
    return snap;
}

void eval_step(Vicebreaker_visible_top_verilator_wrapper& top) {
    top.eval();
}

void clock_cycle(Vicebreaker_visible_top_verilator_wrapper& top) {
    top.clk_i = 0;
    eval_step(top);
    top.clk_i = 1;
    eval_step(top);
}

void reset_dut(Vicebreaker_visible_top_verilator_wrapper& top, uint64_t release_cycles) {
    top.clk_i = 0;
    top.btn_n_i = 0;
    top.joypad_buttons_i = 0;
    for (int index = 0; index < 8; ++index) {
        clock_cycle(top);
    }
    top.btn_n_i = 1;
    for (uint64_t cycle = 0; cycle < release_cycles; ++cycle) {
        clock_cycle(top);
    }
}

bool visible_window_active(const WindowBounds& window) {
    return window.x0 == kWindowX0 && window.x1 == kWindowX1 && window.y0 == kWindowY0 && window.y1 == kWindowY1;
}

void start_ramwr(SpiDecoder& decoder) {
    decoder.ramwr_active = true;
    decoder.pixel_hi_pending = false;
    decoder.frame_pixels_written = 0;
    decoder.write_x = decoder.window.x0;
    decoder.write_y = decoder.window.y0;
}

void advance_write_cursor(SpiDecoder& decoder) {
    if (decoder.write_x < decoder.window.x1) {
        ++decoder.write_x;
    } else {
        decoder.write_x = decoder.window.x0;
        if (decoder.write_y < decoder.window.y1) {
            ++decoder.write_y;
        }
    }
}

bool handle_spi_byte(SpiDecoder& decoder, bool dc, uint8_t byte) {
    if (!dc) {
        decoder.current_command = byte;
        decoder.param_count = 0;
        decoder.ramwr_active = false;
        decoder.pixel_hi_pending = false;
        if (byte == 0x2CU) {
            start_ramwr(decoder);
        }
        return false;
    }

    if (decoder.ramwr_active) {
        if (!decoder.pixel_hi_pending) {
            decoder.pixel_hi = byte;
            decoder.pixel_hi_pending = true;
            return false;
        }

        decoder.pixel_hi_pending = false;
        if (
            decoder.write_x >= 0 && decoder.write_x < kPanelWidth &&
            decoder.write_y >= 0 && decoder.write_y < kPanelHeight
        ) {
            decoder.panel[static_cast<size_t>(decoder.write_y) * kPanelWidth + decoder.write_x] =
                static_cast<uint16_t>((static_cast<uint16_t>(decoder.pixel_hi) << 8) | byte);
        }
        ++decoder.frame_pixels_written;
        const bool frame_complete =
            visible_window_active(decoder.window) &&
            decoder.frame_pixels_written == static_cast<uint32_t>(kFramePixels);
        advance_write_cursor(decoder);
        if (frame_complete) {
            ++decoder.completed_frames;
        }
        return frame_complete;
    }

    if ((decoder.current_command == 0x2AU || decoder.current_command == 0x2BU) && decoder.param_count < 4) {
        decoder.params[decoder.param_count++] = byte;
        if (decoder.param_count == 4) {
            const int start = (static_cast<int>(decoder.params[0]) << 8) | decoder.params[1];
            const int end = (static_cast<int>(decoder.params[2]) << 8) | decoder.params[3];
            if (decoder.current_command == 0x2AU) {
                decoder.window.x0 = start;
                decoder.window.x1 = end;
            } else {
                decoder.window.y0 = start;
                decoder.window.y1 = end;
            }
        }
    }
    return false;
}

std::vector<uint8_t> crop_visible_frame(const SpiDecoder& decoder) {
    std::vector<uint8_t> frame;
    frame.reserve(kFramePixels);
    for (int y = kWindowY0; y <= kWindowY1; ++y) {
        for (int x = kWindowX0; x <= kWindowX1; ++x) {
            const uint16_t pixel = decoder.panel[static_cast<size_t>(y) * kPanelWidth + x];
            uint32_t best_diff = std::numeric_limits<uint32_t>::max();
            size_t best_index = 0;
            for (size_t index = 0; index < iceboy::visible::kRgb565Palette.size(); ++index) {
                const uint16_t candidate = iceboy::visible::kRgb565Palette[index];
                const uint32_t diff = static_cast<uint32_t>(pixel > candidate ? pixel - candidate : candidate - pixel);
                if (diff < best_diff) {
                    best_diff = diff;
                    best_index = index;
                }
            }
            frame.push_back(iceboy::visible::kDmgShadeValues[best_index]);
        }
    }
    return frame;
}

std::vector<uint8_t> build_diff_frame(const std::vector<uint8_t>& actual, const std::vector<uint8_t>& expected) {
    std::vector<uint8_t> diff(actual.size(), 0U);
    for (size_t index = 0; index < actual.size(); ++index) {
        diff[index] = actual[index] == expected[index] ? 0x00U : 0xFFU;
    }
    return diff;
}

void write_optional_png(const std::string& path, const std::vector<uint8_t>& frame, int width, int height) {
    if (path.empty()) {
        return;
    }
    write_file(path, encode_png_grayscale(frame, width, height));
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    try {
        const Config cfg = parse_args(argc, argv);
        const std::vector<uint8_t> expected = read_exact_file(cfg.expected_raw_path, kFramePixels);
        const std::vector<uint8_t> joypad_schedule =
            cfg.joypad_schedule_path.empty() ? std::vector<uint8_t>() : load_joypad_schedule(cfg.joypad_schedule_path);

        Vicebreaker_visible_top_verilator_wrapper top;
        reset_dut(top, cfg.reset_release_cycles);
        top.joypad_buttons_i = joypad_schedule.empty() ? 0U : joypad_schedule[0];

        Snapshot prev = sample(top);
        uint8_t spi_byte = 0U;
        int spi_bit_count = 0;
        bool spi_dc = false;
        SpiDecoder decoder;
        bool saw_source_frame_start = false;
        uint64_t source_completed_frames = 0;
        bool compare_armed = false;

        for (uint64_t cycle = 0; cycle < cfg.max_cycles; ++cycle) {
            clock_cycle(top);
            const Snapshot current = sample(top);

            if (cfg.progress_interval != 0 && ((cycle + 1) % cfg.progress_interval) == 0) {
                std::cout << "progress cycle=" << (cycle + 1)
                          << " completed_frames=" << decoder.completed_frames
                          << " source_completed_frames=" << source_completed_frames
                          << " ledr_n=" << (current.ledr_n ? 1 : 0)
                          << " ledg_n=" << (current.ledg_n ? 1 : 0)
                          << " lcd_res=" << (current.lcd_res ? 1 : 0)
                          << " lcd_bl=" << (current.lcd_bl ? 1 : 0)
                          << " cs=" << (current.lcd_cs ? 1 : 0)
                          << " sck=" << (current.lcd_sck ? 1 : 0)
                          << " frame_start=" << (current.debug_gpio0 ? 1 : 0)
                          << " scanout_valid=" << (current.debug_gpio1 ? 1 : 0)
                          << " reader_active=" << (current.dbg_pc0 ? 1 : 0)
                          << " pixel_valid=" << (current.dbg_pc1 ? 1 : 0)
                          << " frame_active=" << (current.dbg_pc2 ? 1 : 0)
                          << " tx_active=" << (current.dbg_pc3 ? 1 : 0)
                          << " init_done=" << (current.dbg_mce ? 1 : 0)
                          << " pixel_advance=" << (current.dbg_phase0 ? 1 : 0)
                          << " cpu_halted=" << (current.dbg_phase1 ? 1 : 0)
                          << "\n";
            }

            const bool source_frame_start =
                (!prev.dbg_phase2 && current.dbg_phase2) ||
                (!prev.debug_gpio0 && current.debug_gpio0);
            if (source_frame_start) {
                if (saw_source_frame_start && !joypad_schedule.empty()) {
                    ++source_completed_frames;
                    const uint8_t next_buttons =
                        source_completed_frames < joypad_schedule.size()
                            ? joypad_schedule[static_cast<size_t>(source_completed_frames)]
                            : joypad_schedule.back();
                    top.joypad_buttons_i = next_buttons;
                }
                saw_source_frame_start = true;
            }

            if (current.lcd_cs) {
                spi_byte = 0U;
                spi_bit_count = 0;
            } else if (!prev.lcd_sck && current.lcd_sck) {
                if (spi_bit_count == 0) {
                    spi_dc = current.lcd_dc;
                }
                spi_byte = static_cast<uint8_t>(((spi_byte << 1) | (current.lcd_mosi ? 1U : 0U)) & 0xFFU);
                ++spi_bit_count;
                if (spi_bit_count == 8) {
                    const bool frame_complete = handle_spi_byte(decoder, spi_dc, spi_byte);
                    spi_byte = 0U;
                    spi_bit_count = 0;

                    if (frame_complete) {
                        const bool target_reached =
                            joypad_schedule.empty()
                                ? (decoder.completed_frames >= cfg.completed_frames)
                                : (saw_source_frame_start && (source_completed_frames + 1U) >= cfg.completed_frames);

                        if (!joypad_schedule.empty() && !compare_armed && target_reached) {
                            compare_armed = true;
                            prev = current;
                            continue;
                        }

                        if (target_reached || compare_armed) {
                            const std::vector<uint8_t> actual = crop_visible_frame(decoder);
                            int mismatches = 0;
                            int first_x = -1;
                            int first_y = -1;
                            uint8_t first_actual = 0U;
                            uint8_t first_expected = 0U;
                            for (int index = 0; index < kFramePixels; ++index) {
                                if (actual[static_cast<size_t>(index)] != expected[static_cast<size_t>(index)]) {
                                    ++mismatches;
                                    if (first_x < 0) {
                                        first_x = index % kFrameWidth;
                                        first_y = index / kFrameWidth;
                                        first_actual = actual[static_cast<size_t>(index)];
                                        first_expected = expected[static_cast<size_t>(index)];
                                    }
                                }
                            }

                            if (!cfg.captured_raw_path.empty()) {
                                write_file(cfg.captured_raw_path, actual);
                            }
                            write_optional_png(cfg.captured_png_path, actual, kFrameWidth, kFrameHeight);
                            write_optional_png(cfg.reference_png_path, expected, kFrameWidth, kFrameHeight);
                            if (!cfg.diff_png_path.empty()) {
                                write_file(cfg.diff_png_path, encode_png_grayscale(build_diff_frame(actual, expected), kFrameWidth, kFrameHeight));
                            }

                            if (mismatches != 0) {
                                std::cerr << "icebreaker_visible_top mismatch first-diff=("
                                          << first_x << ", " << first_y
                                          << ", expected=0x" << std::hex << static_cast<unsigned>(first_expected)
                                          << ", actual=0x" << static_cast<unsigned>(first_actual)
                                          << std::dec << ") mismatches=" << mismatches << "\n";
                                return 1;
                            }

                            std::cout << "matched " << decoder.completed_frames
                                      << " completed visible frames; final frame pixel-perfect\n";
                            return 0;
                        }
                    }
                }
            }

            prev = current;
        }

        std::cerr << "icebreaker_visible_top did not reach " << cfg.completed_frames
                  << " completed frames within max-cycles=" << cfg.max_cycles << "\n";
        return 2;
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << "\n";
        return 2;
    }
}
