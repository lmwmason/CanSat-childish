#ifndef _CS_GPS_H_
#define _CS_GPS_H_

// GPS Rx Data Processing
// One Byte Data Processing
// $GPGGA Protocol Processing 
// $GNGGA Protocol Processing 
////////////////////////////////////////////////
// $GPRMC,112320.000,A,3622.3375,N,12721.9571,E,0.03,0.00,010212,,,D*61
// $GPGGA,HHMMSS.000,.....      
unsigned char gps_data[96];
unsigned char gps_data_idx = 0;
unsigned char gps_recv_flag = 0;
unsigned long gps_time_t0 = 0;
unsigned long gps_time_t1 = 0;

void hyGps_RecvByte(unsigned char b);

#endif