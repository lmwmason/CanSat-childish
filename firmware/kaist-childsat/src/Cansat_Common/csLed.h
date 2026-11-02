#ifndef _CS_LED_H_
#define _CS_LED_H_

///////////////////////////////////////////////////
// LED output
unsigned char cansat_led = 0xFF;

//////////////////////////////////////////////////////////////////////////////
// 3개의 LED 를 다룬다. 
#define LED_MASK_SIGN   0x40 // Led Toggling 
#define LED_MASK_GS     0x80 // When Recv Gs Port
#define LED_MASK_PL     0x20 // When Recv Data Port
#define LED_MASK_LOG    0x01 // 
//////////////////////////////////////////////////////////////////////////////

void CLEAR_LED(unsigned char mask) { unsigned char b = PINC; b |= (mask & 0xE0); PORTC = b; }
void SET_LED(unsigned char mask) { unsigned char b = PINC; b &= ~(mask & 0xE0); PORTC = b; }
void TOGGLE_LED(unsigned char mask) { unsigned char b = PINC; b ^= (mask & 0xE0); PORTC = b; }

// LED Setting ==> LED Toggle, Flags Clear
void hyLed_PortSet()
{
	TOGGLE_LED(LED_MASK_SIGN);
	CLEAR_LED(LED_MASK_GS);
	CLEAR_LED(LED_MASK_PL);
	//        CLEAR_LED ( LED_MASK_USER) ;
	//      if( IS_NEED_OP(OP_MASK_USER) ) CLEAR_LED(LED_MASK_USER);  else SET_LED(LED_MASK_USER); 	
	CLEAR_LED(LED_MASK_LOG);
}
#endif