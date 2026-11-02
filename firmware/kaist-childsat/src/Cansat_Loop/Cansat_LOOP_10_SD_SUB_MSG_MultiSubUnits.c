// Cansat_2022_ALL_With_SD_SUB_MSG_MultiSubUnits
//////////////////////////
// Cansat Main Loop     //
//////////////////////////
void loop()
{
	hyLed_PortSet();

	if (IS_NEED_ICMD(ICMD_MASK_RESET)) { CLEAR_ICMD(ICMD_MASK_RESET); hyCANSAT_INIT(1); }

	if (watch_dog_cnt == 0) { sei(); }
	//		else wdt_reset() ;                                            // reset hardware watch_dog when data received //
	watch_dog_cnt = 0;

	hyCANSAT_LIFE_SIGN_OPERATION();
	if (IS_NEED_OP(OP_MASK_GPS)) hyCANSAT_GPS_OPERATION(); // 9600
//  if( IS_NEED_OP(OP_MASK_GPS   ) ) hyCANSAT_Gs_Tx_Message(0,"After GPS OP");
	if (IS_NEED_OP(OP_MASK_IMU)) hyCANSAT_IMU_OPERATION(); // 115200
//  if( IS_NEED_OP(OP_MASK_IMU   ) ) hyCANSAT_Gs_Tx_Message(1,"After IMU OP");
	if (IS_NEED_OP(OP_MASK_CAMERA)) hyCANSAT_CAMERA_OPERATION(); // Digital Picture 115200
//  if( IS_NEED_OP(OP_MASK_CAMERA) ) hyCANSAT_Gs_Tx_Message(2,"After CAMERA OP");
	if (IS_NEED_OP(OP_MASK_ATLM)) hyCANSAT_ATLM_OPERATION();
	if (IS_NEED_OP(OP_MASK_DTLM)) hyCANSAT_DTLM_OPERATION();
	//	if( IS_NEED_OP(OP_MASK_USER  ) ) hyCANSAT_USER_OPERATION()  ; // USER DEFINED OPERATION
	//        else                           hyCANSAT_SERVO_OPERATION() ; // PWM OPERATION 

	//        hyCANSAT_M4_OPERATION();
	//        hyCANSAT_M5_OPERATION();

//	hyCANSAT_M6_OPERATION_WITH_UNIT_ID(0); // use m6 port and use id == 0 
//	hyCANSAT_M7_OPERATION_WITH_UNIT_ID(1); // use m7 port and use id == 1 
	hyCANSAT_Mx_OPERATION_WITH_UNIT_Set(4,BAUD_115200,2); // M4 , 115200, Cmd0 
	hyCANSAT_Mx_OPERATION_WITH_UNIT_Set(5,BAUD_115200,3); // M5 , 115200, Cmd1 

	hyTransUartOne();
}