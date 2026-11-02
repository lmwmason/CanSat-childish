#if defined(SERVO_TEST_TA) || defined(SERVO_TEST_AT) || defined(SERVO_TEST_DT)
#include "servo_sweep.h"
#include "bt_inventory.h"
static bool btInventoryRequested = false;
#endif
////////////////////////////////////////////////////////
// CANSAT PROGRAM : 2025.05.03 hypakr@satrec (Check the BT Status and Don't Send Camera Data for Safty )
// CANSAT PROGRAM : 2024.09.03 hypakr@satrec (Insert ProgramRunNumber in LifeSign Data )
// CANSAT PROGRAM : 2024.08.04 hypark@satrec (Check GS Connection and Don't Send Image when Disconnected :: gs.(h,c), TransUart.(h,c), CameraOp.c )
// CANSAT PROGRAM : 2024.07.23 hypark@satrec (Bluetooth Upload OK need reset )
// CANSAT PROGRAM : 2024.07.23 hypark@satrec (PROGRAM 0x41 CANSAT + IMU + SERVO OK )
// CANSAT PROGRAM : 2024.07.10 hypark@satrec (DHT1 Read Insert)
// CANSAT PROGRAM : 2024.06.07 hypark@satrec (Local Time Update :: csLifeSign.c )
// CANSAT PROGRAM : 2024.06.07 hypark@satrec (Cansat Time Set Update :: csGs.c  )
// CANSAT PROGRAM : 2022.06.26 hypark@satrec (DataStructure Conversion)
// CANSAT PROGRAM : 2022.05.13 hypark@satrec (New BT Configuration)
// CANSAT PROGRAM : 2022.05.03 hypark@satrec (New BT)
// CANSAT PROGRAM : 2022.04.04 hypark@satrec (New Gpsr)
// CANSAT PROGRAM : 2016.10.13 hypark@satrec
///////////////////////////////////////////////////

///////////////////////////////////////////////////
#include "Cansat_Common/csCan_BaseDef.h"
#include "Cansat_Common/csCan_Queue.h"
#include "Cansat_Common/csCan_RxMode.h"
#include "Cansat_Common/csCan_DCmd.h"
///////////////////////////////////////////////////
#include "Cansat_Common/csLed.h"
#include "Cansat_Common/csEeprom.h"
//////////////////////////////////////////////////////////////////////////////  
#include "Cansat_Common/csPwmTimer.h"
/////////////////////////////////////////
//        Define Using Data            //
/////////////////////////////////////////
#include "Cansat_Common/csOperations.h"
#include "Cansat_Common/csTransUart.h"
/////////////////////////////////////////
#include "Cansat_Common/csAtlm.h"
#include "Cansat_Common/csDtlm.h"
#include "Cansat_Common/csBT.h"
#include "Cansat_Common/csCamera.h"
#include "Cansat_Common/csGps.h"
#include "Cansat_Common/csImu.h"
//////////////////////////////////////////
#include "Cansat_Common/csServo.h"
//////////////////////////////////////////
#include "Cansat_Common/csMessage.h"
#include "Cansat_Common/csLog.h"
#include "Cansat_Common/csGs.h"
/////////////////////////////////////////
//           Define  Execute           //
/////////////////////////////////////////
#include "Cansat_Common/csAtlm.c"
#include "Cansat_Common/csDtlm.c"
#include "Cansat_Common/csBT.c"
#include "Cansat_Common/csCamera.c"
#include "Cansat_Common/csGps.c"
#include "Cansat_Common/csImu.c"
//#include "Cansat_Common/csImu_Normal.c"
/////////////////////////////////////////
#include "Cansat_Common/csTransUart.c"
#include "Cansat_Common/csMessage.c"
#include "Cansat_Common/csLog.c"
#include "Cansat_Common/csGs.c"
/////////////////////////////////////////
#include "Cansat_Common/csAtlmOp.c"
#include "Cansat_Common/csDtlmOp.c"
#include "Cansat_Common/csCameraOp.c"
#include "Cansat_Common/csGpsOp.c"
#include "Cansat_Common/csImuOp.c"
/////////////////////////////////////////
#include "Cansat_Common/csMessageOp.c"
#include "Cansat_Common/csLifeSignOp.c"
#include "Cansat_Common/csServoOp.c"
#include "Cansat_Common/csUserOp.c"
/////////////////////////////////////////
#include "Cansat_Common/csCan_Init.c"
/////////////////////////////////////////

