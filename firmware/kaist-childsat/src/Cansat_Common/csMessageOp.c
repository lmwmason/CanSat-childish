//////////////////////////////////////////////////////////
// MSG Main Operation
// 1. UART Mode Set
// 2. SubModule Data Get From PL
// 3. SubModule Data Send To GS
// Data Request

void hyCANSAT_MSG_OPERATION(unsigned char iRxMode)
{
	msg_recv_flag = 0;    // Rx Ready Set
	hyRxMode_Set(iRxMode);// Communication Mode, Baud, Port Setting
	hyTransUartUntil(&msg_recv_flag, 0, WAIT_CNT_MSG); // wait Message Rx
	hyTransUartWait(WAIT_CNT_SEND);                    // wait Message Tx
}

void hyCANSAT_MSG_OPERATION_WITH_UNIT_RX_SET(unsigned char iRxMode,unsigned short iBaudType, unsigned char iRxPort)
{
	msg_recv_flag = 0;                                 // Rx Ready Set
	hyRxMode_Set_Direct(iRxMode,iBaudType,iRxPort);    // Communication Mode, Baud, Port Set Directly
	hyTransUartUntil(&msg_recv_flag, 0, WAIT_CNT_MSG); // wait Message Rx
	hyTransUartWait(WAIT_CNT_SEND);                    // wait Message Tx
}


// 56 00 48 00 ID CMD XOR //
void hySendSetCmd_To_Unit(unsigned char id, unsigned char cmd)
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x48);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(id);
	Pl_Tx_QueueIn(cmd);
	Pl_Tx_QueueIn(id ^ cmd);
}

// Data Request for Every UNITs and Receive Data 
void hyCANSAT_MSG_OPERATION_WITH_UNIT(unsigned char iRxMode)
{
	msg_recv_flag = 0;
	hyRxMode_Set(iRxMode);
	for (unsigned char id = 0; id < 8; id++)
	{
		hySendSetCmd_To_Unit(64 + id, cansat_byte_cmd[id]);
		hyTransUartWait(WAIT_CNT_SEND);
	}
	hyTransUartUntil(&msg_recv_flag, 0, WAIT_CNT_MSG);
	hyTransUartWait(WAIT_CNT_SEND);
}

// add 2021.07.01 for use multiple id //
void hyCANSAT_MSG_OPERATION_WITH_UNIT_ID(unsigned char iRxMode, unsigned char iId)
{
	msg_recv_flag = 0;
	hyRxMode_Set(iRxMode);

	hySendSetCmd_To_Unit(64 + iId, cansat_byte_cmd[iId]);
	hyTransUartWait(WAIT_CNT_SEND);

	hyTransUartUntil(&msg_recv_flag, 0, WAIT_CNT_MSG);
	hyTransUartWait(WAIT_CNT_SEND);
}

// add 2022.06.27 for use multiple id //
//inline void hyRxMode_Set_Direct(unsigned char iRxMode, unsigned char iBaudType, unsigned char iRxPort)

void hyCANSAT_MSG_OPERATION_WITH_UNIT_TX_SET(unsigned char iRxMode, unsigned short iBaudType, unsigned char iRxPort, unsigned char iCmdId)
{
	// When Rx done :: msg_recv_flag is change 
	msg_recv_flag = 0;

	// Communication Mode, Baud, Port Set Directly
	hyRxMode_Set_Direct(iRxMode,iBaudType,iRxPort);

	// Send iCmdId Ref Values to UNIT
	hySendSetCmd_To_Unit(64 + iCmdId, cansat_byte_cmd[iCmdId]);
	hyTransUartWait(WAIT_CNT_SEND);

	// wait msg_rec_flag is not 0 ( or  WAIT_CNT_MSG Counts )
	hyTransUartUntil(&msg_recv_flag, 0, WAIT_CNT_MSG);
	hyTransUartWait(WAIT_CNT_SEND);
}

#define DDR_VAL_M4 0xFE
#define DDR_VAL_M5 0xFC
#define DDR_VAL_M6 0xFD
#define DDR_VAL_M7 0xF7


void hyCANSAT_M4_OPERATION() { DDRA = DDR_VAL_M4; hyCANSAT_MSG_OPERATION(RxMode_M4); }
void hyCANSAT_M5_OPERATION() { DDRA = DDR_VAL_M5; hyCANSAT_MSG_OPERATION(RxMode_M5); }
void hyCANSAT_M6_OPERATION() { DDRA = DDR_VAL_M6; hyCANSAT_MSG_OPERATION(RxMode_M6); }
void hyCANSAT_M7_OPERATION() { DDRA = DDR_VAL_M7; hyCANSAT_MSG_OPERATION(RxMode_M7); }

