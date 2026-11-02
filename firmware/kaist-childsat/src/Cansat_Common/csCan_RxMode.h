#ifndef _CS_RX_MODE_H_
#define _CS_RX_MODE_H_

#define RxMode_DEFAULT		  0
#define RxMode_CAMERA		  1
#define RxMode_CAMERA_SIZE	  2
#define RxMode_CAMERA_IMAGE	  3
#define RxMode_CAMERA_IMAGE_BLOCK	8
#define RxMode_GPS		      4
#define RxMode_IMU		      5
#define RxMode_ATLM		      6
#define RxMode_DTLM		      7
#define RxMode_M4          0x14
#define RxMode_M5          0x15
#define RxMode_M6          0x16
#define RxMode_M7          0x17

unsigned char hyRxMode = RxMode_CAMERA;  // when 0 

//#define RxMode_CAMERA_PORT 0x00  
#define RxMode_GPS_PORT    0x01  
#define RxMode_IMU_PORT    0x02  
#define RxMode_M4_PORT     0x04  
#define RxMode_M5_PORT     0x05  
#define RxMode_M6_PORT     0x06  
#define RxMode_M7_PORT     0x07 

#define RxMode_CAMERA_0_PORT 0x00 
#define RxMode_CAMERA_1_PORT RxMode_M4_PORT 

unsigned char RxMode_CAMERA_PORT = 0x00; 

// need direction is 0

void hyRxMode_PortSet(unsigned char iMode)
{
	unsigned char b = PINC;
	b &= 0xF0; // direction is 0
	b |= iMode;
	PORTC = b;
}

// Define Count for Each Steps based  11.0592 Mhz Clock 
#define WAIT_CNT_SEND		        0x000100
#define WAIT_CNT_GPS		        0x020000
#define WAIT_CNT_IMU		        0x010000
#define WAIT_CNT_MSG                0x020000
#define WAIT_CNT_ATLM		        0x000080
//#define WAIT_CNT_CAMERA_STEP	    0x002000
#define WAIT_CNT_CAMERA_STEP	    0x001000
#define WAIT_CNT_CAMERA_INIT_STEP   0x007000
#define WAIT_CNT_CAMERA_IMAGE_160   0x010000
#define WAIT_CNT_CAMERA_IMAGE_320   0x020000
#define WAIT_CNT_CAMERA_IMAGE_640   0x080000

unsigned long  WAIT_CNT_CAMERA_IMAGE = WAIT_CNT_CAMERA_IMAGE_640;
//#define WAIT_CNT_CAMERA_IMAGE	WAIT_CNT_CAMERA_IMAGE_640

#define WAIT_CNT_BT_STEP            0x010000
#define WAIT_CNT_BT_NEW_STEP        0x100000


// Need to Payload Data 
// Select UART PORT and Set the Baud rates  using MUX Control
#define CAMERA_INIT_BAUD 38400
//#define CAMERA_BAUD 38400
#define CAMERA_BAUD     115200
#define IMU_BAUD        115200
#define GPS_BAUD          9600
#define ATLM_BAUD  CAMERA_BAUD
#define DTLM_BAUD  CAMERA_BAUD

// NEED to Change for Test
#ifndef MSG_M4_BAUD
#define MSG_M4_BAUD       115200
#endif  

#ifndef MSG_M5_BAUD
#define MSG_M5_BAUD       115200
#endif

#ifndef MSG_M6_BAUD
#define MSG_M6_BAUD       115200
#endif

#ifndef MSG_M7_BAUD
#define MSG_M7_BAUD       115200
#endif

#define BAUD_1200 1
#define BAUD_2400 2
#define BAUD_4800 3
#define BAUD_9600 4
#define BAUD_19200 5
#define BAUD_38400 6
#define BAUD_57600 7
#define BAUD_115200 8


// OnebyOne Set ( Baud, Mode, Ports ) //
inline void hyRxMode_Set_Direct(unsigned char iRxMode, unsigned char iBaudType, unsigned char iRxPort)
{
	switch( iBaudType )
	{
		case BAUD_1200 : PL_PORT_SPEED_SET(1200); break;
		case BAUD_2400 : PL_PORT_SPEED_SET(2400); break;
		case BAUD_4800 : PL_PORT_SPEED_SET(4800); break;
		case BAUD_9600 : PL_PORT_SPEED_SET(9600); break;
		case BAUD_19200 : PL_PORT_SPEED_SET(19200); break;
		case BAUD_38400 : PL_PORT_SPEED_SET(38400); break;
		case BAUD_57600 : PL_PORT_SPEED_SET(57600); break;
		case BAUD_115200 : PL_PORT_SPEED_SET(115200); break;
	}

	hyRxMode = iRxMode  ;

	if(iRxPort) 
		hyRxMode_PortSet(iRxPort);
}

// Need to Payload Data 
// Select UART PORT and Set the Baud rates  using MUX Control
void hyRxMode_Set(unsigned char iMode)
{
	switch (iMode)
	{
		case RxMode_CAMERA:
		case RxMode_CAMERA_SIZE:
		case RxMode_CAMERA_IMAGE: PL_PORT_SPEED_SET(CAMERA_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_CAMERA_PORT); break;
		case RxMode_CAMERA_IMAGE_BLOCK: PL_PORT_SPEED_SET(CAMERA_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_CAMERA_PORT); break; // 2025.05.02
		case RxMode_IMU: PL_PORT_SPEED_SET(IMU_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_IMU_PORT); break;
		case RxMode_GPS: PL_PORT_SPEED_SET(GPS_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_GPS_PORT); break;
		case RxMode_ATLM: PL_PORT_SPEED_SET(ATLM_BAUD); hyRxMode = iMode; break;
		case RxMode_DTLM: PL_PORT_SPEED_SET(DTLM_BAUD); hyRxMode = iMode; break;
		case RxMode_M4: PL_PORT_SPEED_SET(MSG_M4_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_M4_PORT); break;
		case RxMode_M5: PL_PORT_SPEED_SET(MSG_M5_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_M5_PORT); break;
		case RxMode_M6: PL_PORT_SPEED_SET(MSG_M6_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_M6_PORT); break;
		case RxMode_M7: PL_PORT_SPEED_SET(MSG_M7_BAUD); hyRxMode = iMode; hyRxMode_PortSet(RxMode_M7_PORT); break;
	}
}

#endif