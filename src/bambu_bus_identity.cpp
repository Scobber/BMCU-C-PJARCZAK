#include "bambu_bus_identity.h"
#include "Flash_saves.h"
#include "Debug_log.h"
#include <string.h>

static BambuAmsIdentity g_identity = {
    BAMBU_AMS_ID_UNASSIGNED,
    false,
    false,
    {0},
    {0},
    0u,
    false,
    BambuAmsProtocolState::UNASSIGNED,
    0u,
    0u
};

static void trace_state_change(const char* msg, uint8_t id)
{
#if BMCU_BAMBU_PROTOCOL_TRACE
    DEBUG(msg);
    DEBUG_num("", (int)id);
    DEBUG("\n");
#else
    (void)msg;
    (void)id;
#endif
}

static uint64_t uid_hash64(void)
{
    volatile const uint8_t* uid = (volatile const uint8_t*)0x1FFFF7E8;
    uint64_t v = 1469598103934665603ull;
    for (int i = 0; i < 12; i++)
    {
        v ^= uid[i];
        v *= 1099511628211ull;
    }

    v ^= v >> 30;
    v *= 0xBF58476D1CE4E5B9ull;
    v ^= v >> 27;
    v *= 0x94D049BB133111EBull;
    v ^= v >> 31;
    return v;
}

static void build_physical_identity(void)
{
    static const char hex[] = "0123456789ABCDEF";
    const uint64_t v = uid_hash64();

    g_identity.serial_ascii[0] = '0';
    g_identity.serial_ascii[1] = 'E';
    g_identity.serial_ascii[2] = 'A';
    g_identity.serial_ascii[3] = '0';

    const uint8_t b0 = (uint8_t)(v >> 56);
    const uint8_t b1 = (uint8_t)(v >> 48);
    const uint8_t b2 = (uint8_t)(v >> 40);
    const uint8_t b3 = (uint8_t)(v >> 32);
    const uint8_t b4 = (uint8_t)(v >> 24);
    const uint8_t b5 = (uint8_t)(v >> 16);

    g_identity.serial_ascii[4] = hex[(b0 >> 4) & 0x0F];
    g_identity.serial_ascii[5] = hex[b0 & 0x0F];
    g_identity.serial_ascii[6] = hex[(b1 >> 4) & 0x0F];
    g_identity.serial_ascii[7] = hex[b1 & 0x0F];
    g_identity.serial_ascii[8] = hex[(b2 >> 4) & 0x0F];
    g_identity.serial_ascii[9] = hex[b2 & 0x0F];
    g_identity.serial_ascii[10] = hex[(b3 >> 4) & 0x0F];
    g_identity.serial_ascii[11] = hex[b3 & 0x0F];
    g_identity.serial_ascii[12] = hex[(b4 >> 4) & 0x0F];
    g_identity.serial_ascii[13] = hex[b4 & 0x0F];
    g_identity.serial_ascii[14] = hex[(b5 >> 4) & 0x0F];

    g_identity.hardware_identity[0] = 0x0E;
    g_identity.hardware_identity[1] = 0xA0;
    g_identity.hardware_identity[2] = (uint8_t)(v >> 56);
    g_identity.hardware_identity[3] = (uint8_t)(v >> 48);
    g_identity.hardware_identity[4] = (uint8_t)(v >> 40);
    g_identity.hardware_identity[5] = (uint8_t)(v >> 32);
    g_identity.hardware_identity[6] = (uint8_t)(v >> 24);
    g_identity.hardware_identity[7] = (uint8_t)(v >> 16);
    g_identity.hardware_identity[8] = (uint8_t)(v >> 24);
    g_identity.hardware_identity[9] = (uint8_t)(v >> 16);
    g_identity.hardware_identity[10] = (uint8_t)(v >> 8);
    g_identity.hardware_identity[11] = (uint8_t)(v >> 0);
    g_identity.hardware_identity[12] = 0xFF;
    g_identity.hardware_identity[13] = 0xFF;
    g_identity.hardware_identity[14] = 0xFF;
    g_identity.hardware_identity[15] = 0xFF;
}

static void set_state_from_flags(void)
{
    if (!g_identity.id_valid)
    {
        g_identity.state = BambuAmsProtocolState::UNASSIGNED;
        return;
    }
    if (g_identity.registered && g_identity.heartbeat_alive)
    {
        g_identity.state = BambuAmsProtocolState::ONLINE;
        return;
    }
    if (g_identity.heartbeat_alive)
    {
        g_identity.state = BambuAmsProtocolState::REGISTERING;
        return;
    }
    g_identity.state = BambuAmsProtocolState::ASSIGNED;
}

