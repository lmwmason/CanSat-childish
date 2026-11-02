//////////////////////////////////////////////////////////
// GPS Main Funtions
// 1. UART Mode Set
// 2. GPS Data Rx from PL
// 3. GPS Data Tx to GS
void hyCANSAT_GPS_OPERATION()
{
	gps_recv_flag = 0;
	hyRxMode_Set(RxMode_GPS);
	hyTransUartUntil(&gps_recv_flag, 0, WAIT_CNT_GPS);
	hyTransUartWait(WAIT_CNT_SEND);
}
