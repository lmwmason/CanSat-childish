// IMU Rx Data Processing 
// One Byte Rx Byte Processing
// [[*...\n\a]] Protocol Processing
////////////////////////////////////////////////
// * .... /a/d
// each 6 ~ 7bytes.
// 7 bytes x 10 items = 70 bytes...
////////////////////////////////////////////////
//#define IMU_DATA_SIZE 128
//unsigned char imu_data[IMU_DATA_SIZE];
//unsigned char imu_data_idx = 0;
//unsigned char imu_recv_flag = 0;

#define IMU_DATA_RETRY_CNT 1

void hyImu_RecvByte(unsigned char b)
{
	static unsigned char imu_i_state = 0;
	unsigned char csum_imu, csum_high, csum_low;
	if (b == '*')
	{
		imu_data[0] = b;
		imu_data_idx = 1;
		imu_data[imu_data_idx] = 0;
	}
	else if (0 < imu_data_idx && imu_data_idx < IMU_DATA_SIZE - 2)
	{
		if (b == '\n' || b == '\a')	// when receive the IMU DATA //
		{
			if (imu_data[0] == '*')
			{
				if (imu_i_state == 0)  // remove first data for sync //
				{
					imu_i_state++;
					for (unsigned char i = 0; i < IMU_DATA_SIZE; i++) imu_data[i] = 0;
					imu_data_idx = 0;
				}
				else if (imu_i_state != 0)
				{
					// receive 3rd times //
					imu_i_state = (imu_i_state < IMU_DATA_RETRY_CNT) ? imu_i_state + 1 : 0;
					//					if( imu_i_state == 0 ) imu_recv_flag = 1 ;
					if (imu_i_state == 0) { imu_recv_flag = 1; hyLOG_IMU_DATA(); }

					Gs_Tx_QueueIn(0x76);
					Gs_Tx_QueueIn(0x00);
					Gs_Tx_QueueIn(0x60);
					Gs_Tx_QueueIn(0x00);
					csum_imu = 0;
					for (unsigned char idx = 0; idx < imu_data_idx; idx++)
					{
						Gs_Tx_QueueIn(imu_data[idx]);
						csum_imu += imu_data[idx];
					}
					Gs_Tx_QueueIn(',');				    // , for csum
					csum_high = (csum_imu >> 4) & 0x0F;
					csum_low = csum_imu & 0x0F;

					csum_high += (csum_high < 10) ? '0' : 'a' - 10;
					csum_low += (csum_low < 10) ? '0' : 'a' - 10;

					Gs_Tx_QueueIn(csum_high);	//   add for csum
					Gs_Tx_QueueIn(csum_low);	//   add for csum
					Gs_Tx_QueueIn(0x0D);
					Gs_Tx_QueueIn(0x0A);

					for (unsigned char i = 0; i < IMU_DATA_SIZE; i++) imu_data[i] = 0;
					imu_data_idx = 0;
				}
			}
		}
		else
		{
			imu_data[imu_data_idx] = b;
			imu_data_idx++;
			imu_data[imu_data_idx] = 0;
		}
	}
	else
	{
		imu_data[0] = 0;
		imu_data_idx = 0;
	}
}
