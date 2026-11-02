#ifndef _CS_ATLM_H_
#define _CS_ATLM_H_

// Analog Inputs  :: ADC Conver Number Define
#define ADC_TLMS    8
#define ADC_MASK 0x07

// AD convertor ¸¦ ´Ù·é´Ù.
unsigned char adc_mux = 0;
unsigned char ad_data[ADC_TLMS];// AD Converting Value Save

unsigned char FILTER_MID_3(unsigned char b0, unsigned char b1, unsigned char b2);

// ATLM Get Function
// Analog Telemetry GET : Interrupt Setting //
void hyATlm_Get(void);

// ATLM Send To GS Function
// 76 00 40 10 (ad_data)  * 8 //
void hyATlm_Send();



#endif
