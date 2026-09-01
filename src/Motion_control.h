#pragma once
#include <stdint.h>
#include <stdbool.h>

void Motion_control_init();
void Motion_control_set_PWM(uint8_t CHx, int PWM);
void Motion_control_run(int error);
bool Motion_control_save_dm_key_none_thresholds(void);

void MC_PULL_detect_channels_inserted();

// Externy
extern float   MC_PULL_V_OFFSET[4];
extern float   MC_PULL_V_MIN[4];
extern float   MC_PULL_V_MAX[4];
extern uint8_t MC_PULL_pct[4];
extern int8_t  MC_PULL_POLARITY[4];
extern float   MC_DM_KEY_NONE_THRESH[4];
extern bool    filament_channel_inserted[4];

// platformio.ini: -DBAMBU_BUS_AMS_NUM
#ifndef BAMBU_BUS_AMS_NUM
#define BAMBU_BUS_AMS_NUM 0
#endif

// platformio.ini: -DAMS_RETRACT_LEN
#ifndef AMS_RETRACT_LEN
#define AMS_RETRACT_LEN 0.2f
#endif

// DM PRO maximum retract distance: one source of truth.
// This is the safety/fallback limit; normal unload stops at front-switch clear.
#define DM_PRO_MAX_RETRACT_M AMS_RETRACT_LEN

// DM PRO dual-microswitch hardware is the only supported hardware in this fork.
#define BMCU_DM_TWO_MICROSWITCH 1

// BMCU_DM_SOLO=1: standalone DM PRO feeder (BAMBU_BUS_AMS_NUM=0, no AMS chain).
// Protocol is identical to AMS A; this flag is reserved for future differentiation.
#ifndef BMCU_DM_SOLO
#define BMCU_DM_SOLO 0
#endif

// BMCU_DM_LITE=1: DM PRO lite variant (BAMBU_BUS_AMS_NUM=0).
// No distinct source implementation exists; this flag is reserved for future differentiation.
#ifndef BMCU_DM_LITE
#define BMCU_DM_LITE 0
#endif

// platformio.ini: -DBMCU_ONLINE_LED_FILAMENT_RGB=1 (show filament RGB on ONLINE LED when loaded)
#ifndef BMCU_ONLINE_LED_FILAMENT_RGB
#define BMCU_ONLINE_LED_FILAMENT_RGB 0
#endif

#ifndef motion_control_ams_num
#define motion_control_ams_num BAMBU_BUS_AMS_NUM
#endif

#ifndef motion_control_pull_back_distance
// DM PRO pullback: DM_PRO_MAX_RETRACT_M is the maximum allowed retract distance.
// Normal unload completion is front-switch-cleared; this is only the safety fallback.
#define motion_control_pull_back_distance DM_PRO_MAX_RETRACT_M
#endif

#if (BAMBU_BUS_AMS_NUM < 0) || (BAMBU_BUS_AMS_NUM > 3)
#error "BAMBU_BUS_AMS_NUM must be in range 0..3"
#endif
