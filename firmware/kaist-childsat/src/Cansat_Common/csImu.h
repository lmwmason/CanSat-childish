#ifndef _CS_IMU_H_
#define _CS_IMU_H_

//  _USE_IMU_RECV_WITH_VALUE_SET_
// 
// IMU Rx Data Processing 
// One Byte Rx Byte Processing
// [[*...\n\a]] Protocol Processing
////////////////////////////////////////////////
// * .... /a/d
// each 6 ~ 7bytes.
// 7 bytes x 10 items = 70 bytes...
////////////////////////////////////////////////

#define IMU_DATA_SIZE 128
unsigned char imu_data[IMU_DATA_SIZE];
unsigned char imu_data_idx = 0;
unsigned char imu_recv_flag = 0;
void hyImu_RecvByte(unsigned char b);

unsigned char IMU_DATA_RETRY_CNT = 1;
//#define IMU_DATA_RETRY_CNT 1  // normal use
//#define IMU_DATA_RETRY_CNT 3  // filtering use


////// when need imu value /////
unsigned char v_sign = 0;
unsigned char v_sign_0 = 0;
unsigned char v_sign_1 = 0;
unsigned char v_sign_2 = 0;

unsigned char v_value = 0;
unsigned char v_value_0 = 0;
unsigned char v_value_1 = 0;
unsigned char v_value_2 = 0;
///////////////////////////////
unsigned char v_x_roll = 0; 
//short v_x_roll  = 0; 
//short v_y_ptich = 0;
//short v_z_yaw   = 0;

inline void IMU_DATA_RETRY_CNT_SET(unsigned char uc) { IMU_DATA_RETRY_CNT = uc;  }

#endif