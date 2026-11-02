#ifndef _CS_CAMERA_H_
#define _CS_CAMERA_H_

// SIZE :: when received 76 00 34 00 04 00 00 XX YY //
unsigned char sCameraReceive_SizeFlag = 0;
unsigned char hyCameraImageSize[2];
unsigned char img_recv_flag = 0;
unsigned char img_recv_part_flag = 0;


// DATA :: when received 76 00 34 00 04 00 00 XX YY //
void hyCamera_Reset();
void hyCamera_Reset_Set();
void hyGs_Reset_Reply();

// Camera Sleep 
void hyCamera_Sleep();

// Camera Wake 
void hyCamera_Wake();

// Camera Tx Baud 9600 
void hyCamera_9600_bps();

// Camera Tx Baud 38400 
void hyCamera_38400_bps();

// Camera Tx Baud 115200 
void hyCamera_115200_bps();

// Camera Tx Baud 115200 ( Direct )
void hyCamera_115200_bps_Set();

// Camera Image 160 
void hyCamera_160();

// Camea Image 320
void hyCamera_320();

// Camera Image 640
void hyCamera_640();

// Camera Image Stop 
void hyCamera_Stop();

// Camera Image Take
void hyCamera_Take();

// Camera Image Resume
void hyCamera_Resume();

unsigned char Char_to_OSD(char ich);
void hyCamera_Osd_Add_Char(char* istr);

// Camea Image Size Request
void hyCamera_Size();

// Camera Data Request
void hyCamera_ImageGet(unsigned char b0, unsigned char b1, unsigned char b2, unsigned char b3);

// Camear Image Size Rx Processing 
// When received image size data
// Set sCameraImageSize 
// Receive : 76 00 34 00 04 00 00 XX YY //
void hyCamera_Receive_Size(unsigned char rx);


// Camera Image Data Rx Function
// When received end of the image signal 
// set img_recv_flag to 1 
// Receive : FF D9 76 00 32 00 //

void hyCamera_Receive_Image(unsigned char rx);

// Camera Initialize Functions
// 1. UART0 , UART1 Initialize
// 2. 38400 , 115200 Baud Set
// 3. Camera Reset
// 4. Camera Image Size 320 
// 5. Camera Baud  115200 
// 6. Cansat UART0, 115200

void hyCamera_PictureSize();

void hyCamera_Init();

#endif