// SIZE :: when received 76 00 34 00 04 00 00 XX YY //
//unsigned char sCameraReceive_SizeFlag = 0;
//unsigned char hyCameraImageSize[2];


// DATA :: when received 76 00 34 00 04 00 00 XX YY //
void hyCamera_Reset()
{
	Pl_Tx_QueueFlush();
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x26);
	Pl_Tx_QueueIn(0x00);
}

void hyCamera_Reset_Set()
{
	Pl_Tx_QueueFlush();
	hyPlTxByte(0x56);
	hyPlTxByte(0x00);
	hyPlTxByte(0x26);
	hyPlTxByte(0x00);
}


void hyGs_Reset_Reply()
{
	Gs_Tx_QueueIn(0x76);
	Gs_Tx_QueueIn(0x00);
	Gs_Tx_QueueIn(0x26);
	Gs_Tx_QueueIn(0x00);
}


// Sleep 
void hyCamera_Sleep()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x3E);
	Pl_Tx_QueueIn(0x03);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x01);
}

// Wake 
void hyCamera_Wake()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x3E);
	Pl_Tx_QueueIn(0x03);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x00);
}


// Baud 9600 Set
void hyCamera_9600_bps()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x24);
	Pl_Tx_QueueIn(0x03);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0xAE);
	Pl_Tx_QueueIn(0xC8);
}

// Baud 38400 Set
void hyCamera_38400_bps()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x24);
	Pl_Tx_QueueIn(0x03);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x2A);
	Pl_Tx_QueueIn(0xF2);
}

// Baud 115200 Set (Bufferd)
void hyCamera_115200_bps()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x24);
	Pl_Tx_QueueIn(0x03);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x0D);
	Pl_Tx_QueueIn(0xA6);
}

// Baud 115200 Set ( Direct )
void hyCamera_115200_bps_Set()
{
	Pl_Tx_QueueFlush();
	hyPlTxByte(0x56);
	hyPlTxByte(0x00);
	hyPlTxByte(0x24);
	hyPlTxByte(0x03);
	hyPlTxByte(0x01);
	hyPlTxByte(0x0D);
	hyPlTxByte(0xA6);
}

// Image 160 Set 
void hyCamera_160()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x31);
	Pl_Tx_QueueIn(0x05);
	Pl_Tx_QueueIn(0x04);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x19);
	Pl_Tx_QueueIn(0x22);

	WAIT_CNT_CAMERA_IMAGE = WAIT_CNT_CAMERA_IMAGE_160;
}

// Image 320 Set
void hyCamera_320()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x31);
	Pl_Tx_QueueIn(0x05);
	Pl_Tx_QueueIn(0x04);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x19);
	Pl_Tx_QueueIn(0x11);

	WAIT_CNT_CAMERA_IMAGE = WAIT_CNT_CAMERA_IMAGE_320;

}

// Image 640 Set
void hyCamera_640()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x31);
	Pl_Tx_QueueIn(0x05);
	Pl_Tx_QueueIn(0x04);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x19);
	Pl_Tx_QueueIn(0x00);

	WAIT_CNT_CAMERA_IMAGE = WAIT_CNT_CAMERA_IMAGE_640;

}

// Image Stop 
void hyCamera_Stop()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x36);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x03);
}

// Image Take 
void hyCamera_Take()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x36);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x00);
}

// Image Resume 
void hyCamera_Resume()
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x36);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x02);
}

unsigned char Char_to_OSD(char ich)
{
	if ('0' <= ich && ich <= '9') return ich - '0'; // 0  : 10
	if ('A' <= ich && ich <= 'Z') return ich - 'A' + 10; // 10 : 10 + 26      
	if ('a' <= ich && ich <= 'z') return ich - 'a' + 36; // 36 : 10 + 26 + 26 => 62
	switch (ich)
	{
	case '-': return 62;
	case '_': return 63;
	case ':': return 64;
	case '.': return 65;
	case '/': return 66;
	case '*': return 67;
	case '(': return 68;
	case ')': return 69;
	case '[': return 70;
	case ']': return 71;
	case '@': return 72;
	case '!': return 73;
	case '+': return 74;
	case '|': return 75;
	case '\\': return 76;
	case '#': return 77;
	case '=': return 78;
	}
	return 79;
}

