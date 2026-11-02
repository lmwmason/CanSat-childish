#ifndef _CS_LOG_H_
#define _CS_LOG_H_

File csLogFile;

char sLogFileName[10];
void hyLOG_FILE_OPEN();
void hyLOG_FILE_CLOSE();
void hyLOG_GPS_DATA();
void hyLOG_IMU_DATA();
void hyLOG_CAMERA_INIT();
void hyLOG_CAMERA_SIZE();
void hyLOG_CAMERA_IMAGE();
void hyLOG_ATLM_DATA();
void hyLOG_DTLM_DATA();
void hyLOG_LIFE_SIGN();

#endif
