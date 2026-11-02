#ifndef _CS_BT_H_
#define _CS_BT_H_


// BT Initialize Function
// Version 1
// 1. UART1 Initialize    : 9600
// 2. BT Speed Init       : AT+UARTCONFIG,115200,N,1
// 2.1 BT Speed Init      : AT+BTUART,115200,N,1
// 3. BT MODE Init        : AT+BTMODE,3
// 4. BT Restart          : ATZ

// New Version :: 2025 == use CansatGS
// t,t,3,2,5,1,8, t, 6,1,7,1 : MODE 2, 115200, SLAVE, OPMODE 0

void hyBT_STOP();
void hyBT_115200();
void hyBT_MODE();
void hyBT_ATS();
void hyBT_ATZ();

void hyBluetooth_Org_Init();
void hyBT_NEW_CFG_CHAR(unsigned char ch);
void hyBluetooth_New_Cfg();

void hyBluetooth_Init();

#endif