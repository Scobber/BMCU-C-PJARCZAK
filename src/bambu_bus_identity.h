#pragma once
#include <stdint.h>

#ifndef BMCU_DYNAMIC_AMS_ID
#define BMCU_DYNAMIC_AMS_ID 1
#endif

#ifndef BMCU_BAMBU_PROTOCOL_TRACE
#define BMCU_BAMBU_PROTOCOL_TRACE 0
#endif

#ifndef BMCU_CLEAR_ASSIGNED_ID_ON_BOOT
#define BMCU_CLEAR_ASSIGNED_ID_ON_BOOT 0
#endif

#ifndef BAMBU_BUS_AMS_NUM
#define BAMBU_BUS_AMS_NUM 0
#endif

static constexpr uint8_t BAMBU_AMS_ID_UNASSIGNED = 0xFFu;
static constexpr uint8_t BAMBU_AMS_MAX_ID = 3u;

enum class BambuAmsProtocolState : uint8_t
{
    UNASSIGNED = 0,
    ASSIGNED,
    REGISTERING,
    ONLINE,
    LOST_HOST
};

struct BambuAmsIdentity
{
    uint8_t assigned_id;
    bool id_valid;
    bool registered;
    uint8_t serial_ascii[15];
    uint8_t hardware_identity[16];
    uint32_t assignment_generation;
    bool heartbeat_alive;
    BambuAmsProtocolState state;
    uint8_t last_assignment_reason;
    uint8_t last_clear_reason;
};

void bambubus_identity_init(void);
const BambuAmsIdentity* bambubus_identity_get(void);
uint8_t bambubus_current_ams_id(void);
bool bambubus_has_assigned_id(void);
bool bambubus_is_registered(void);
bool bambubus_set_assigned_id(uint8_t id);
void bambubus_clear_assigned_id(void);
void bambubus_reset_registration(void);
void bambubus_mark_registering(void);
void bambubus_mark_registered(void);
void bambubus_heartbeat_alive(bool alive);
uint8_t bambubus_local_ams_index(void);
void bambubus_build_identity_blob(uint8_t out[67]);
