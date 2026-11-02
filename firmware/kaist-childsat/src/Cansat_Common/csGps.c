// GPS Rx Data Processing
// One Byte Input Processing 
// $GPGGA Protocol Processing
// $GNGGA Protocol Processing
////////////////////////////////////////////////
// $GPRMC,112320.000,A,3622.3375,N,12721.9571,E,0.03,0.00,010212,,,D*61
// $GPGGA,HHMMSS.000,.....      
//unsigned char gps_data[96];
//unsigned char gps_data_idx = 0;
//unsigned char gps_recv_flag = 0;
//unsigned long gps_time_t0 = 0;
//unsigned long gps_time_t1 = 0;

void hyGps_RecvByte(unsigned char b)
{
	unsigned char csum_gps, csum_high, csum_low;
	if (b == '$')
	{
		gps_data[0] = b;
		gps_data_idx = 1;
		gps_data[gps_data_idx] = 0;
	}
	else if (0 < gps_data_idx && gps_data_idx < 94)
	{
		if (b == '\n' || b == '\a')	// when receive the GPSR DATA //
		{

			if (gps_data[0] == '$')
			if (gps_data[1] == 'G')
			if (gps_data[2] == 'P' || gps_data[2] == 'N')
			if (gps_data[3] == 'G')
			if (gps_data[4] == 'G')
			if (gps_data[5] == 'A')
			if (gps_data[6] == ',')
			{
				gps_recv_flag = 1;
				Gs_Tx_QueueIn(0x76);
				Gs_Tx_QueueIn(0x00);
				Gs_Tx_QueueIn(0x58);
				Gs_Tx_QueueIn(0x00);
				Gs_Tx_QueueIn(gps_data[0]);
				csum_gps = 0;
				unsigned char idx;
				for (idx = 1; idx < gps_data_idx && gps_data[idx] != '*'; idx++)
				{
					Gs_Tx_QueueIn(gps_data[idx]);
					csum_gps ^= gps_data[idx];
				}
				for (; idx < gps_data_idx; idx++)
				{
					Gs_Tx_QueueIn(gps_data[idx]);
				}
				// add csum
				Gs_Tx_QueueIn('*');
				csum_high = (csum_gps >> 4) & 0x0F;
				csum_low = csum_gps & 0x0F;

				csum_high += (csum_high < 10) ? '0' : 'a' - 10;
				csum_low += (csum_low < 10) ? '0' : 'a' - 10;

				Gs_Tx_QueueIn(csum_high);	//   add for csum
				Gs_Tx_QueueIn(csum_low);	//   add for csum


				Gs_Tx_QueueIn(0x0D);
				Gs_Tx_QueueIn(0x0A);

				hyLOG_GPS_DATA(); // use gps_data, gps_data_idx 

				// init gps data
				gps_data_idx = 0;
				gps_data[0] = 0;

				gps_time_t0 = gps_data[7] - '0';	gps_time_t1 = gps_time_t0 * 36000;
				gps_time_t0 = gps_data[8] - '0';	gps_time_t1 += gps_time_t0 * 3600;
				gps_time_t0 = gps_data[9] - '0';	gps_time_t1 += gps_time_t0 * 600;
				gps_time_t0 = gps_data[10] - '0';	gps_time_t1 += gps_time_t0 * 60;
				gps_time_t0 = gps_data[11] - '0';	gps_time_t1 += gps_time_t0 * 10;
				gps_time_t0 = gps_data[12] - '0';	gps_time_t1 += gps_time_t0;
				time_sec = gps_time_t1;
			}
		}
		else
		{
			gps_data[gps_data_idx] = b;
			gps_data_idx++;
			gps_data[gps_data_idx] = 0;
		}
	}
	else
	{
		gps_data[0] = 0;
		gps_data_idx = 0;
	}
}

