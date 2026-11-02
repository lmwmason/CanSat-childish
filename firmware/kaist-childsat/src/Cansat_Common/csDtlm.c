// DTLM Processing Functions
// 1. Flag Toggle
// 2. PORT : Data Set

void hyDTlm_OP()
{
	TOGGLE_ICMD(ICMD_MASK_SIGN);
	// User can Change the below code 

	unsigned char pf = PINF;        // analog data status get
	cansat_dcmd_3 = 0;
	if (pf & 0x01) cansat_dcmd_3 |= 0x80;
	if (pf & 0x02) cansat_dcmd_3 |= 0x40;
	if (pf & 0x04) cansat_dcmd_3 |= 0x20;
	if (pf & 0x08) cansat_dcmd_3 |= 0x10;
	if (pf & 0x10) cansat_dcmd_3 |= 0x08;
	if (pf & 0x20) cansat_dcmd_3 |= 0x04;
	if (pf & 0x40) cansat_dcmd_3 |= 0x02;
	if (pf & 0x80) cansat_dcmd_3 |= 0x01;

	PORTA = cansat_dcmd_1; // digital setting 
}

// DTLM Tx to GS 
#if 0 // OLD VERSION
// 76 00 48 [02] DTLM(2)  CS(1)  //
void hyDTlm_Send()
{
	Gs_Tx_QueueIn(0x76);
	Gs_Tx_QueueIn(0x00);
	Gs_Tx_QueueIn(0x48);
	Gs_Tx_QueueIn(0x02);
	Gs_Tx_QueueIn(cansat_dcmd_0);
	Gs_Tx_QueueIn(cansat_dcmd_1);
	Gs_Tx_QueueIn((cansat_dcmd_0 ^ cansat_dcmd_1));
}
#else // new version
// 76 00 48 [04] DTLM(4)  CS(1)  //
void hyDTlm_Send()
{
	Gs_Tx_QueueIn(0x76);
	Gs_Tx_QueueIn(0x00);
	Gs_Tx_QueueIn(0x48);
	Gs_Tx_QueueIn(0x04);
	Gs_Tx_QueueIn(cansat_dcmd_0);
	Gs_Tx_QueueIn(cansat_dcmd_1);
	Gs_Tx_QueueIn(cansat_dcmd_2);
	Gs_Tx_QueueIn(cansat_dcmd_3);
	Gs_Tx_QueueIn((cansat_dcmd_0 ^ cansat_dcmd_1 ^ cansat_dcmd_2 ^ cansat_dcmd_3));
}
#endif