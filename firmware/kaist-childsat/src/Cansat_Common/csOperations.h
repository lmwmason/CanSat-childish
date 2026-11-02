#ifndef _CS_OPERATIONS_H_
#define _CS_OPERATIONS_H_

// ATLM Main Operation Function
void hyCANSAT_ATLM_OPERATION();

// DTLM Main Operation Function
void hyCANSAT_DTLM_OPERATION();

// Camera Main Operation Function
void hyCANSAT_CAMERA_OPERATION();
void hyCANSAT_CAMERA_NO_OPERATION();

// GPS Main Operation Function
void hyCANSAT_GPS_OPERATION();

// IMU Main Operation Function
void hyCANSAT_IMU_OPERATION();

// Send time_sec to GS //
void hyCANSAT_LIFE_SIGN_OPERATION();

// Servo Control Operation 
void hyCANSAT_SERVO_OPERATION();

// User Defined OPERATION 
void hyCANSAT_USER_OPERATION();

//////////////////////////////////////////////////////////
// Message Main Operations
void hyCANSAT_MSG_OPERATION();
void hyCANSAT_M4_OPERATION();
void hyCANSAT_M5_OPERATION();
void hyCANSAT_M6_OPERATION();
void hyCANSAT_M7_OPERATION();
void hyCANSAT_MSG_M4_OPERATION_WITH_UNIT();
void hyCANSAT_MSG_M5_OPERATION_WITH_UNIT();
void hyCANSAT_MSG_M6_OPERATION_WITH_UNIT();
void hyCANSAT_MSG_M7_OPERATION_WITH_UNIT();

#endif