// MSG_LOOP
#include "../Cansat_Common/csDHT11_to_Atlm.h"
#include "../Cansat_Common/csDHT11_to_Atlm.c"
#include "../Cansat_Common/csDHT11_to_Atlm_Op.c"
//////////////////////////
// Cansat main loop     //
//////////////////////////
#if 1
void loop()
{
	hyLed_PortSet();

	if (IS_NEED_ICMD(ICMD_MASK_RESET)) { CLEAR_ICMD(ICMD_MASK_RESET); hyCANSAT_INIT(1); }

	if (watch_dog_cnt == 0) { sei(); }
	//		else wdt_reset() ;    // reset hardware watch_dog when data received //
	watch_dog_cnt = 0;

	hyCANSAT_LIFE_SIGN_OPERATION();
	if (IS_NEED_OP(OP_MASK_GPS)) hyCANSAT_GPS_OPERATION(); // 9600
	if (IS_NEED_OP(OP_MASK_GPS)) hyCANSAT_Gs_Tx_Message(0, "After GPS OP");
	if (IS_NEED_OP(OP_MASK_IMU)) hyCANSAT_IMU_OPERATION(); // 115200
	if (IS_NEED_OP(OP_MASK_IMU)) hyCANSAT_Gs_Tx_Message(1, "After IMU OP");
	if (IS_NEED_OP(OP_MASK_CAMERA)) hyCANSAT_CAMERA_OPERATION(); // Digital Picture 115200
	if (IS_NEED_OP(OP_MASK_CAMERA)) hyCANSAT_Gs_Tx_Message(2, "After CAMERA OP");
//	if (IS_NEED_OP(OP_MASK_ATLM)) hyCANSAT_ATLM_OPERATION();
	if (IS_NEED_OP(OP_MASK_ATLM)) hyCANSAT_DHT11_to_ATLM_OPERATION();
	if (IS_NEED_OP(OP_MASK_DTLM)) hyCANSAT_DTLM_OPERATION();
//	if (IS_NEED_OP(OP_MASK_USER)) hyCANSAT_USER_OPERATION() ; // USER DEFINED OPERATION
//	else                          hyCANSAT_SERVO_OPERATION(); // PWM OPERATION 
	hyTransUartOne();
}

#else // for debugging //
void dht11_setup()
{
  //Serial.begin(9600);
  pinMode (DHpin, OUTPUT);
  Serial.println("DHT11 TEST PROGRAM ");
  Serial.print("LIBRARY VERSION: ");
  Serial.println();
}

double Fahrenheit(double celsius)
{
	return 1.8 * celsius + 32;
}

void dht11_loop()
{
  Serial.println("\n");

  int chk = DHT11.read(DHpin);

  Serial.print("Read sensor: ");
  switch (chk)
  {
    case 0  : Serial.println("OK"); break;
    case -1 : Serial.println("Checksum error")     ; break;
    case -2 : Serial.println("Time out error")     ; break;
    case -10: Serial.println("Time out (10) error"); break;
    case -20: Serial.println("Time out (20) error"); break;
    case -30: Serial.println("Time out (30) error"); break;
    case -40: Serial.println("Time out (40) error"); break;
    default : Serial.println("Unknown error"); break;
  }

  Serial.print("Humidity (%): ");
  Serial.println((float)DHT11.humidity, 2);

  Serial.print("Temperature (oC): ");
  Serial.println((float)DHT11.temperature, 2);

  Serial.print("Temperature (oF): ");
  Serial.println(Fahrenheit(DHT11.temperature), 2);

//  delay(1000);
}

void LED_TEST( int pin)
{
	digitalWrite(pin,HIGH);
	delay(500);
	digitalWrite(pin,LOW);
	delay(500);
}

void loop()
{
	static unsigned char is_first = 1 ;

	if( is_first ) { dht11_setup() ; is_first = 0 ;}
	dht11_loop();
	// LED_TEST(DPpin);
	delay(500);
}
#endif