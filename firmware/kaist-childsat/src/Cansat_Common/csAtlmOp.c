// ATLM Main Function
// 1. UART Rx Mode Set
// 2. ATLM 8 items Get
// 3. ATLM Send
void hyCANSAT_ATLM_OPERATION()
{
	hyRxMode_Set(RxMode_ATLM); hyTransUartWait(WAIT_CNT_ATLM);
	//	for( unsigned char step = 0 ; step < 8 ; step++ )
	for (unsigned char step = 0; step < 8; step++) // 3 times run
	{
		hyATlm_Get();
		hyTransUartWait(WAIT_CNT_ATLM);
	}
	hyATlm_Send();
	hyTransUartWait(WAIT_CNT_SEND);
	hyLOG_ATLM_DATA();
}
