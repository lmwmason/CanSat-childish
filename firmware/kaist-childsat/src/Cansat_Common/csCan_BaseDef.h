#ifndef _CS_BASE_DEF_H_
#define _CS_BASE_DEF_H_

#include <Arduino.h> // USE Arduino
#include <EEPROM.h>  // USE arduino EEPROM
#include <Servo.h>   // USE arduino SERVO 

// BT
#define BT_NEED_INIT 1
#define BT_NO_NEED_INIT 0
#define GS_0_PL_1  // if defined  GS = UART_PORT_0 , PL = UART_PORT_1 VERSION 2014

// SD CARD //
#include <SPI.h>
#include <SD.h>


#define GS_0_PL_1  // if defined  GS = UART_PORT_0 , PL = UART_PORT_1 VERSION 2014
//#define GS_1_PL_0  // if defined  GS = UART_PORT_0 , PL = UART_PORT_1 VERSION 2012,3

const unsigned char MASK_BIT_OR[8] = { 0x80,0x40,0x20,0x10,0x08,0x04,0x02,0x01 };
const unsigned char MASK_BIT_AND[8] = { 0x7F,0xBF,0xDF,0xEF,0xF7,0xFB,0xFD,0xFE };

unsigned char  time_tick = 0;
unsigned short time_servo_tick = 0;
unsigned short time_msec = 0; // use millis() % 1000 ;
unsigned long time_run = 0;  // use millis() / 1000 ; 
unsigned long time_sec = 0;  // use gps + time_run 

unsigned short watch_dog_cnt = 0; // watch_dog_count 

#ifndef CAMERA_ONE_BLOCK_SIZE
//#define CAMERA_ONE_BLOCK_SIZE 0x80
#define CAMERA_ONE_BLOCK_SIZE 0x40
#endif

// PORT 0 is Camera
// PORT 1 is GS
#define MAX_PL_RX_QUEUE			(CAMERA_ONE_BLOCK_SIZE*2)
#define MAX_GS_RX_QUEUE			32
#define MAX_PL_TX_QUEUE			32
#define MAX_GS_TX_QUEUE			(CAMERA_ONE_BLOCK_SIZE*2)
#define MAX_GS_TX_FRAME_QUEUE   (CAMERA_ONE_BLOCK_SIZE*2)

#define PL_RX_QUEUE_IDX_MASK (MAX_PL_RX_QUEUE-1)
#define GS_RX_QUEUE_IDX_MASK (MAX_GS_RX_QUEUE-1)
#define PL_TX_QUEUE_IDX_MASK (MAX_PL_TX_QUEUE-1)
#define GS_TX_QUEUE_IDX_MASK (MAX_GS_TX_QUEUE-1)
#define GS_TX_FRAME_QUEUE_IDX_MASK (MAX_GS_TX_FRAME_QUEUE-1)

#define MAX_RX_FRAME_DATA_SIZE       (CAMERA_ONE_BLOCK_SIZE)
#define MAX_TX_FRAME_DATA_SIZE       (CAMERA_ONE_BLOCK_SIZE*2)

#define TX_SPEED_9600       9600   
#define TX_SPEED_38400      38400  
#define TX_SPEED_115200     115200 

// baud_setting = (F_CPU / 8 / baud - 1) / 2;

#define PL_TX_SPEED        115200
#define GS_TX_SPEED        115200

#ifdef GS_0_PL_1

#define GS_PORT Serial
#define PL_PORT Serial1

#else

#define PL_PORT Serial
#define GS_PORT Serial1

#endif

///////////////////////////////////////////////////////////////////////////////////
// USE ARDUINO's begin function.. OK 
//    baud_setting = (F_CPU / 8 / baud - 1) / 2;
#define GS_PORT_SPEED_SET(macSpeed) GS_PORT.begin(macSpeed)
#define PL_PORT_SPEED_SET(macSpeed) PL_PORT.begin(macSpeed) 
///////////////////////////////////////////////////////////////////////////////////
void PL_UART_INIT() { PL_PORT.begin(PL_TX_SPEED); }
void GS_UART_INIT() { GS_PORT.begin(GS_TX_SPEED); }
///////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////
// One Byte Tx Function Define  //
#define hyPlTxByte(data)     PL_PORT.write(data)
#define hyGsTxByte(data)     GS_PORT.write(data)
#define hyGsSetTxByte(data)  hyGsTxByte(data)
//#define hyGsSetTxByte(data)  GS_PORT.write(data)

// read one byte processing //
// One Byte Rx Function Define for each Ports// 
void hyGs_RecvByte(unsigned char b);
void hyCamera_RecvByte(unsigned char b);
void hyImu_RecvByte(unsigned char b);
void hyGps_RecvByte(unsigned char b);

unsigned char gIsGsConnected = 0 ;
inline unsigned char Is_GsConnected() { return gIsGsConnected ; }
//inline void Get_GsConnected()        { gIsGsConnected = (PINF & 0x01) ? 0 : 1; } // user ATLM0
inline void Get_GsConnected()          { gIsGsConnected = (PINF & 0x10) ? 0 : 1; } // user ATLM5

#endif