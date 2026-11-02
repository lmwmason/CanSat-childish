// update : 20240804 : hyTransUartUntilAnd added

//unsigned short watch_dog_cnt = 0;
//unsigned char hyTransUart();
//void hyTransUartWait(unsigned long cnt);
//void hyTransUartUntil(unsigned char* flag, unsigned char value, unsigned long cnt);


// UART Communication Main Operation
// 1. Pl_Rx_Queue (PL to Cansat Processing with Mode )
// 2. Gs_Rx_Queue (Gs to Cansat Processing)
// 3. Gs_Tx_Queue (Cansat to Gs Processing)
// 4. Pl_Tx_Queue (Cansat to PL Processing)
unsigned char hyTransUart()
{
	unsigned char b;
	unsigned char worked = 0;

	// Pl_Rx ==> Gs_Tx
	if (PL_PORT.available()) { Pl_Rx_QueueIn(PL_PORT.read()); } // When no interrupt processing ... 

	if (Pl_Rx_QueueIsNotEmpty())
	{
		worked = 1;
		Pl_Rx_QueueOut(b);

		switch (hyRxMode)
		{
			case RxMode_CAMERA            :  Gs_Tx_QueueIn(b); break;
			case RxMode_CAMERA_SIZE       :  Gs_Tx_QueueIn(b); hyCamera_Receive_Size(b);  break;
			case RxMode_CAMERA_IMAGE      :  if( Is_GsConnected() ) Gs_Tx_QueueIn(b); hyCamera_Receive_Image(b);  break;
			case RxMode_CAMERA_IMAGE_BLOCK:  if( Is_GsConnected() ) Gs_Tx_QueueIn(b); hyCamera_Receive_Image_Part(b);  break;
			case RxMode_GPS: hyGps_RecvByte(b); break;
			case RxMode_IMU: hyImu_RecvByte(b); break;
			case RxMode_M4:  hyMsg_RecvByte(b); break;
			case RxMode_M5:  hyMsg_RecvByte(b); break;
			case RxMode_M6:  hyMsg_RecvByte(b); break;
			case RxMode_M7:  hyMsg_RecvByte(b); break;

			default:  Gs_Tx_QueueIn(b); break;
		}
	}

	//	if( GS_PORT.available() ) { Gs_Rx_QueueIn(PL_PORT.read()); } // When no interrupt processing ...  // use interrupt OK ..
		// Gs_Rx ==> Pl_Tx
	if (Gs_Rx_QueueIsNotEmpty())
	{
		worked = 1;
		Gs_Rx_QueueOut(b);
		hyGs_RecvByte(b);
	}

	// Gs_Tx ==> Gs_Tx PORT
	if (Gs_Tx_QueueIsNotEmpty())
	{
		worked = 1;
		Gs_Tx_QueueOut(b);
		// hyGsTxByte(b);
		TX_CAMERA_BYTE(b);
	}

	if (Gs_Tx_Frame_QueueIsNotEmpty())
	{
		worked = 1;
		Gs_Tx_Frame_QueueOut(b);
		hyGsTxByte(b);
	}

	// Pl_Tx ==> Pl_Tx PORT
	if (Pl_Tx_QueueIsNotEmpty())
	{
		worked = 1;
		Pl_Tx_QueueOut(b);
		hyPlTxByte(b);
	}
	return worked; // 0 means do nothing  //
}

// 1 time communication processing 
//#define hyTransUartOne() { if( hyTransUart() ) { watch_dog_cnt++; } }

// processing cnt times 
void hyTransUartWait(unsigned long cnt)
{
	for (unsigned long loop_cnt = 0; loop_cnt < cnt; loop_cnt++)
		hyTransUartOne();
}

// special 1 signal duration and cnt times processing 
void hyTransUartUntil(unsigned char* flag, unsigned char value, unsigned long cnt)
{
	for (unsigned long loop_cnt = 0; loop_cnt < cnt && *flag == value; loop_cnt++)
		hyTransUartOne();
}

// specital 2 signal duration and cnt times processing 
void hyTransUartUntilAnd(unsigned char* flag0, unsigned char value0, unsigned char *flag1, unsigned char value1, unsigned long cnt)
{
	for (unsigned long loop_cnt = 0; loop_cnt < cnt && *flag0 == value0 && *flag1 == value1 ; loop_cnt++)
		hyTransUartOne();
}
