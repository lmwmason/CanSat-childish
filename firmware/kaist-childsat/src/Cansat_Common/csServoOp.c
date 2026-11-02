
void hyCANSAT_SERVO_OPERATION()
{
#if defined(SERVO_TEST_TA) || defined(SERVO_TEST_AT) || defined(SERVO_TEST_DT)
    return;
#endif
	hyCANSAT_SERVO_ATTACH();
	if (IS_NEED_ICMD(ICMD_MASK_PWM_0_L)) { pwm_0_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_0_R)) ? PWM_CNT_CENTER : PWM_CNT_LEFT; } // 11 , 10
	else { pwm_0_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_0_R)) ? PWM_CNT_RIGHT : cansat_byte_cmd[0]; } // 01 , 00

	if (IS_NEED_ICMD(ICMD_MASK_PWM_1_L)) { pwm_1_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_1_R)) ? PWM_CNT_CENTER : PWM_CNT_LEFT; } // 11 , 10
	else { pwm_1_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_1_R)) ? PWM_CNT_RIGHT : cansat_byte_cmd[1]; } // 01 , 00

	csServo[0].write(pwm_0_cnt);
	csServo[1].write(pwm_1_cnt);
}

void hyCANSAT_SERVO_OPERATION_WITH_ATLM()
{
	hyCANSAT_SERVO_ATTACH();

	csServo[0].write(ad_data[0]);
	csServo[1].write(ad_data[1]); // when use 
}

void hyCANSAT_SERVO_OPERATION_WITH_IMU_VALUE()
{
	hyCANSAT_SERVO_ATTACH();
	//  csServo[0].write(yaw);
	//  csServo[0].write(map(ad_data[6],0,256,0,180));

	csServo[0].write(v_value);
	csServo[1].write(v_sign);
}