void hyCANSAT_M4_OPERATION_WITH_UNIT() { DDRA = DDR_VAL_M4; hyCANSAT_MSG_OPERATION_WITH_UNIT(RxMode_M4); }
void hyCANSAT_M5_OPERATION_WITH_UNIT() { DDRA = DDR_VAL_M5; hyCANSAT_MSG_OPERATION_WITH_UNIT(RxMode_M5); }
void hyCANSAT_M6_OPERATION_WITH_UNIT() { DDRA = DDR_VAL_M6; hyCANSAT_MSG_OPERATION_WITH_UNIT(RxMode_M6); }
void hyCANSAT_M7_OPERATION_WITH_UNIT() { DDRA = DDR_VAL_M7; hyCANSAT_MSG_OPERATION_WITH_UNIT(RxMode_M7); }

// This is for multi unit 
void hyCANSAT_M4_OPERATION_WITH_UNIT_ID(unsigned char iId) { DDRA = DDR_VAL_M4; hyCANSAT_MSG_OPERATION_WITH_UNIT_ID(RxMode_M4, iId); }
void hyCANSAT_M5_OPERATION_WITH_UNIT_ID(unsigned char iId) { DDRA = DDR_VAL_M5; hyCANSAT_MSG_OPERATION_WITH_UNIT_ID(RxMode_M5, iId); }
void hyCANSAT_M6_OPERATION_WITH_UNIT_ID(unsigned char iId) { DDRA = DDR_VAL_M6; hyCANSAT_MSG_OPERATION_WITH_UNIT_ID(RxMode_M6, iId); }
void hyCANSAT_M7_OPERATION_WITH_UNIT_ID(unsigned char iId) { DDRA = DDR_VAL_M7; hyCANSAT_MSG_OPERATION_WITH_UNIT_ID(RxMode_M7, iId); }

// Unit Operation with Sending iCmdId ==> 
// Send iCmdId Ref Values  To UNIT,
// Receive Data From UNIT 
void hyCANSAT_Mx_OPERATION_WITH_UNIT_TX_SET(unsigned char iMid,unsigned char iBaudType, unsigned char iCmdId)
{
	switch(iMid) 
	{
		case 4 : DDRA = DDR_VAL_M4; hyCANSAT_MSG_OPERATION_WITH_UNIT_TX_SET(RxMode_M4,iBaudType,RxMode_M4_PORT,iCmdId); break; 
		case 5 : DDRA = DDR_VAL_M5; hyCANSAT_MSG_OPERATION_WITH_UNIT_TX_SET(RxMode_M5,iBaudType,RxMode_M5_PORT,iCmdId); break; 
		case 6 : DDRA = DDR_VAL_M6; hyCANSAT_MSG_OPERATION_WITH_UNIT_TX_SET(RxMode_M6,iBaudType,RxMode_M6_PORT,iCmdId); break; 
		case 7 : DDRA = DDR_VAL_M7; hyCANSAT_MSG_OPERATION_WITH_UNIT_TX_SET(RxMode_M7,iBaudType,RxMode_M7_PORT,iCmdId); break; 
	}
}

// Wait Data Receive 
void hyCANSAT_Mx_OPERATION_WITH_UNIT_RX_SET(unsigned char iMid,unsigned char iBaudType)
{
	switch(iMid) 
	{
		case 4 : DDRA = DDR_VAL_M4; hyCANSAT_MSG_OPERATION_WITH_UNIT_RX_SET(RxMode_M4,iBaudType,RxMode_M4_PORT); break; 
		case 5 : DDRA = DDR_VAL_M5; hyCANSAT_MSG_OPERATION_WITH_UNIT_RX_SET(RxMode_M5,iBaudType,RxMode_M5_PORT); break; 
		case 6 : DDRA = DDR_VAL_M6; hyCANSAT_MSG_OPERATION_WITH_UNIT_RX_SET(RxMode_M6,iBaudType,RxMode_M6_PORT); break; 
		case 7 : DDRA = DDR_VAL_M7; hyCANSAT_MSG_OPERATION_WITH_UNIT_RX_SET(RxMode_M7,iBaudType,RxMode_M7_PORT); break; 
	}
}
