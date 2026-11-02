// 20240804 : gGsConnectState added 
#ifndef _CS_GS_H_
#define _CS_GS_H_


// One Byte Rx Data Processing From GS 
void hyGs_RecvByte(unsigned char b);

// Send Message to GS 
void hyCANSAT_Gs_Tx_Message(unsigned char msg_id, const char* msg);

// Send Direct Messasge To GS 
void hyCansat_Message(char* msg);

unsigned char gGsConnectState = 0x00 ;
inline void SET_GS_CONNECT_STATE(unsigned char macV) { gGsConnectState = (macV) ;}
#define GS_CONNECT_STATE  gGsConnectState

#endif