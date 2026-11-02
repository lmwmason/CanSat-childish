// IMU Rx Data Processing 
// One Byte Rx Data Processing 
// [[*...\n\a]] Protocol Processing 
////////////////////////////////////////////////
// * .... /a/d
// each 6 bytes or 7 bytes
// 7 bytes x 10 tiems == 70 bytes...
////////////////////////////////////////////////

//#define IMU_DATA_RETRY_CNT 3
//#define IMU_DATA_SIZE 128
//unsigned char imu_data[IMU_DATA_SIZE];
//unsigned char imu_data_idx = 0;
//unsigned char imu_recv_flag = 0;
//unsigned char roll  = 0 ;
//unsigned char pitch = 0 ;
//unsigned char yaw   = 0 ; 
//unsigned char v_sign = 0; unsigned char v_sign_0 = 0; unsigned char v_sign_1 = 0; unsigned char v_sign_2 = 0;
//unsigned char v_value = 0; unsigned char v_value_0 = 0; unsigned char v_value_1 = 0; unsigned char v_value_2 = 0;
//unsigned char v_roll = 0;

void hyImu_RecvByte(unsigned char b)
{
    static unsigned char imu_i_state = 0;
    unsigned char csum_imu, csum_high, csum_low;
    unsigned char idx_0, idx_1;
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

                    if (imu_i_state == 0)
                    {
                        imu_recv_flag = 1;
                        hyLOG_IMU_DATA();

                        v_sign = FILTER_MID_3(v_sign_0, v_sign_1, v_sign_2);
                        v_value = FILTER_MID_3(v_value_0, v_value_1, v_value_2);
                    }

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

                    //// set the value //
//                                      sscanf((const char*)&imu_data[1],"%f,%f,%f",&roll, &pitch, &yaw ) ;  //
// roll  : -180 ~ 180
// pitch :  -90 ~ 90 
// yaw   : -180 ~ 180  ==> 

#if 1
// when roll is -90 to 90 else ...
                                        // Receive Data Processing // 
                    {
                        v_value_2 = v_value_1;
                        v_value_1 = v_value_0;
                        v_sign_2 = v_sign_1;
                        v_sign_1 = v_sign_0;

                        idx_0 = 1;
                        { // for roll srrrr.rr,
                            if (imu_data[idx_0] == '-') { v_sign = 25; idx_0++; }
                            else { v_sign = 0; } // _srrrr.rr,
                            idx_1 = idx_0;

                            while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != '.' && imu_data[idx_0]) idx_0++; //  srrrr_.rr,

                            v_roll = 0;
                            for (; idx_1 < idx_0; idx_1++)
                                if ('0' <= imu_data[idx_1] && imu_data[idx_1] <= '9')
                                    v_roll = v_roll * 10 + (imu_data[idx_1] - '0');

                            while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != ',' && imu_data[idx_0]) idx_0++;  // srrrr.rr_,
                            if (imu_data[idx_0] == ',') idx_0++;// 1 (,)  srrrr.rr
                        }

                        while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != ',' && imu_data[idx_0]) idx_0++; if (imu_data[idx_0] == ',') idx_0++;// 2 (,)  spppp.pp

                        { // for yaw
                            if (imu_data[idx_0] == '-') { v_sign_0 = 180; idx_0++; }
                            else v_sign_0 = 0;

                            idx_1 = idx_0;

                            while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != '.' && imu_data[idx_0]) idx_0++; // 3 (.) syyyy.yy

                            v_value_0 = 0;
                            for (; idx_1 < idx_0; idx_1++)
                                if ('0' <= imu_data[idx_1] && imu_data[idx_1] <= '9')
                                    v_value_0 = v_value_0 * 10 + (imu_data[idx_1] - '0');
                            // -180 ~ 180 ==> 0 ~ 180 mapping 
                            // 1. -180 to  -0 ==> 0 to 180 and  0 to 180 ==> 0 to 180 
                            // 2. -90 to 90   ==> 0 to 180 and  0 to 180 ==> 0 to 180 
#if 0                                            
                            if (0 <= v_value_0 && v_value_0 <= 90)
                            {
                                if (v_sign_0 == 0) v_value_0 = v_value_0 + 90; // 0 to 90    ==> 90 to 180
                                else                v_value_0 = 90 - v_value_0; // -90 to 0   ==>  0 to  90
                            }
                            else
                            {
                                if (v_sign_0 == 0) v_value_0 = (180 - v_value_0) + 90; //  90 to  180  ==>   180 to 90
                                else                v_value_0 = v_value_0 - 90; // -180 to -90  ==>   90  to  0
                            }
#else                                            
                            if (v_sign_0 != 0) v_value_0 = 180 - v_value_0;
#endif
                            if (90 < v_roll) { v_value_0 = 180 - v_value_0; }
                        }
                    }
#else                                       
                    idx_0 = 1;
                    while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != ',' && imu_data[idx_0]) idx_0++; if (imu_data[idx_0] == ',') idx_0++;// 1 (,)  srrrr.rr
#if 1  // when only use yaw                                      
                    while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != ',' && imu_data[idx_0]) idx_0++; if (imu_data[idx_0] == ',') idx_0++;// 2 (,)  spppp.pp

                    { // for yaw
                        if (imu_data[idx_0] == '-') { v_sign = 180; idx_0++; }
                        else v_sign = 0;

                        idx_1 = idx_0;

                        while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != '.' && imu_data[idx_0]) idx_0++; // 3 (.) syyyy.yy

                        v_value = 0;
                        for (; idx_1 < idx_0; idx_1++)
                            if ('0' <= imu_data[idx_1] && imu_data[idx_1] <= '9')
                                v_value = v_value * 10 + (imu_data[idx_1] - '0');
                        //                                         if( v_sign == 0 ) v_value = 180 - v_value ; // when reverse mode //
                        if (v_sign != 0) v_value = 180 - v_value;

                    }
#else // when pitch is + v_sign = 0, else v_sign = 25 //
                    { // for pitch
                        if (imu_data[idx_0] == '-') { v_sign = 180; idx_0++; }
                        else { v_sign = 0; }
                        while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != ',' && imu_data[idx_0]) idx_0++; if (imu_data[idx_0] == ',') idx_0++;// 2 (,)  spppp.pp
                    }

                    { // for yaw
                        if (imu_data[idx_0] == '-') // when yaw is - direction
                        {
                            v_sign = (v_sign == 0) ? 180 : 0;
                            idx_0++;
                        }
                        idx_1 = idx_0;

                        while (idx_0 < IMU_DATA_SIZE && imu_data[idx_0] != '.' && imu_data[idx_0]) idx_0++; // 3 (.) syyyy.yy

                        v_value = 0;
                        for (; idx_1 < idx_0; idx_1++)
                            if ('0' <= imu_data[idx_1] && imu_data[idx_1] <= '9')
                                v_value = v_value * 10 + (imu_data[idx_1] - '0');
                        //                                         if( v_sign == 0 ) v_value = 180 - v_value ; // when reverse mode //
                        if (v_sign != 0) v_value = 180 - v_value;

                    }
#endif
#endif                                        
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

