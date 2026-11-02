#include "csDHT11_to_Atlm.h"

//  8M ==> 10000
// 11M ==> 15000
// 16M ==> 20000

#define V_CLOCK_TIME_CONV(macV) ( (macV) * 8 / 11 ) 
#define DHT11_WAIT_COUNT (V_CLOCK_TIME_CONV(10000))


// this function use parts of the dht11.cpp 
int dht11::read(int pin)
{
	// BUFFER TO RECEIVE
	unsigned char bits[5];
	unsigned char cnt = 7;
	unsigned char idx = 0;

	// EMPTY BUFFER
	for (int i=0; i< 5; i++) bits[i] = 0;

	// REQUEST SAMPLE
	pinMode(pin, OUTPUT);
	digitalWrite(pin, LOW);
	delay(V_CLOCK_TIME_CONV(18)); 
	//delay(30);

	digitalWrite(pin, HIGH);
	delayMicroseconds(V_CLOCK_TIME_CONV(40));
	pinMode(pin, INPUT);

	// ACKNOWLEDGE or TIMEOUT
	unsigned int loopCnt = DHT11_WAIT_COUNT;
	while(digitalRead(pin) == LOW)
		if (loopCnt-- == 0) 
			return -10;

	loopCnt = DHT11_WAIT_COUNT;
	while(digitalRead(pin) == HIGH)
		if (loopCnt-- == 0) 
			return -20;

	// READ OUTPUT - 40 BITS => 5 BYTES or TIMEOUT
	for (int i=0; i<40; i++)
	{
		loopCnt = DHT11_WAIT_COUNT;
		while(digitalRead(pin) == LOW)
			if (loopCnt-- == 0) 
				return -30;

		unsigned long t = micros();

		loopCnt = DHT11_WAIT_COUNT;
		while(digitalRead(pin) == HIGH)
			if (loopCnt-- == 0) 
				return -40;

		if ((micros() - t) > V_CLOCK_TIME_CONV(40)) bits[idx] |= (1 << cnt);
		if (cnt == 0)   // next byte?
		{
			cnt = 7;    // restart at MSB
			idx++;      // next byte!
		}
		else cnt--;
	}

	// WRITE TO RIGHT VARS
    // as bits[1] and bits[3] are allways zero they are omitted in formulas.
	humidity    = bits[0]; 
	temperature = bits[2]; 

	uint8_t sum = bits[0] + bits[2];  

	if (bits[4] != sum) return -1;
	return 0;
}


dht11 DHT11 ;

void hy_DHT11_To_ATlm_Get(void)
{
	DHT11.read(DHpin);
	ad_data[0] = DHT11.humidity  ;
	ad_data[1] = DHT11.temperature;
}

