// A0 to SERVO
//////////////////////////
// Cansat Main Loop     //
//////////////////////////
//void hyCANSAT_SERVO_OPERATION_WITH_ATLM()
//{
//	hyCANSAT_SERVO_ATTACH();
//
//	csServo[0].write(ad_data[0]);
//	csServo[1].write(ad_data[1]); // when use 
//}


void loop()
{
	hyLed_PortSet();

	if (IS_NEED_ICMD(ICMD_MASK_RESET)) { CLEAR_ICMD(ICMD_MASK_RESET); hyCANSAT_INIT(1); }

	if (watch_dog_cnt == 0) { sei(); }
	//		else wdt_reset() ;    // reset hardware watch_dog when data received //
	watch_dog_cnt = 0;

	//hyCANSAT_LIFE_SIGN_OPERATION();
	//if (IS_NEED_OP(OP_MASK_GPS)) hyCANSAT_GPS_OPERATION(); // 9600
	//if (IS_NEED_OP(OP_MASK_GPS)) hyCANSAT_Gs_Tx_Message(0, "After GPS OP");
	//if (IS_NEED_OP(OP_MASK_IMU)) hyCANSAT_IMU_OPERATION(); // 115200
	//if (IS_NEED_OP(OP_MASK_IMU)) hyCANSAT_Gs_Tx_Message(1, "After IMU OP");
	//if (IS_NEED_OP(OP_MASK_CAMERA)) hyCANSAT_CAMERA_OPERATION(); // Digital Picture 115200
	//if (IS_NEED_OP(OP_MASK_CAMERA)) hyCANSAT_Gs_Tx_Message(2, "After CAMERA OP");
	//if (IS_NEED_OP(OP_MASK_ATLM)) hyCANSAT_ATLM_OPERATION();
	//if (IS_NEED_OP(OP_MASK_DTLM)) hyCANSAT_DTLM_OPERATION();
	//if (IS_NEED_OP(OP_MASK_USER)) hyCANSAT_USER_OPERATION(); // USER DEFINED OPERATION
	//else                             hyCANSAT_SERVO_OPERATION(); // PWM OPERATION 
	//  
	//hyTransUartOne();
	hyCANSAT_ATLM_OPERATION();
	hyCANSAT_SERVO_OPERATION_WITH_ATLM();  // PWM OPERATION 
	hyTransUartOne();
}
