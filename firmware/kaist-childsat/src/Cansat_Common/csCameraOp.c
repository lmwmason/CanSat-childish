// update : 20240804 : hyTransUartUntilAnd added

// Camera Main Functions
// 1. Camera STOP
// 2. Camera TAKE
// 3. Camera Image Size Request
// 4. Rx Camera Image Data 
// 5. Tx Camera Image to GS 
// 6. WHen Error, Camera Initialize 
#if 0
void hyCANSAT_CAMERA_OPERATION()
{
	if (IS_NEED_ICMD(ICMD_MASK_CAMERA_RESET)) // When Need Camera Reset //
	{
		CLEAR_ICMD(ICMD_MASK_CAMERA_RESET);
		hyRxMode_Set(RxMode_CAMERA);
		hyCamera_PictureSize(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		hyCamera_Reset_Set(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
	}
	else // only camera operation
	{
		Get_GsConnected();
		img_recv_flag = 0;
		//		hyRxMode_Set(RxMode_CAMERA)	 ; hyCamera_Stop()        ; hyTransUartWait(WAIT_CNT_CAMERA_STEP) ;
		hyRxMode_Set(RxMode_CAMERA); hyCamera_Take(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		hyRxMode_Set(RxMode_CAMERA_SIZE); hyCamera_Size(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		hyRxMode_Set(RxMode_CAMERA_IMAGE); hyCamera_ImageGet(0, 0, hyCameraImageSize[0], hyCameraImageSize[1]);
	#if 1	
		hyTransUartUntil(&img_recv_flag, 0, WAIT_CNT_CAMERA_IMAGE);
	#else
		hyTransUartUntilAnd(&img_recv_flag, 0, &GS_CONNECT_STATE, 1, WAIT_CNT_CAMERA_IMAGE);
    #endif
		if ((img_recv_flag == 0))	// when not receive image 
		{
			hyRxMode_Set(RxMode_CAMERA); hyCamera_Init(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		}
		hyTransUartWait(WAIT_CNT_SEND);
		//		hyRxMode_Set(RxMode_CAMERA)	 ; hyCamera_Stop(); hyTransUartWait(WAIT_CNT_CAMERA_STEP) ;
		hyRxMode_Set(RxMode_CAMERA); hyCamera_Resume(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		//		hyRxMode_Set(RxMode_CAMERA)	 ; hyCamera_Osd_Add_Char("cansat")        ; hyTransUartWait(WAIT_CNT_CAMERA_STEP) ;
	}
}

#else

// Image Size is Too Big
// Splite the Image Area 
// if needed send with some image Block ( Chunk )  size 
//#ifndef CAMERA_ONE_BLOCK_SIZE 
//#define CAMERA_ONE_BLOCK_SIZE 0x80
//#endif

//void hyCANSAT_CAMERA_OPERATION_WITH_IMG_BLOCK()
void hyCANSAT_CAMERA_OPERATION()
{
	if (IS_NEED_ICMD(ICMD_MASK_CAMERA_RESET)) // When Need Camera Reset //
	{
		CLEAR_ICMD(ICMD_MASK_CAMERA_RESET);
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyRxMode_Set(RxMode_CAMERA);
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyCamera_PictureSize(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyCamera_Reset_Set(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
	}
	else // only camera operation
	{
		img_recv_flag = 0;
		//		hyRxMode_Set(RxMode_CAMERA)	 ; hyCamera_Stop()        ; hyTransUartWait(WAIT_CNT_CAMERA_STEP) ;
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyRxMode_Set(RxMode_CAMERA); hyCamera_Take(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyRxMode_Set(RxMode_CAMERA_SIZE); hyCamera_Size(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyRxMode_Set(RxMode_CAMERA_IMAGE_BLOCK);
		TX_CAMERA_BYTE_IN_TX_BUFF();
		// USE BLOCK SIZE == 128 //

		unsigned short cam_img_size = 0;
		cam_img_size  = hyCameraImageSize[0];  cam_img_size <<= 8;
		cam_img_size += hyCameraImageSize[1];
		for (unsigned short addr_s = 0; addr_s < cam_img_size; addr_s += CAMERA_ONE_BLOCK_SIZE)
		{
			Get_GsConnected(); 
			img_recv_part_flag = 0; 
			TX_CAMERA_BYTE_IN_TX_BUFF();
			unsigned char addr_0 = (addr_s >> 8) & 0xFF;
			unsigned char addr_1 = (addr_s & 0xFF);
			unsigned short cam_img_left = cam_img_size - addr_s;
			if (CAMERA_ONE_BLOCK_SIZE < cam_img_left) cam_img_left = CAMERA_ONE_BLOCK_SIZE;
			unsigned char left_0 = (cam_img_left >> 8) & 0xFF;
			unsigned char left_1 = (cam_img_left & 0xFF);
			hyCamera_ImageGet(addr_0, addr_1, left_0, left_1);
			hyTransUartUntil(&img_recv_part_flag, 0, WAIT_CNT_CAMERA_STEP);
			// if ((addr_s & 0x00FF) == 0x00FF) { delay(1); }
		}
		
		if ((img_recv_part_flag == 0))	// when not receive image 
		{
			hyRxMode_Set(RxMode_CAMERA); hyCamera_Init(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		}
		hyTransUartWait(WAIT_CNT_SEND);
		//		hyRxMode_Set(RxMode_CAMERA)	 ; hyCamera_Stop(); hyTransUartWait(WAIT_CNT_CAMERA_STEP) ;
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyRxMode_Set(RxMode_CAMERA);
		TX_CAMERA_BYTE_IN_TX_BUFF(); hyCamera_Resume(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
		//		hyRxMode_Set(RxMode_CAMERA)	 ; hyCamera_Osd_Add_Char("cansat")        ; hyTransUartWait(WAIT_CNT_CAMERA_STEP) ;
	}
}
#endif


void hyCANSAT_CAMERA_NO_OPERATION()
{
	hyRxMode_Set(RxMode_CAMERA); hyCamera_Stop(); hyTransUartWait(WAIT_CNT_CAMERA_STEP);
}


// 카메라 포트 설정 및 GS
void hyCANSAT_CAMERA_TOGGLE_PORT()
{
	// Toggle Port //
	RxMode_CAMERA_PORT = (RxMode_CAMERA_PORT == RxMode_CAMERA_0_PORT) ? RxMode_CAMERA_1_PORT : RxMode_CAMERA_0_PORT;
	if (RxMode_CAMERA_PORT == RxMode_CAMERA_0_PORT)
	{
		hyCANSAT_Gs_Tx_Message(0, "CAMERA_0");
	}
	else
	{
		DDRA = 0xFE; // DDRA SETTING
		hyCANSAT_Gs_Tx_Message(0, "CAMERA_1");
	}
}
