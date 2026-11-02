#ifndef _CS_PWM_TIMER_H_
#define _CS_PWM_TIMER_H_

////////////////////////////////////////////////////////////////////////////////
// for 10 ms
// 16000000/1024 ==> 15625  // 15625==125*125==> 125   ==> 0x7D
// 11059200/1024 ==> 10800  // 10800/100     ==> 108   ==> 0x6C
// 9830400/1024 ==> 9600	// 9600/100      ==> 96    ==> 0x60 ==> 0x90

// User TIMER to Control SERVO
// 20 msec period use
// 1.0 msec Left Move Time
// 1.5 msec Middle Move Time
// 2.0 msec Right Move Time

unsigned char pwm_0_cnt = 0;
unsigned char pwm_1_cnt = 0;
/////////////////////////////////////////////////////////////////////////////////////////////


#if 0 // when 0.25msec ticks
#define PWM_20_MSEC_CNT  80   // 20 msec
#define PWM_CNT_NULL      0   //  no control
#define PWM_CNT_LEFT      5   //  1   msec   // over 4 + 1
#define PWM_CNT_CENTER    6   //  1.5 msec
#define PWM_CNT_RIGHT     7   //  2   msec  // under 8 - 1
#elif 0 // when 0.1 msec ticks
#define PWM_20_MSEC_CNT 200   // 20 msec
#define PWM_CNT_NULL      0   //  no control
#define PWM_CNT_LEFT     11   //  1   msec  // over  10 + 1
#define PWM_CNT_CENTER   15   //  1.5 msec  // 
#define PWM_CNT_RIGHT    19   //  2   msec  // under 20 - 1
#elif 0 // when 0.05 msec ticks
#define PWM_20_MSEC_CNT 400   // 20 msec
#define PWM_CNT_NULL      0   //  no control
#define PWM_CNT_START    15
#define PWM_CNT_LEFT     20   //  1   msec  // over  10 + 1
#define PWM_CNT_CENTER   30   //  1.5 msec  //
#define PWM_CNT_RIGHT    40   //  2   msec  // under 20 - 1
#define PWM_CNT_END      55
#elif 0 // when 0.25 msec ticks
#define PWM_20_MSEC_CNT 800   // 20 msec
#define PWM_CNT_NULL      0   //  no control
#define PWM_CNT_START    30
#define PWM_CNT_LEFT     41   //  1   msec  // over  10 + 1
#define PWM_CNT_CENTER   60   //  1.5 msec  //
#define PWM_CNT_RIGHT    79   //  2   msec  // under 20 - 1
#define PWM_CNT_END     140
#elif 0 // when 0.02 msec ticks ( 20 us )
#define PWM_20_MSEC_CNT 1000   // 20 msec
#define PWM_CNT_NULL       0   //  no control
#define PWM_CNT_LEFT      51   //  1   msec  // over   + 1
#define PWM_CNT_CENTER    75   //  1.5 msec  //
#define PWM_CNT_RIGHT     99   //  2   msec  // under  - 1
#else  // when arduino's count == degree
#define PWM_20_MSEC_CNT 800   // 20 msec
#define PWM_CNT_NULL      0   //  no control
#define PWM_CNT_START     0
#define PWM_CNT_LEFT      0   //    0 deg
#define PWM_CNT_CENTER   90   //   90 deg
#define PWM_CNT_RIGHT   180   //  180 deg
#define PWM_CNT_END     180
#endif

