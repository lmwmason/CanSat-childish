// DTLM Main Operation 
// 1. DTLM Setting 
// 2. UART Receive Mode Set
// 3. DTLM Send to GS
// 4. need FLAG OFF 
void hyCANSAT_DTLM_OPERATION()
{
	hyDTlm_OP();
	hyRxMode_Set(RxMode_DTLM); hyTransUartWait(WAIT_CNT_ATLM);
	hyDTlm_Send();             hyTransUartWait(WAIT_CNT_SEND);

	hyLOG_DTLM_DATA();

	CLEAR_ICMD(ICMD_MASK_GS);
	//	CLEAR_LED (LED_MASK_GS   );
}
