// Cansat_2022_ALL_With_SD_SUB_MSG_MultiSubUnits4
//////////////////////////
// Cansat Main Loop  //
//////////////////////////
void loop()
{
	hyLed_PortSet();

	if (IS_NEED_ICMD(ICMD_MASK_RESET)) { CLEAR_ICMD(ICMD_MASK_RESET); hyCANSAT_INIT(1); }

	if (watch_dog_cnt == 0) { sei(); }
	//		else wdt_reset() ; // reset hardware watch_dog when data received //
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


   // hyCANSAT_Mx_OPERATION_WITH_UNIT_Set(unsigned char iMid,unsigned char iBaudType, unsigned char iCmdId)
	hyCANSAT_Mx_OPERATION_WITH_UNIT_TX_SET(4,BAUD_115200,0); // M4 , 115200, Cmd0 
	hyCANSAT_Mx_OPERATION_WITH_UNIT_TX_SET(5,BAUD_115200,1); // M5 , 115200, Cmd1 
	hyCANSAT_Mx_OPERATION_WITH_UNIT_TX_SET(6,BAUD_115200,2); // M6 , 115200, Cmd2 
	hyCANSAT_Mx_OPERATION_WITH_UNIT_TX_SET(7,BAUD_115200,3); // M7 , 115200, Cmd3 

	hyTransUartOne();
}