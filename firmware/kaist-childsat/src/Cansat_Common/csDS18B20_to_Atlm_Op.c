// ATLM Main Operation Function
// 1. UART Rx Mode Setting
// 2. ATLM 8 Get
// 3. DS18S20 Data Get
// 4. ATLM Tx
void hyCANSAT_DS18B20_to_ATLM_OPERATION()
{
	hyRxMode_Set(RxMode_ATLM); hyTransUartWait(WAIT_CNT_ATLM);
	//	for( unsigned char step = 0 ; step < 8 ; step++ )
	for (unsigned char step = 0; step < 8; step++) // 3 times run
	{
		hyATlm_Get();
		hyTransUartWait(WAIT_CNT_ATLM);
	}
	// append ds18s20 Data Get
	cli(); // interrupt disable for safe aquisition
	hy_DS18B20_To_ATlm_Get(); // need to wait 1 sec //
	sei(); // interrupt enable 
	hyATlm_Send();
	hyTransUartWait(WAIT_CNT_SEND);
	hyLOG_ATLM_DATA();
}
