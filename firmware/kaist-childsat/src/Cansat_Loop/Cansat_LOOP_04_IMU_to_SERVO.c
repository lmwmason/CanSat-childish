// IMU to SERVO

//void hyCANSAT_SERVO_OPERATION_WITH_IMU_VALUE()
//{
//	hyCANSAT_SERVO_ATTACH();
//	//  csServo[0].write(yaw);
//	//  csServo[0].write(map(ad_data[6],0,256,0,180));
//
//	csServo[0].write(v_value);
//	csServo[1].write(v_sign);
//}

////////////////////////
// Cansat Main Loop   //
////////////////////////
void loop()
{
	hyLed_PortSet();

	//	if( IS_NEED_ICMD(ICMD_MASK_RESET) ) { CLEAR_ICMD(ICMD_MASK_RESET) ; hyCANSAT_INIT(); }

	if (watch_dog_cnt == 0) { sei(); }
	//		else wdt_reset() ;                                            // reset hardware watch_dog when data received //
	watch_dog_cnt = 0;

	hyCANSAT_LIFE_SIGN_OPERATION();
	//	if( IS_NEED_OP(OP_MASK_GPS   ) ) hyCANSAT_GPS_OPERATION()   ; // 9600
	//	if( IS_NEED_OP(OP_MASK_IMU   ) ) hyCANSAT_IMU_OPERATION()   ; // 115200
	//	if( IS_NEED_OP(OP_MASK_CAMERA) ) hyCANSAT_CAMERA_OPERATION(); // Digital Picture 115200
	//	if( IS_NEED_OP(OP_MASK_ATLM  ) ) hyCANSAT_ATLM_OPERATION()  ; 
	//	if( IS_NEED_OP(OP_MASK_DTLM  ) ) hyCANSAT_DTLM_OPERATION()  ;
	//	if( IS_NEED_OP(OP_MASK_USER  ) ) hyCANSAT_USER_OPERATION()  ;   // USER DEFINED OPERATION
	//      else                             hyCANSAT_SERVO_OPERATION() ;  // PWM OPERATION 
	IMU_DATA_RETRY_CNT_SET(3);
	hyCANSAT_IMU_OPERATION(); // 115200
	hyCANSAT_SERVO_OPERATION_WITH_IMU_VALUE();  // PWM OPERATION 
	hyTransUartOne();
}