////////////////////////////
// Cansat Initial Setup   //
///////////////////////////

#if defined(SERVO_TEST_TA) || defined(SERVO_TEST_AT) || defined(SERVO_TEST_DT)
#include <stdio.h>
extern volatile unsigned long servoTimer3Count;
void btInventoryReport()
{
    btInventoryRequested = false;
    const uint16_t n = btRecordLength();
    char text[80];
    snprintf(text, sizeof(text), "BT_EEPROM valid=%u length=%u", n ? 1 : 0, n);
    hyCANSAT_Gs_Tx_Message(14, text);
    for (uint16_t offset=0; offset<n; offset+=16) {
        int pos=snprintf(text,sizeof(text),"BT_EEPROM_HEX %u ",offset);
        const char hex[]="0123456789ABCDEF";
        for(uint16_t i=offset;i<n && i<offset+16;++i) {
            const uint8_t b=EEPROM.read(BT_RECORD_BASE+8+i);
            text[pos++]=hex[b>>4];text[pos++]=hex[b&15];
        }
        text[pos]=0;hyCANSAT_Gs_Tx_Message(14,text);
    }
}
void servoSweepReport()
{
    static unsigned long reported = 0;
    const unsigned long now = millis();
    if (now - reported < 2000) return;
    reported = now;
    unsigned long irq;
    const uint8_t saved = SREG;
    cli(); irq = servoTimer3Count; SREG = saved;
    char text[104];
    snprintf(text, sizeof(text), "SERVO angle=%d pins=%u,%u,%u DDRF=%02X JTD=%u T3=%02X IRQ=%lu attached=%u%u%u",
             testAngle, testPins[0], testPins[1], testPins[2], DDRF,
             !!(MCUCSR & _BV(JTD)), ETIMSK, irq,
             testServos[0].attached(), testServos[1].attached(), testServos[2].attached());
    hyCANSAT_Gs_Tx_Message(15, text);
}
#endif

void setup() 
{
  //hyCANSAT_INIT(BT_NEED_INIT);  // need initial boot load
  hyCANSAT_INIT(BT_NO_NEED_INIT);
  hyLed_PortSet() ;
  OP_FROM_EEPROM();
  hyCANSAT_SD_LOG_INIT();
#if defined(SERVO_TEST_TA) || defined(SERVO_TEST_AT) || defined(SERVO_TEST_DT)
  servoSweepSetup();
#endif  
}

//////////////////////////
// Cansat Main Loop     //
//////////////////////////

#define RUN_PROGRAM 1 // Default //

// 2024.09.03 : Display in LifeSign
unsigned char gProgramType = RUN_PROGRAM ;

#if   ( RUN_PROGRAM == 1  )
#include "Cansat_Loop/Cansat_LOOP_01_SD_MSG.c"
#elif ( RUN_PROGRAM == 4  )
#include "Cansat_Loop/Cansat_LOOP_04_IMU_to_SERVO.c"
#elif ( RUN_PROGRAM == 5  )
#include "Cansat_Loop/Cansat_LOOP_05_ATLM_to_SERVO.c"
#elif ( RUN_PROGRAM == 6  )
#include "Cansat_Loop/Cansat_LOOP_06_SD_SUB_MSG.c"
#elif ( RUN_PROGRAM == 7  )
#include "Cansat_Loop/Cansat_LOOP_07_SD_MSG_2_CAMERA.c"
#elif ( RUN_PROGRAM == 8  )
#include "Cansat_Loop/Cansat_LOOP_08_SD_SUB_MSG_3_SubUnit.c"
#elif ( RUN_PROGRAM == 9  )
#include "Cansat_Loop/Cansat_LOOP_08_SD_SUB_MSG_3_SubUnit.c"
#elif ( RUN_PROGRAM == 10 )
#include "Cansat_Loop/Cansat_LOOP_10_SD_SUB_MSG_MultiSubUnits.c"
#elif ( RUN_PROGRAM == 11  )
#include "Cansat_Loop/Cansat_LOOP_11_SD_SUB_MSG_MultiSubUnits4.c"
#elif ( RUN_PROGRAM == 12  )
#include "Cansat_Loop/Cansat_LOOP_12_SD_SUB_MSG_MultiSubUnits4_Sch.c"
#elif ( RUN_PROGRAM == 20 )
#include "Cansat_Common/csServo_RobotArm.h"
#include "Cansat_Common/csServoOp_RobotArm.c"
#include "Cansat_Loop/Cansat_LOOP_20_ATLM_to_ROBOT_ARM.c"
#elif ( RUN_PROGRAM == 30  )  // not yet
#include "Cansat_Loop/Cansat_LOOP_30_DS18B20_to_ATLM.c"
#elif ( RUN_PROGRAM == 31  )  // OK with Timming Change 
#include "Cansat_Loop/Cansat_LOOP_31_DHT11_to_ATLM.c"
#elif ( RUN_PROGRAM == 0x41) 
#include "Cansat_Loop/Cansat_LOOP_41_IMU_to_SERVO.c"
#else

