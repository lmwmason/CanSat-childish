#ifndef _CS_CAN_INIT_H_
#define _CS_CAN_INIT_H_
/////////////////////////////////////////
// First Initialize Functions
void hyCANSAT_AVR_INIT();

void hyCANSAT_BT_INIT();

void hyCANSAT_PAYLOAD_INIT();

void hyCANSAT_INIT(unsigned char ucCheck);

void hyCANSAT_LOG_INIT();


//#ifdef GS_0_PL_1
//
////void serialEvent() { Gs_Rx_QueueIn(Serial.read()); } //  OK
////void serialEvent1(){ Pl_Rx_QueueIn(Serial1.read()); } // NOT OK : why ??? 
//void serialEvent() { SET_LED(LED_MASK_PL); while (Serial.available())  Gs_Rx_QueueIn(Serial.read()); } // OK 
////void serialEvent1(){ SET_LED(LED_MASK_PORT); while(Serial1.available() ) Pl_Rx_QueueIn(Serial1.read()); }
//
//#else
//
//void serialEvent() { Pl_Rx_QueueIn(Serial.read()); }
////void serialEvent1(){ Gs_Rx_QueueIn(Serial1.read()); }

#endif


#endif