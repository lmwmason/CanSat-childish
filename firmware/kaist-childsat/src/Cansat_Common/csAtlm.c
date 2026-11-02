// AD convertor 
// unsigned char adc_mux = 0;
// unsigned char ad_data[ADC_TLMS];// AD Converting Value Save in ad_data[]

unsigned char FILTER_MID_3(unsigned char b0, unsigned char b1, unsigned char b2)
{
	if (b0 < b1) // 0 < 1 
	{
		if (b1 < b2)              return b1;
		else if (b0 < b2)        return b2;
		else                       return b0;
	}
	else                                  // 1 < 0 
	{
		if (b0 < b2)             return b0;
		else if (b1 < b2)       return b2;
		else                      return b1;
	}
}

// ATLM Get Function //
// Analog Telemetry GET : Interrupt Setting //
void hyATlm_Get(void)
{
	unsigned char b0, b1, b2;
	int sensor_value;
	sensor_value = analogRead(adc_mux); // remove 
	sensor_value = analogRead(adc_mux); // remove 
	sensor_value = analogRead(adc_mux); b0 = (sensor_value >> 2) & 0xFF; // b0 = map(sensor_value,0,1023,0,255); // 10 bits ==> 8 bits ,, >> 4 
	sensor_value = analogRead(adc_mux); b1 = (sensor_value >> 2) & 0xFF; // b1 = map(sensor_value,0,1023,0,255); // 10 bits ==> 8 bits ,, >> 4 
	sensor_value = analogRead(adc_mux); b2 = (sensor_value >> 2) & 0xFF; // b2 = map(sensor_value,0,1023,0,255); // 10 bits ==> 8 bits ,, >> 4 
	ad_data[adc_mux] = FILTER_MID_3(b0, b1, b2);
	adc_mux = (adc_mux + 1) & 0x07;
}

// ATLM Tx to GS Function 
// 76 00 40 10 (ad_data)  * 8 //
void hyATlm_Send()
{
	unsigned char cs_atlm = 0;
	Gs_Tx_QueueIn(0x76);
	Gs_Tx_QueueIn(0x00);
	Gs_Tx_QueueIn(0x40);
	Gs_Tx_QueueIn(0x10);
	Gs_Tx_QueueIn(ad_data[0]); cs_atlm += ad_data[0];
	Gs_Tx_QueueIn(ad_data[1]); cs_atlm += ad_data[1];
	Gs_Tx_QueueIn(ad_data[2]); cs_atlm += ad_data[2];
	Gs_Tx_QueueIn(ad_data[3]); cs_atlm += ad_data[3];
	Gs_Tx_QueueIn(ad_data[4]); cs_atlm += ad_data[4];
	Gs_Tx_QueueIn(ad_data[5]); cs_atlm += ad_data[5];
	Gs_Tx_QueueIn(ad_data[6]); cs_atlm += ad_data[6];
	Gs_Tx_QueueIn(ad_data[7]); cs_atlm += ad_data[7];
	Gs_Tx_QueueIn(cs_atlm);
}