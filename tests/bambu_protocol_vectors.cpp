#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>
#include "../src/crc_bus.h"

static bool check_crc16(const std::vector<uint8_t>& frame)
{
    if (frame.size() < 4) return false;
    const uint16_t crc = bus_crc16(frame.data(), (uint32_t)frame.size() - 2u);
    return frame[frame.size() - 2u] == (uint8_t)(crc & 0xFFu) &&
           frame[frame.size() - 1u] == (uint8_t)(crc >> 8);
}

static uint8_t classify_short_cmd(const std::vector<uint8_t>& frame)
{
    if (frame.size() < 6u || frame[0] != 0x3D || frame[1] != 0xC5) return 0xFFu;
    if (frame[3] != bus_crc8(frame.data(), 3u)) return 0xFFu;
    if (!check_crc16(frame)) return 0xFFu;
    return frame[4];
}

struct LongHeader
{
    uint16_t package_number;
    uint16_t package_length;
    uint16_t target_address;
    uint16_t source_address;
    uint16_t type;
    uint16_t payload_len;
};

static bool parse_long(const std::vector<uint8_t>& frame, LongHeader& out)
{
    if (frame.size() < 15u || frame[0] != 0x3D) return false;
    if (!(frame[1] == 0x04 || frame[1] == 0x05 || frame[1] == 0x00)) return false;
    if (frame[6] != bus_crc8(frame.data(), 6u)) return false;
    if (!check_crc16(frame)) return false;

    std::memcpy(&out.package_number, frame.data() + 2u, 2u);
    std::memcpy(&out.package_length, frame.data() + 4u, 2u);
    std::memcpy(&out.target_address, frame.data() + 7u, 2u);
    std::memcpy(&out.source_address, frame.data() + 9u, 2u);
    std::memcpy(&out.type, frame.data() + 11u, 2u);
    out.payload_len = (uint16_t)(frame.size() - 15u);
    return true;
}

int main()
{
    const std::vector<uint8_t> short_motion = {0x3D, 0xC5, 0x0C, 0xC8, 0x03, 0x00, 0x07, 0x00, 0x7F, 0x02, 0x36, 0x54};
    const std::vector<uint8_t> short_status = {0x3D, 0xC5, 0x0D, 0xF1, 0x04, 0x00, 0x01, 0x00, 0x03, 0xFF, 0x00, 0xB2, 0xC4};
    const std::vector<uint8_t> short_set = {0x3D, 0xC0, 0x08, 0xB2, 0x08, 0x60, 0xB4, 0x04};

    assert(classify_short_cmd(short_motion) == 0x03u);
    assert(classify_short_cmd(short_status) == 0x04u);
    assert(check_crc16(short_set));

    std::vector<uint8_t> bad_crc = short_motion;
    bad_crc[10] ^= 0x01u;
    assert(classify_short_cmd(bad_crc) == 0xFFu);

    std::vector<uint8_t> long_serial = {
        0x3D, 0x00,
        0x34, 0x12,
        0x11, 0x00,
        0x00,
        0x00, 0x07,
        0x34, 0x12,
        0x02, 0x04,
        0x01, 0x02, 0x03, 0x04,
        0x00, 0x00
    };

    long_serial[6] = bus_crc8(long_serial.data(), 6u);
    const uint16_t c = bus_crc16(long_serial.data(), (uint32_t)long_serial.size() - 2u);
    long_serial[long_serial.size() - 2u] = (uint8_t)(c & 0xFFu);
    long_serial[long_serial.size() - 1u] = (uint8_t)(c >> 8);

    LongHeader h{};
    assert(parse_long(long_serial, h));
    assert(h.package_number == 0x1234u);
    assert(h.target_address == 0x0700u);
    assert(h.source_address == 0x1234u);
    assert(h.type == 0x0402u);
    assert(h.payload_len == 4u);

    std::vector<uint8_t> truncated = {0x3D, 0x00, 0x00};
    assert(!parse_long(truncated, h));
    return 0;
}