void bambubus_identity_init(void)
{
    build_physical_identity();
    g_identity.registered = false;
    g_identity.heartbeat_alive = false;
    g_identity.last_assignment_reason = 0u;
    g_identity.last_clear_reason = 0u;

#if BMCU_DYNAMIC_AMS_ID
    uint8_t saved_id = BAMBU_AMS_ID_UNASSIGNED;
    bool saved_valid = false;
    if (Flash_AMS_bus_id_read(&saved_id, &saved_valid) && saved_valid && saved_id <= BAMBU_AMS_MAX_ID)
    {
        g_identity.assigned_id = saved_id;
        g_identity.id_valid = true;
    }
    else
    {
        g_identity.assigned_id = BAMBU_AMS_ID_UNASSIGNED;
        g_identity.id_valid = false;
    }
#if BMCU_CLEAR_ASSIGNED_ID_ON_BOOT
    bambubus_clear_assigned_id();
#endif
#else
    g_identity.assigned_id = (uint8_t)BAMBU_BUS_AMS_NUM;
    g_identity.id_valid = (g_identity.assigned_id <= BAMBU_AMS_MAX_ID);
#endif

    set_state_from_flags();
}

const BambuAmsIdentity* bambubus_identity_get(void)
{
    return &g_identity;
}

uint8_t bambubus_current_ams_id(void)
{
    return g_identity.id_valid ? g_identity.assigned_id : BAMBU_AMS_ID_UNASSIGNED;
}

bool bambubus_has_assigned_id(void)
{
    return g_identity.id_valid;
}

bool bambubus_is_registered(void)
{
    return g_identity.registered;
}

bool bambubus_set_assigned_id(uint8_t id)
{
    if (id > BAMBU_AMS_MAX_ID) return false;
    if (g_identity.id_valid && g_identity.assigned_id == id) return true;

    const uint8_t prev_id = g_identity.assigned_id;
    const bool prev_valid = g_identity.id_valid;
    const uint8_t prev_registered = g_identity.registered ? 1u : 0u;

    g_identity.assigned_id = id;
    g_identity.id_valid = true;
    g_identity.assignment_generation++;
    g_identity.last_assignment_reason = 1u;
    g_identity.registered = false;
#if BMCU_DYNAMIC_AMS_ID
    if (!Flash_AMS_bus_id_write(id, true))
    {
        g_identity.assigned_id = prev_id;
        g_identity.id_valid = prev_valid;
        g_identity.registered = (prev_registered != 0u);
        set_state_from_flags();
        return false;
    }
#endif
    set_state_from_flags();
    trace_state_change("ID ASSIGNED id=", id);
    return true;
}

void bambubus_clear_assigned_id(void)
{
    const uint8_t old_id = g_identity.assigned_id;
    g_identity.assigned_id = BAMBU_AMS_ID_UNASSIGNED;
    g_identity.id_valid = false;
    g_identity.registered = false;
    g_identity.last_clear_reason = 1u;
#if BMCU_DYNAMIC_AMS_ID
    Flash_AMS_bus_id_clear();
#endif
    set_state_from_flags();
    trace_state_change("ID CLEAR old=", old_id);
}

void bambubus_reset_registration(void)
{
    g_identity.registered = false;
    if (g_identity.id_valid && !g_identity.heartbeat_alive)
        g_identity.state = BambuAmsProtocolState::LOST_HOST;
    else
        set_state_from_flags();
}

void bambubus_mark_registering(void)
{
    if (!g_identity.id_valid) return;
    g_identity.registered = false;
    g_identity.state = BambuAmsProtocolState::REGISTERING;
    trace_state_change("REGISTER START id=", g_identity.assigned_id);
}

void bambubus_mark_registered(void)
{
    if (!g_identity.id_valid) return;
    g_identity.registered = true;
    set_state_from_flags();
    trace_state_change("REGISTER OK id=", g_identity.assigned_id);
}

void bambubus_heartbeat_alive(bool alive)
{
    g_identity.heartbeat_alive = alive;
    if (!alive)
        g_identity.registered = false;
    set_state_from_flags();
}

uint8_t bambubus_local_ams_index(void)
{
#if BMCU_DYNAMIC_AMS_ID
    return 0u;
#else
    return (uint8_t)BAMBU_BUS_AMS_NUM;
#endif
}

void bambubus_build_identity_blob(uint8_t out[67])
{
    if (!out) return;
    static const uint8_t k_template[67] = {
        15,
        '0','E','A','0','3','0','3','0','3','0','3','0','0','0','0',
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,
        0x0E,0xA0,0x30,0x30,0x30,0x30,0x00,0x00,
        0x30,0x30,0x30,0x30,
        0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,
        0x00,
        0xFF,0x00,0xFF,0x00,0xFF,0x00,
        0x00
    };
    memcpy(out, k_template, sizeof(k_template));
    memcpy(out + 1, g_identity.serial_ascii, sizeof(g_identity.serial_ascii));
    const uint8_t id = bambubus_current_ams_id();
    out[4] = g_identity.id_valid ? (uint8_t)('0' + id) : (uint8_t)'F';
    memcpy(out + 33, g_identity.hardware_identity, sizeof(g_identity.hardware_identity));
    out[34] = g_identity.id_valid ? (uint8_t)(0xA0u + id) : 0xAFu;
    out[65] = g_identity.id_valid ? id : BAMBU_AMS_ID_UNASSIGNED;
}
