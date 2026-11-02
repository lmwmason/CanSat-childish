#ifndef _CS_DTLM_H_
#define _CS_DTLM_H_
// DTLM Process
// 1. Flag Toggle
// 2. PORT Data Set
void hyDTlm_OP();

// DTLM Send to GS
// 76 00 48 02 DTLM(2)  CS(1)  // OLD VERSION
// 76 00 48 04 DTLM(4)  CS(1)  // NEW VERSION
void hyDTlm_Send();


#endif 