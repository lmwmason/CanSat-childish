// ATLM Main Functions
// 1. UART Rx Mode Set
// 2. ATLM 8 item Get
// 3. DHT11 Data Get
// 4. ATLM Tx
void hyCANSAT_DHT11_to_ATLM_OPERATION()
{
	hyRxMode_Set(RxMode_ATLM); hyTransUartWait(WAIT_CNT_ATLM);
	//	for( unsigned char step = 0 ; step < 8 ; step++ )
	for (unsigned char step = 0; step < 8; step++) // 3 times run
	{
		hyATlm_Get();
		hyTransUartWait(WAIT_CNT_ATLM);
	}
	// append DHT11 Data 
	hy_DHT11_To_ATlm_Get(); 
	hyATlm_Send();
	hyTransUartWait(WAIT_CNT_SEND);
	hyLOG_ATLM_DATA();
}
