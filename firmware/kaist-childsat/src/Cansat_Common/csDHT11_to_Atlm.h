#ifndef _CS_DHT11_TO_ATLM_H_
#define _CS_DHT11_TO_ATLM_H_

#define DHpin D10


// ATLM Get and Temperature Setting Function
void hy_DHT11_To_ATlm_Get(void);

//////////////////////
class dht11
{
public:
    int read(int pin);
	unsigned char humidity;
	unsigned char temperature;
};
////////////////////


#endif