// Cansat Default Main Loop Template //
void loop() 
{
	hyLed_PortSet() ;

	if( IS_NEED_ICMD(ICMD_MASK_RESET) ) { CLEAR_ICMD(ICMD_MASK_RESET) ; hyCANSAT_INIT(1); }
		
	if( watch_dog_cnt == 0 ) { sei(); } 
	watch_dog_cnt=0 ;

  Get_GsConnected() ; // update 2025.05.03 :: defined in the csCan_BaseDef.h
  if( !Is_GsConnected() ) delay(100);

	hyCANSAT_LIFE_SIGN_OPERATION() ;  
	if( IS_NEED_OP(OP_MASK_GPS   ) ) hyCANSAT_GPS_OPERATION()   ; // 9600
  if( IS_NEED_OP(OP_MASK_GPS   ) ) hyCANSAT_Gs_Tx_Message(0,"After GPS OP");
	if( IS_NEED_OP(OP_MASK_IMU   ) ) hyCANSAT_IMU_OPERATION()   ; // 115200
  if( IS_NEED_OP(OP_MASK_IMU   ) ) hyCANSAT_Gs_Tx_Message(1,"After IMU OP");
//	if( IS_NEED_OP(OP_MASK_CAMERA) ) hyCANSAT_CAMERA_OPERATION_WITH_IMG_BLOCK(); // Digital Picture 115200
  if( IS_NEED_OP(OP_MASK_CAMERA) ) hyCANSAT_CAMERA_OPERATION(); // Digital Picture 115200
  if( IS_NEED_OP(OP_MASK_CAMERA) ) hyCANSAT_Gs_Tx_Message(2,"After CAMERA OP");
	if( IS_NEED_OP(OP_MASK_ATLM  ) ) hyCANSAT_ATLM_OPERATION()  ; 
  if( IS_NEED_OP(OP_MASK_ATLM  ) ) hyCANSAT_Gs_Tx_Message(3,"After ATRM OP");
	if( IS_NEED_OP(OP_MASK_DTLM  ) ) hyCANSAT_DTLM_OPERATION()  ;
  if( IS_NEED_OP(OP_MASK_DTLM  ) ) hyCANSAT_Gs_Tx_Message(4,"After DTLM OP");
	if( IS_NEED_OP(OP_MASK_USER  ) ) hyCANSAT_USER_OPERATION()  ; // USER DEFINED OPERATION
  else                             hyCANSAT_SERVO_OPERATION() ; // PWM OPERATION 

//  hyCANSAT_M4_OPERATION();
//  hyCANSAT_M5_OPERATION();
//  hyCANSAT_M6_OPERATION();
//  hyCANSAT_M7_OPERATION();
//  hyCANSAT_Mx_OPERATION_WITH_UNIT_Set(4,BAUD_115200,0); // M4 , 115200, Cmd0 
//  hyCANSAT_Mx_OPERATION_WITH_UNIT_Set(5,BAUD_115200,1); // M5 , 115200, Cmd1 
//  hyCANSAT_Mx_OPERATION_WITH_UNIT_Set(6,BAUD_115200,2); // M6 , 115200, Cmd2 
//  hyCANSAT_Mx_OPERATION_WITH_UNIT_Set(7,BAUD_115200,3); // M7 , 115200, Cmd3 
        
	hyTransUartOne();  
}
#endif

