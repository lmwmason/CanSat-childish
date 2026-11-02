// 20240804 : gGsConnectState added

// void hyGs_RecvByte(unsigned char b);
// void hyCANSAT_Gs_Tx_Message(unsigned char msg_id, const char* msg);
// void hyCansat_Message(char* msg);


// GS Data Rx Processing 
// One Byte Rx Data Processing
// 56 00 ....... Protocol Processing
// TCMD : 56 00  48 : 00 ID CMD CS
// TIME : 56 00  49 : 00 T0 T1 T2 T3 XOR
/////////////////////////////////////////////////////////////////////////////////////////////
// 56 00 CMD LEN .... 

// BITMAP CMD 
// 40 08 XX XX XX XX XX XX XX XX XX XX XX XX XX XX ( Block(128BYTE) per 1 bit use, 8*16*128 = 16.384  )
// 76 00 40 bidx ....   Tx (will be)         

// DISCONNECT Detecting for BT Communication : 20240804

void hyGs_RecvByte(unsigned char b)
{
	static unsigned char sConnectMode = 0;
	static unsigned char sRecvMode    = 0;
	static unsigned char cRecvCmd[4]  = { 0,0,0,0 };
	static unsigned char cRecvTime[4] = { 0,0,0,0 };
	//unsigned char   tb_0=0                    ;
	//unsigned char   tb_1=0                    ;
//	SET_OP(ICMD_MASK_GS);
	// 56 00 .... 
	switch (sRecvMode)
	{
	case 0x00: sRecvMode = (b == 0x56) ? 0x01 : 0;                     break; // 56
	case 0x01: sRecvMode = (b == 0x00) ? 0x02 : ((b == 0x56) ? 1 : 0); break; // 00
	case 0x02: sRecvMode = (b == 0x48) ? 0x10 : ((b == 0x49) ? 0x20 : ((b == 0x56) ? 1 : 0)); break; // 48	

	case 0x10: sRecvMode = (b == 0x00) ? sRecvMode + 1 : ((b == 0x56) ? 1 : 0); break; // 00
	case 0x11: sRecvMode++; cRecvCmd[0] = b; break; // ID
	case 0x12: sRecvMode++; cRecvCmd[1] = b; break; // SET
	case 0x13: sRecvMode = 0; cRecvCmd[2] = b;        // CSUM
		if (0 <= cRecvCmd[0] && cRecvCmd[0] < 64) // when Digital Bit Command
		{
			if (0 <= cRecvCmd[1] && cRecvCmd[1] <= 1)
			{
				if ((cRecvCmd[0] ^ cRecvCmd[1]) == cRecvCmd[2]) // XOR
				{
					SET_ICMD(ICMD_MASK_GS); SET_LED(LED_MASK_GS);

					if (0 <= cRecvCmd[0] && cRecvCmd[0] < 8) // Operation Flags 
					{
						if (cRecvCmd[1]) 	cansat_dcmd_0 |= MASK_BIT_OR[cRecvCmd[0]];
						else                cansat_dcmd_0 &= ~MASK_BIT_OR[cRecvCmd[0]];
						OP_TO_EEPROM();
					}

					if (8 <= cRecvCmd[0] && cRecvCmd[0] < 16) // Direct Commanding
					{
						if (cRecvCmd[1]) 	cansat_dcmd_1 |= MASK_BIT_OR[cRecvCmd[0] & 0x07];
						else                cansat_dcmd_1 &= ~MASK_BIT_OR[cRecvCmd[0] & 0x07];
						PORTA = cansat_dcmd_1;
					}

					if (16 <= cRecvCmd[0] && cRecvCmd[0] < 24) // Internal Setting Command Processing 
					{
						if (cRecvCmd[1]) 	cansat_dcmd_2 |= MASK_BIT_OR[cRecvCmd[0] & 0x07];
						else                cansat_dcmd_2 &= ~MASK_BIT_OR[cRecvCmd[0] & 0x07];
						// ICMD_TO_EEPROM(); // Don't Save !!!
					}

					if (24 <= cRecvCmd[0] && cRecvCmd[0] < 32) // but not used 
					{
						if (cRecvCmd[1]) 	cansat_dcmd_3 |= MASK_BIT_OR[cRecvCmd[0] & 0x07];
						else                cansat_dcmd_3 &= ~MASK_BIT_OR[cRecvCmd[0] & 0x07];
					}
				}
			}
		}
		else if (64 <= cRecvCmd[0] && cRecvCmd[0] < 64 + 8) // when 8 bit data value
		{
			if ((cRecvCmd[0] ^ cRecvCmd[1]) == cRecvCmd[2]) // XOR
			{
				SET_ICMD(ICMD_MASK_GS); SET_LED(LED_MASK_GS);
				cansat_byte_cmd[cRecvCmd[0] - 64] = cRecvCmd[1];
#if defined(SERVO_TEST_TA) || defined(SERVO_TEST_AT) || defined(SERVO_TEST_DT)
                if (cRecvCmd[0] == 71) servoTrigger(cRecvCmd[1]);
                if (cRecvCmd[0] == 70 && cRecvCmd[1] == 1) btInventoryRequested = true;
#endif
			}
		}
		break;
	case 0x20: sRecvMode = (b == 0x00) ? sRecvMode + 1 : ((b == 0x56) ? 1 : 0); break; // 00
	case 0x21: sRecvMode++; cRecvTime[0] = b; break; // T0
	case 0x22: sRecvMode++; cRecvTime[1] = b; break; // T1
	case 0x23: sRecvMode++; cRecvTime[2] = b; break; // T2
	case 0x24: sRecvMode++; cRecvTime[3] = b; break; // T3
	case 0x25: sRecvMode = 0;       // XOR
				if( (cRecvTime[0] ^ cRecvTime[1] ^ cRecvTime[2] ^ cRecvTime[3]) ==  b ) 
				{
					time_sec  = cRecvTime[0] ;	time_sec <<= 8;
					time_sec += cRecvTime[1] ;	time_sec <<= 8;
					time_sec += cRecvTime[2] ;	time_sec <<= 8;
					time_sec += cRecvTime[3] ;
				}
				else if ( b == 0x56 ) 
					sRecvMode = 1 ; 
				break;
	default: sRecvMode = (b == 0x56) ? 1 : 0; break;
	}

    // 20240804 : sConnectMode added
	switch( sConnectMode )
	{
		case 0x00 : sConnectMode = ( b == 'D' ) ? 0x01 : 0x00 ;  // when assume connect
		            if ( sConnectMode == 0x00 ) SET_GS_CONNECT_STATE(1); 
					break;
		case 0x01 : sConnectMode = ( b == 'I' ) ? 0x02 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x02 : sConnectMode = ( b == 'S' ) ? 0x03 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x03 : sConnectMode = ( b == 'C' ) ? 0x04 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x04 : sConnectMode = ( b == 'O' ) ? 0x05 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x05 : sConnectMode = ( b == 'N' ) ? 0x06 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x06 : sConnectMode = ( b == 'N' ) ? 0x07 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x07 : sConnectMode = ( b == 'E' ) ? 0x08 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x08 : sConnectMode = ( b == 'C' ) ? 0x09 : ( b == 'D' ? 0x01 : 0x00) ; break;
		case 0x09 : sConnectMode = ( b == 'T' ) ? 0x0A : ( b == 'D' ? 0x01 : 0x00) ; // when find DISCONNECT 
					if( sConnectMode == 0x0A  ) SET_GS_CONNECT_STATE(0) ; 
					break;
		case 0x0A : sConnectMode = ( b == 'D' ) ? 0x01 : 0x0B ; break;
		case 0x0B : sConnectMode = ( b == 'D' ) ? 0x01 : 0x0C ; break;
		case 0x0C : sConnectMode = ( b == 'D' ) ? 0x01 : 0x0D ; break;
		case 0x0D : sConnectMode = ( b == 'D' ) ? 0x01 : 0x0E ; break;
		case 0x0E : sConnectMode = ( b == 'D' ) ? 0x01 : 0x0F ; break;
		case 0x0F : sConnectMode = ( b == 'D' ) ? 0x01 : 0x00 ; break;
		default   : sConnectMode = ( b == 'D' ) ? 0x01 : 0x00 ; break;
	}
}

// Send Message from Canst to GS 
void hyCANSAT_Gs_Tx_Message(unsigned char msg_id, const char* msg)
{

	unsigned char msg_len = 0;
	for (msg_len = 0; msg_len < 255 && msg[msg_len]; msg_len++);

	Gs_Tx_QueueIn(0x76);
	Gs_Tx_QueueIn(0x00);
	Gs_Tx_QueueIn(0xA0 + (msg_id & 0x0f));
	Gs_Tx_QueueIn(msg_len);
	for (unsigned char idx = 0; idx < msg_len; idx++)
	{
		Gs_Tx_QueueIn(msg[idx]);
	}
	hyTransUartWait(WAIT_CNT_SEND);
}

// Send Direct Character Message From Cansat to GS 
void hyCansat_Message(const char* msg)
{
	for (unsigned char i = 0; i < 255 && *msg; i++, msg++)
		hyGsTxByte(*msg);
	hyTransUartWait(WAIT_CNT_SEND);
}
