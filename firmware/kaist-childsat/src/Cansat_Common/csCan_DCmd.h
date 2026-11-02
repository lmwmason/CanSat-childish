#ifndef _CS_CAN_DCMD_H_
#define _CS_CAN_DCMD_H_

///////////////////////////////////////////////////
// use COMMANDS 4 Bytes 32 Commands 
// it is possible to  command as array [[cansat_dcmd[4]]]
// but for the processing speed use each variable name 
// DTLM & CMD & iCMD
unsigned char cansat_dcmd_0 = 0xFF; // operation flag 1111 1111
unsigned char cansat_dcmd_1 = 0x00; // dcmd_1 for use Digital Port
unsigned char cansat_dcmd_2 = 0x00; // dcmd_2 for use sub command
unsigned char cansat_dcmd_3 = 0x00; // dcmd_3 for use Analog Port 

unsigned char cansat_byte_cmd[8] = { 0,0,0,0,0,0,0,0 };

// 2012.6.29 : Append OP_MASK_USER for USER Defined Operation

// cansat_dcmd_0 
#define OP_MASK_GPS        0x80
#define OP_MASK_IMU        0x40
#define OP_MASK_CAMERA     0x20 
#define OP_MASK_ATLM       0x10
#define OP_MASK_DTLM       0x08
#define OP_MASK_USER       0x04
#define OP_MASK_CAMERA_160 0x02 // default 320 when 1 0 then 160
#define OP_MASK_CAMERA_640 0x01 // default 320 when 0 1 then 640

#define IS_NEED_OP(macMask) (( cansat_dcmd_0 & (macMask) ) ? 1 : 0 )
#define TOGGLE_OP(macMask)  {cansat_dcmd_0 ^= (macMask) ; }
#define SET_OP(macMask)     {cansat_dcmd_0 |=  (macMask) ; }
#define CLEAR_OP(macMask)   {cansat_dcmd_0 &= ~(macMask) ; }

// cansat_dcmd_2 
#define ICMD_MASK_RESET             0x80 // reset cansat 
#define ICMD_MASK_CAMERA_RESET      0x40 // reset camera command
#define ICMD_MASK_ATLM_TO_DIGITAL   0x20 // when user operation
#define ICMD_MASK_ATLM_TO_LED       0x10 // when user operation
#define ICMD_MASK_PWM_0_L           0x20 // when not user/pwm operation
#define ICMD_MASK_PWM_0_R           0x10 // when not user/pwm operation
#define ICMD_MASK_PWM_1_L           0x08 // when not user/pwm operation
#define ICMD_MASK_PWM_1_R           0x04 // when not user/pwm operation
#define ICMD_MASK_GS                0x02
#define ICMD_MASK_SIGN              0x01

#define IS_NEED_ICMD(macMask) (( cansat_dcmd_2 & (macMask) ) ? 1 : 0 )
#define TOGGLE_ICMD(macMask)  {cansat_dcmd_2 ^=  (macMask) ; }
#define SET_ICMD(macMask)     {cansat_dcmd_2 |=  (macMask) ; }
#define CLEAR_ICMD(macMask)   {cansat_dcmd_2 &= ~(macMask) ; }

#endif