#if 0
void hyCamera_Osd_Add_Char(char* istr)
{
	unsigned char slen;  for (slen = 0; slen < 14 && *istr; slen++);
	unsigned char i;
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x45);
	Pl_Tx_QueueIn(slen + 1); // data_length
	Pl_Tx_QueueIn(slen); // chracter number : max 14
	Pl_Tx_QueueIn(0x00); // starting address [x][y] = x 2 bits y 5 bits 
	for (i = 0; i < slen; i++)
		Pl_Tx_QueueIn(Char_to_OSD(istr[i])); // characters
}
#else
void hyCamera_Osd_Add_Char(char* istr)
{
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x45);
	Pl_Tx_QueueIn(0x07); // data_length
	Pl_Tx_QueueIn(0x06); // chracter number : max 14
	Pl_Tx_QueueIn(0x24); // starting address [x][y] = x 2 bits y 5 bits 
	Pl_Tx_QueueIn(0x1F); // characters
	Pl_Tx_QueueIn(0x2C); // characters
	Pl_Tx_QueueIn(0x30); // characters
	Pl_Tx_QueueIn(0x2C); // characters
	Pl_Tx_QueueIn(0x26); // characters
	Pl_Tx_QueueIn(0x35); // characters
	Pl_Tx_QueueIn(0x32); // characters
}
#endif


// Image Size Request 
void hyCamera_Size()
{
	sCameraReceive_SizeFlag = 0;
	Pl_Tx_QueueIn(0x56);
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x34);
	Pl_Tx_QueueIn(0x01);
	Pl_Tx_QueueIn(0x00);
}


// Image Request With Size 
void hyCamera_ImageGet(unsigned char b0, unsigned char b1, unsigned char b2, unsigned char b3)
{
	Pl_Tx_QueueIn(0x56);	
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(0x32);	
	Pl_Tx_QueueIn(0x0C);
	Pl_Tx_QueueIn(0x00);	
	Pl_Tx_QueueIn(0x0A);
	Pl_Tx_QueueIn(0x00);	
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(b0);	    
	Pl_Tx_QueueIn(b1);
	Pl_Tx_QueueIn(0x00);	
	Pl_Tx_QueueIn(0x00);
	Pl_Tx_QueueIn(b2);	    
	Pl_Tx_QueueIn(b3);
	Pl_Tx_QueueIn(0x00);	
	Pl_Tx_QueueIn(0x0A);
}

// Image Size Rx Function 
// When need to receive camera image 
// need to set sCameraImageSize and sCameraReceive_SizeFlag = 1
// Receive : 76 00 34 00 04 00 00 XX YY //
void hyCamera_Receive_Size(unsigned char rx)
{
	static unsigned char sSizeMode = 0;

	switch (sSizeMode)
	{
	case 0:	sSizeMode = (rx == 0x76) ? 1 : 0; break; // 76 
	case 1:	sSizeMode = (rx == 0x00) ? 2 : ((rx == 0x76) ? 1 : 0); break; // 00 
	case 2:	sSizeMode = (rx == 0x34) ? 3 : ((rx == 0x76) ? 1 : 0); break; // 34
	case 3:	sSizeMode = (rx == 0x00) ? 4 : ((rx == 0x76) ? 1 : 0); break; // 00 
	case 4:	sSizeMode = (rx == 0x04) ? 5 : ((rx == 0x76) ? 1 : 0); break; // 04 
	case 5:	sSizeMode = (rx == 0x00) ? 6 : ((rx == 0x76) ? 1 : 0); break; // 00 
	case 6:	sSizeMode = (rx == 0x00) ? 7 : ((rx == 0x76) ? 1 : 0); break; // 00 
	case 7:	hyCameraImageSize[0] = rx; sSizeMode = 8; break; // data 
	case 8:	hyCameraImageSize[1] = rx; sSizeMode = 0;
		sCameraReceive_SizeFlag = 1;
		hyLOG_CAMERA_SIZE(); // 
		break; // data 
	default:	sSizeMode = 0; sCameraReceive_SizeFlag = 0;
	}
}



// Image Data Rx Function 
// When received the end of the image signal 
// set img_recv_flag to 1
// Receive : FF D9 76 00 32 00 //
//unsigned char img_recv_flag = 0;
void hyCamera_Receive_Image(unsigned char rx)
{
	static unsigned char sImageMode = 0;

	switch (sImageMode)
	{
	case 0:	sImageMode = (rx == 0xFF) ? 1 : 0; break; // FF 
	case 1:	sImageMode = (rx == 0xD9) ? 2 : ((rx == 0xFF) ? 1 : 0); break; // D9 
	case 2:	sImageMode = (rx == 0x76) ? 3 : ((rx == 0xFF) ? 1 : 0); break; // 76
	case 3:	sImageMode = (rx == 0x00) ? 4 : ((rx == 0xFF) ? 1 : 0); break; // 00 
	case 4:	sImageMode = (rx == 0x32) ? 5 : ((rx == 0xFF) ? 1 : 0); break; // 32 
	case 5:	sImageMode = (rx == 0x00) ? 6 : ((rx == 0xFF) ? 1 : 0);
		if (rx == 0x00)
		{
			img_recv_flag = 1;
			hyLOG_CAMERA_IMAGE();
		}
		break; // 00 
	default:	sImageMode = 0;
	}
}

