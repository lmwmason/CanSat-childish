#ifndef _CS_MESSAGE_H_
#define _CS_MESSAGE_H_

// 76 00 MSG_TYPE MSG_LEN MSG //
unsigned char msg_data[96];
unsigned char msg_data_idx = 0;
unsigned char msg_recv_flag = 0;
void hyMsg_RecvByte(unsigned char b);


// 56 00 48 00 ID CMD XOR //
//void hySendSetCmd_To_Unit(unsigned char id, unsigned char cmd);

//void hyCANSAT_MSG_OPERATION_WITH_UNIT(unsigned char iRxMode);


#endif