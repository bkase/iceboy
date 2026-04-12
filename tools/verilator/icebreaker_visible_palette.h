#ifndef ICEBOY_VISIBLE_PALETTE_H_
#define ICEBOY_VISIBLE_PALETTE_H_

#include <array>
#include <cstdint>

namespace iceboy {
namespace visible {

static constexpr std::array<uint16_t, 4> kRgb565Palette = {
    0xFFFFU,
    0xAD55U,
    0x52AAU,
    0x0000U,
};

static constexpr std::array<uint8_t, 4> kDmgShadeValues = {
    0xFFU,
    0xAAU,
    0x55U,
    0x00U,
};

}  // namespace visible
}  // namespace iceboy

#endif  // ICEBOY_VISIBLE_PALETTE_H_