// Use Value to Control 
// 00 : NULL : Nothing 
// 01 : LEFT
// 11 : CENTER
// 10 : RIGHT  
inline void hyCANSAT_PWM_OPERATION() // 0.1 msec Step Processing
{
	// pwm processing  20 msec processing
	time_servo_tick++;
	if (PWM_20_MSEC_CNT <= time_servo_tick)	time_servo_tick = 0;


	// 0 == 0.5ms , 1 == 1ms , 2 == 1.5ms, 3 == 2 ms
	// PWM_0 COUNT °è»ê
	if (IS_NEED_ICMD(ICMD_MASK_PWM_0_L)) { pwm_0_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_0_R)) ? PWM_CNT_CENTER : PWM_CNT_LEFT; }
	else { pwm_0_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_0_R)) ? PWM_CNT_RIGHT : cansat_byte_cmd[0]; }
	if (IS_NEED_ICMD(ICMD_MASK_PWM_1_L)) { pwm_1_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_1_R)) ? PWM_CNT_CENTER : PWM_CNT_LEFT; }
	else { pwm_1_cnt = (IS_NEED_ICMD(ICMD_MASK_PWM_1_R)) ? PWM_CNT_RIGHT : cansat_byte_cmd[1]; }

	if (PWM_CNT_START <= pwm_0_cnt && time_servo_tick <= pwm_0_cnt && time_servo_tick <= PWM_CNT_END) { cansat_dcmd_1 |= 0x80; }
	else { cansat_dcmd_1 &= 0x7F; }
	if (PWM_CNT_START <= pwm_1_cnt && time_servo_tick <= pwm_1_cnt && time_servo_tick <= PWM_CNT_END) { cansat_dcmd_1 |= 0x40; }
	else { cansat_dcmd_1 &= 0xBF; }
	PORTA = cansat_dcmd_1;
}

//// 1ms Step Processing
//inline void hyCANSAT_MSEC_OPERATION() // 1 msec Step Processing.
//{
//	// msec Step time increase
//	time_msec++   ;
//	
//	// wait ms processing
//	if( 0 < time_wait_msec ) time_wait_msec-- ;
//	
//	// 1000ms == 1sec step Operation 
////	if( 1000 < time_msec ) // 1 SEC // need more 80 steps
//	if( 1080 < time_msec )     // 1 SEC // need more 80 steps
//	{
//		time_msec = 0 ;
//		time_run++    ;
//		time_sec++    ; // 1 sec
//	}
//}

//   1  msec : 0xAA
// 0.5  msec : 0xD5 
// 0.25 msec : 0xEC
// 0.20 msec : 0xEF
// 0.10 msec : 0xF8 : when TCCR0 == 5 // 100 us
// 0.05 msec : 0xF? : when TCCR0 == 5 // 50  us
// 0.02 msec : 0xF9 : when TCCR0 == 3 // 20  us
// 0.01 msec : 0x?? : when TCCR0 == 3 // 10  us 
//SIGNAL(TIMER0_OVF_vect)
//{
////	TCNT0 = 0xAA ;	// clock change ==> need change : lets make 1ms
////	TCNT0 = 0xD5 ;	// clock change ==> need change : lets make 0.5ms 
////	TCNT0 = 0xEC ;	// clock change ==> need change : lets make 0.25ms 
////	TCNT0 = 0xEF ;	// clock change ==> need change : lets make 0.2ms 
////	TCNT0 = 0xF8 ;	// clock change ==> need change : lets make 0.1ms , TCCR0 == 5
//	TCNT0 = 0xFC ;	// clock change ==> need change : lets make 0.05ms , TCCR0 == 5
////	TCNT0 = 0xFE ;	// clock change ==> need change : lets make 0.025ms, TCCR0 == 5 .. occur image error..
////	TCNT0 = 0xF9 ;	// clock change ==> need change : lets make 0.02ms , TCCR0 == 3
//	
//	// increase time_msec
//	time_tick++ ; // when Initial Value is 0 , 1 ==> 0 ==> 1 // Toggle 1 and 0 
//	if( 20 <= time_tick  ) { time_tick = 0 ; hyCANSAT_MSEC_OPERATION() ; } // every : 1msec 
//	if( !IS_NEED_OP(OP_MASK_USER  ) ) hyCANSAT_PWM_OPERATION()  ;          // NOT USER DEFINED ==> PWM OPERATION
////   cansat_dcmd_1 ^= 0x80 ;	PORTA = cansat_dcmd_1 ;
//}


#endif