// Image Data Receive  ?
// When Receiving the Camera Image 
// 56 SN 32 0C FT CM A0 A1 A2 A3 D0 D1 D2 D3 W0 W1 ==>
// 76 SN 32 00 00 image 76 SN 32 00 00 
void hyCamera_Receive_Image_Part(unsigned char rx)
{
	static unsigned char sImageMode = 0;

	switch (sImageMode)
	{
		case  0:	sImageMode = (rx == 0x76) ? 1 : 0; break;                      // 76 
		case  1:	sImageMode = (rx == 0x00) ? 2 : ((rx == 0x76) ? 1 : 0); break; // 00 
		case  2:	sImageMode = (rx == 0x32) ? 3 : ((rx == 0x76) ? 1 : 0); break; // 32
		case  3:	sImageMode = (rx == 0x00) ? 4 : ((rx == 0x76) ? 1 : 0); break; // 00 
		case  4:	sImageMode = (rx == 0x00) ? 5 : ((rx == 0x76) ? 1 : 0); break; // 00
		case  5:	sImageMode = (rx == 0x76) ? 1 : 6; break; // image start
		case  6:    sImageMode = (rx == 0x76) ? 7 : 6; break; // image // 76
		case  7:	sImageMode = (rx == 0x00) ? 8 : ((rx == 0x76) ? 7 : 6); break; // 00 
		case  8:	sImageMode = (rx == 0x32) ? 9 : ((rx == 0x76) ? 7 : 6); break; // 32
		case  9:	sImageMode = (rx == 0x00) ? 10 : ((rx == 0x76) ? 7 : 6); break; // 00 
		case 10:	sImageMode = (rx == 0x00) ? 0 : ((rx == 0x76) ? 7 : 6);        // 00 // end of frame 
					img_recv_part_flag = (sImageMode == 0);
					break;
		default:    sImageMode = 0; break;
	}
}

// Camera Initialize Functions
// 1. UART0 , UART1 Initialize
// 2. 38400 , 115200 Set
// 3. Camera Reset 
// 4. Camera Image 320 
// 5. Camera Baud  115200 
// 6. Cansat UART0 115200

void hyCamera_PictureSize()
{
	switch ((IS_NEED_OP(OP_MASK_CAMERA_160) << 1) + IS_NEED_OP(OP_MASK_CAMERA_640))
	{
	case 1: hyCamera_640(); break;
	case 2: hyCamera_160(); break;
	case 0:
	case 3:
	default: hyCamera_320(); break;
	}
}

void hyCamera_Init()
{
	volatile unsigned short wait_cnt;
	hyLOG_CAMERA_INIT();

	PL_UART_INIT();
	GS_UART_INIT();

	PL_PORT_SPEED_SET(CAMERA_INIT_BAUD);
	GS_PORT_SPEED_SET(GS_TX_SPEED);

	hyTransUartWait(WAIT_CNT_CAMERA_INIT_STEP);
	hyCamera_Reset();	hyTransUartWait(WAIT_CNT_CAMERA_INIT_STEP);
	hyTransUartWait(WAIT_CNT_CAMERA_INIT_STEP);
	//	hyCamera_PictureSize()   ;	
	hyTransUartWait(WAIT_CNT_CAMERA_INIT_STEP);
	for (unsigned char i = 0; i < 10; i++)
	{
#if CAMERA_BAUD == 9600
		hyCamera_9600_bps();
#elif CAMERA_BAUD == 38400
		hyCamera_38400_bps();
#else
		hyCamera_115200_bps();
#endif     
		hyTransUartWait(WAIT_CNT_CAMERA_INIT_STEP);
	}

	PL_PORT_SPEED_SET(CAMERA_BAUD);

	// hypark : 2013.06.03 appended
	hyCamera_PictureSize();
	hyTransUartWait(WAIT_CNT_CAMERA_INIT_STEP);

	// Added :: SLEEP Mode  //
	// hyCamera_Sleep(); hyTransUartWait(WAIT_CNT_CAMERA_INIT_STEP);

	// Will be Add :: COmpress Mode //
}
