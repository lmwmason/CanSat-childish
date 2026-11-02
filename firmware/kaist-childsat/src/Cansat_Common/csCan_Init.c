/////////////////////////////////////////
// First Initialize Functsion
// when Tx to the Port   : use  PORTx 
// when Rx from the Port : use PINx  
// when Set the Port     : use DDRx : 0 means  Readable , 1 mean Writable
void hyCANSAT_AVR_INIT()
{
	// Initialize Parts
	MCUCR = 0x00;

	DDRA = 0xFF; // for DTLM CMD : output
	PORTA = 0x00;

	DDRB = 0xFF;  // for OUTPUT LED
	PORTB = 0xFF;

	DDRC = 0xFF; // for selection output
	DDRF = 0x00; // for adc input
	//PORTF =0x00;

	DDRE = 0xFF; // 1110 0010 : OUT for 1 Read for 0 

	PL_UART_INIT();
	GS_UART_INIT();

	// Timer Set Parts
	  // Timer :: for 1ms 

#ifdef CANSAT_AT90CAN128  // when at90can128
	TIMSK0 = (1 << TOIE0);
	TCNT0 = 0;
	TCCR0A = 5; // 1 , 2=/8, 3 =/64 , 4 =/256 5 =/1024 
#else
	TIMSK = (1 << TOIE0);
	TCNT0 = 0;
	TCCR0 = 5; // 1 , 2=/8, 3 =/64 , 4 =/256 5 =/1024 
  //  TCCR0 = 3 ; // 1 , 2=/8, 3 =/64 , 4 =/256 5 =/1024
#endif

	DDRD = 0xFF; // Bidirection

//	for getting the Telemetry, AMUX Initialize
//	ADC_INIT(); 

	// for watch dog enable
//	wdt_enable(0x07); 
//	sei();
}

// 1. stop
// 2. mode
// 3. uart
// 4. reset 
void hyCANSAT_BT_INIT()
{
	// 9600 bps 
	GS_PORT_SPEED_SET(9600);

	hyCansat_Message("+++\n");
	hyCansat_Message("at+btmode,3\n");
	hyCansat_Message("at+uartconfig,115200,N,1,0\n");
	hyCansat_Message("atz\n");

	GS_PORT_SPEED_SET(115200);

	hyCansat_Message("+++\n");
	hyCansat_Message("at+btmode,3\n");
	hyCansat_Message("at+uartconfig,115200,N,1,0\n");
	hyCansat_Message("atz\n");
}

void hyCANSAT_PAYLOAD_INIT()
{
	watch_dog_cnt = 0;

	hyCansat_Message("CANSAT FSW (hypark@satrec)[" __DATE__ "]\n");
	//	hyBluetooth_Init();
	//	hyCamera_Init() ;	
}

void hyCANSAT_INIT(unsigned char ucCheck)
{
	// 1. Avr Init
	hyCANSAT_AVR_INIT();

	// 2. BT Init : default not reset operation , use test module board 
	//	hyCANSAT_BT_INIT();
	if (ucCheck) hyBluetooth_Init();

	// 3. Payload Init
	hyCANSAT_PAYLOAD_INIT();

	// 4. Set Camera Reset Flag
	SET_ICMD(ICMD_MASK_CAMERA_RESET);
}

void hyCANSAT_SD_LOG_INIT()
{
	// SD Card Init Setting //
	pinMode(SS, OUTPUT);    // SS pin
	if (SD.begin(SS))
	{
		hyCansat_Message("SD.begin OK\n");
	}
	else
	{
		hyCansat_Message("SD.begin FAIL\n");
	}
	csLogFile = SD.open("test.txt", FILE_WRITE);
	if (csLogFile)
	{
		hyCansat_Message("SD.open OK\n");
	}
	else
	{
		hyCansat_Message("SD.open Fail\n");
	}
//	if (csLogFile) csLogFile.println("testing 1.2.3");
	if (csLogFile) csLogFile.close();
}


#ifdef GS_0_PL_1

//void serialEvent() { Gs_Rx_QueueIn(Serial.read()); } //  OK
//void serialEvent1(){ Pl_Rx_QueueIn(Serial1.read()); } // NOT OK : why ??? 
void serialEvent() { SET_LED(LED_MASK_PL); while (Serial.available())  Gs_Rx_QueueIn(Serial.read()); } // OK 
//void serialEvent1(){ SET_LED(LED_MASK_PORT); while(Serial1.available() ) Pl_Rx_QueueIn(Serial1.read()); }

#else

void serialEvent() { Pl_Rx_QueueIn(Serial.read()); }
//void serialEvent1(){ Gs_Rx_QueueIn(Serial1.read()); }

#endif

//unsigned long TIME_TO_YEAR(unsigned long itime) 
//{
//  unsigned long days ;
//  days = itime/(24*3600)  ; // days from 1970 
//  leap_days = days/360/4  ; // every 4 years 
//  years = days/365 
//  
//}


