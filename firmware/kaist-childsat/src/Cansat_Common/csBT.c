// BT Initialize Function
// Version 1
// 1. UART1 Initialize    : 9600
// 2. BT Speed Init       : AT+UARTCONFIG,115200,N,1
// 2.1 BT Speed Init      : AT+BTUART,115200,N,1
// 3. BT MODE Init        : AT+BTMODE,3
// 4. BT Restart          : ATZ

// New Version :: 2025 == use CansatGS
// t,t,3,2,5,1,8, t, 6,1,7,1 : MODE 2, 115200, SLAVE, OPMODE 0

void hyBT_STOP()
{
	hyGsSetTxByte('+');
	hyGsSetTxByte('+');
	hyGsSetTxByte('+');
	hyGsSetTxByte(0x0D);
	hyGsSetTxByte(0x0A);
}

void hyBT_115200()
{
	hyGsSetTxByte('a');
	hyGsSetTxByte('t');
	hyGsSetTxByte('+');
	hyGsSetTxByte('u');
	hyGsSetTxByte('a');
	hyGsSetTxByte('r');
	hyGsSetTxByte('t');
	hyGsSetTxByte('c');
	hyGsSetTxByte('o');
	hyGsSetTxByte('n');
	hyGsSetTxByte('f');
	hyGsSetTxByte('i');
	hyGsSetTxByte('g');
	hyGsSetTxByte(',');
	hyGsSetTxByte('1');
	hyGsSetTxByte('1');
	hyGsSetTxByte('5');
	hyGsSetTxByte('2');
	hyGsSetTxByte('0');
	hyGsSetTxByte('0');
	hyGsSetTxByte(',');
	hyGsSetTxByte('N');
	hyGsSetTxByte(',');
	hyGsSetTxByte('1');
	hyGsSetTxByte(',');
	hyGsSetTxByte('0');
	hyGsSetTxByte(0x0D);
	hyGsSetTxByte(0x0A);
}


void hyBT_MODE()
{
	hyGsSetTxByte('a');
	hyGsSetTxByte('t');
	hyGsSetTxByte('+');
	hyGsSetTxByte('b');
	hyGsSetTxByte('t');
	hyGsSetTxByte('m');
	hyGsSetTxByte('o');
	hyGsSetTxByte('d');
	hyGsSetTxByte('e');
	hyGsSetTxByte(',');
	hyGsSetTxByte('3');
	hyGsSetTxByte(0x0D);
	hyGsSetTxByte(0x0A);
}

void hyBT_ATS()
{
	hyGsSetTxByte('a');
	hyGsSetTxByte('t');
	hyGsSetTxByte('s');
	hyGsSetTxByte('1');
	hyGsSetTxByte('0');
	hyGsSetTxByte('=');
	hyGsSetTxByte('1');
	hyGsSetTxByte(0x0D);
	hyGsSetTxByte(0x0A);
}
void hyBT_ATZ()
{
	hyGsSetTxByte('a');
	hyGsSetTxByte('t');
	hyGsSetTxByte('z');
	hyGsSetTxByte(0x0D);
	hyGsSetTxByte(0x0A);
}

void hyBluetooth_Org_Init()
{
	hyBT_STOP();  hyTransUartWait(WAIT_CNT_BT_STEP);
	hyBT_MODE();  hyTransUartWait(WAIT_CNT_BT_STEP);
	hyBT_115200();  hyTransUartWait(WAIT_CNT_BT_STEP);
	hyBT_ATZ();  hyTransUartWait(WAIT_CNT_BT_STEP);
}

void hyBT_NEW_CFG_CHAR(unsigned char ch)
{
	hyGsSetTxByte(ch);
	hyGsSetTxByte(0x0D);
}

void hyBluetooth_New_Cfg()
{
	hyBT_NEW_CFG_CHAR('t'); hyTransUartWait(WAIT_CNT_BT_STEP); // TOP
	hyBT_NEW_CFG_CHAR('t'); hyTransUartWait(WAIT_CNT_BT_STEP); // TOP
	hyBT_NEW_CFG_CHAR('3'); hyTransUartWait(WAIT_CNT_BT_STEP); // MODE
	hyBT_NEW_CFG_CHAR('2'); hyTransUartWait(WAIT_CNT_BT_STEP); // MODE 2  
	hyBT_NEW_CFG_CHAR('5'); hyTransUartWait(WAIT_CNT_BT_STEP); // UART
	hyBT_NEW_CFG_CHAR('1'); hyTransUartWait(WAIT_CNT_BT_STEP); // BAUD RATE
	hyBT_NEW_CFG_CHAR('8'); hyTransUartWait(WAIT_CNT_BT_STEP); // 115200
	hyBT_NEW_CFG_CHAR('t'); hyTransUartWait(WAIT_CNT_BT_STEP); // TOP  
	hyBT_NEW_CFG_CHAR('6'); hyTransUartWait(WAIT_CNT_BT_STEP); // ROLE
	hyBT_NEW_CFG_CHAR('1'); hyTransUartWait(WAIT_CNT_BT_STEP); // SLAVE
	hyBT_NEW_CFG_CHAR('7'); hyTransUartWait(WAIT_CNT_BT_STEP); // OPMODE
	hyBT_NEW_CFG_CHAR('1'); hyTransUartWait(WAIT_CNT_BT_STEP); // OPMODE 0

  //hyBT_NEW_CFG_CHAR(0x08);hyTransUartWait(WAIT_CNT_BT_STEP) ; // Data Input Cancel
}

#if 0 
void hyBluetooth_Init()
{
	GS_UART_INIT();

	GS_PORT_SPEED_SET(9600);
	hyTransUartWait(WAIT_CNT_BT_STEP);

	hyBluetooth_New_Cfg(); // set Configuration 
	hyTransUartWait(WAIT_CNT_BT_STEP);

	GS_PORT_SPEED_SET(GS_TX_SPEED);
	GS_PORT_SPEED_SET(GS_TX_SPEED);
}

#elif 1 // 2025 Version
void hyBluetooth_Init()
{
	GS_UART_INIT();
	GS_PORT_SPEED_SET(GS_TX_SPEED);
	hyTransUartWait(WAIT_CNT_BT_STEP);
}

#else // Old Version

void hyBluetooth_Init()
{
	GS_UART_INIT();

	GS_PORT_SPEED_SET(9600);
	hyTransUartWait(WAIT_CNT_BT_STEP);

	hyBluetooth_New_Cfg(); // set Configuration 
	hyTransUartWait(WAIT_CNT_BT_STEP);

	hyBluetooth_Org_Init(); // set with 9600

  //	hyBT_STOP()  ;  hyTransUartWait(WAIT_CNT_BT_STEP) ;
  //	hyBT_MODE()  ;	hyTransUartWait(WAIT_CNT_BT_STEP) ;
  //	hyBT_115200();	hyTransUartWait(WAIT_CNT_BT_STEP) ;
  //  hyBT_New_115200();  hyTransUartWait(WAIT_CNT_BT_STEP) ;
  ////	hyBT_ATS()   ;	hyTransUartWait(WAIT_CNT_BT_STEP) ;
  //	hyBT_ATZ()   ;	hyTransUartWait(WAIT_CNT_BT_STEP) ;


	GS_PORT_SPEED_SET(GS_TX_SPEED);

	//	hyBT_MODE()  ;	hyTransUartWait(WAIT_CNT_BT_STEP) ;
	//	hyBT_ATZ()   ;	hyTransUartWait(WAIT_CNT_BT_STEP) ;
		//
	GS_PORT_SPEED_SET(GS_TX_SPEED);
}

#endif
