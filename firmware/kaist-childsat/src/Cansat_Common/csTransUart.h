// update : 20240804 : hyTransUartUntilAnd added

#ifndef _CS_TRANS_UART_H_
#define _CS_TRANS_UART_H_

// UART Communication Main Processing
unsigned char hyTransUart();

// cnt times processing 
void hyTransUartWait(unsigned long cnt);

// spetical 1 signal watching and cnt times processing 
void hyTransUartUntil(unsigned char* flag, unsigned char value, unsigned long cnt);

// spetial 2 signal watching and cnt times processing 
void hyTransUartUntilAnd(unsigned char* flag0, unsigned char value0, unsigned char *flag1, unsigned char value1, unsigned long cnt);


// 1 time comminication processing 
#if defined(SERVO_TEST_TA) || defined(SERVO_TEST_AT) || defined(SERVO_TEST_DT)
#define hyTransUartOne() { servoSweepTick(); if( hyTransUart() ) { watch_dog_cnt++; } }
#else
#define hyTransUartOne() { if( hyTransUart() ) { watch_dog_cnt++; } }
#endif

#endif