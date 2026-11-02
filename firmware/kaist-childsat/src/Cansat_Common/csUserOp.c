// void hyCANSAT_ATLM_TO_DIGITAL();
// void hyCANSAT_ATLM_TO_LED();
// void hyCANSAT_USER_OPERATION()


// User Defined Operations 
void hyCANSAT_ATLM_TO_DIGITAL()
{
#if 1	
	unsigned char pf = PINF; // ANALOG PIN PORT
	cansat_dcmd_1 = 0;
	if (pf & 0x01) cansat_dcmd_1 |= 0x80;
	if (pf & 0x02) cansat_dcmd_1 |= 0x40;
	if (pf & 0x04) cansat_dcmd_1 |= 0x20;
	if (pf & 0x08) cansat_dcmd_1 |= 0x10;
	if (pf & 0x10) cansat_dcmd_1 |= 0x08;
	if (pf & 0x20) cansat_dcmd_1 |= 0x04;
	if (pf & 0x40) cansat_dcmd_1 |= 0x02;
	if (pf & 0x80) cansat_dcmd_1 |= 0x01;
#else	
	cansat_dcmd_1 = PINF;
#endif	
	PORTA = cansat_dcmd_1; // ANALOG to DIGITAL
}

void hyCANSAT_ATLM_TO_LED()
{
	cansat_led = 0;
	if (0x10 < ad_data[0]) cansat_led |= 0x01;
	if (0x30 < ad_data[0]) cansat_led |= 0x02;
	if (0x50 < ad_data[0]) cansat_led |= 0x04;
	if (0x70 < ad_data[0]) cansat_led |= 0x08;
	if (0x90 < ad_data[0]) cansat_led |= 0x10;
	if (0xB0 < ad_data[0]) cansat_led |= 0x20;
	if (0xD0 < ad_data[0]) cansat_led |= 0x40;
	if (0xF0 < ad_data[0]) cansat_led |= 0x80;
	if (!IS_NEED_OP(OP_MASK_USER)) { cansat_led = cansat_dcmd_0; }
	//	else                              { cansat_led = cansat_dcmd_0; }
	//	cansat_led = cansat_dcmd_0       ;
	//	cansat_led = cansat_led ^ 0xFF ;
	PORTB = cansat_led;
}

// User Defined OPERATION
#if 0
void hyCANSAT_USER_OPERATION()
{
	hyCANSAT_SERVO_DETACH();
	//  hyCANSAT_M4_OPERATION();
	//  hyCANSAT_M5_OPERATION();
	//  hyCANSAT_M6_OPERATION();
	hyCANSAT_M7_OPERATION();
}

#else
void hyCANSAT_USER_OPERATION()
{
	hyCANSAT_SERVO_DETACH();
	if      (IS_NEED_ICMD(ICMD_MASK_ATLM_TO_DIGITAL)) hyCANSAT_ATLM_TO_DIGITAL();
	else if (IS_NEED_ICMD(ICMD_MASK_ATLM_TO_LED)    ) hyCANSAT_ATLM_TO_LED();
}
#endif
