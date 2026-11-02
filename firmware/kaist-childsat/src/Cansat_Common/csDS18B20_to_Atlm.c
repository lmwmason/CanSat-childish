#include "csDS18B20_to_Atlm.h"

// 16 000 000 ==> 11 059 200
//#define hyDelayUS(macCnt) __builtin_avr_delay_cycles((macCnt)*16UL)
//#define hyDelayUS(macCnt) __builtin_avr_delay_cycles((macCnt)*11UL) 
#define hyDelayUS(macCnt) delayMicroseconds(macCnt)     // OK
//#define hyDelayUS(macCnt) delayMicroseconds(macCnt*8/11)  // OK 
//#define hyDelayUS(macCnt) delayMicroseconds(macCnt*16000/11059)  //  Not OK

bool ds_reset() {
	pinMode(DS18B20_PIN, OUTPUT);
	digitalWrite(DS18B20_PIN, LOW);
	hyDelayUS(480); // 로우 상태 480us 유지
	
	pinMode(DS18B20_PIN, INPUT); // 핀을 입력으로 변경 (풀업 저항에 의해 하이로 올라감)
	hyDelayUS(70);  // 센서가 응답할 때까지 대기
	
	bool presence = (digitalRead(DS18B20_PIN) == LOW); // 센서가 로우로 당기면 응답 있음
	hyDelayUS(410); // 나머지 타임슬롯 대기
	return presence;
  }
  
  // 1바이트 데이터 쓰기
  void ds_write_byte(byte data) {
	for (int i = 0; i < 8; i++) {
	  pinMode(DS18B20_PIN, OUTPUT);
	  digitalWrite(DS18B20_PIN, LOW); // 타임슬롯 시작
	  
	  if (data & 0x01) {
		hyDelayUS(10);
		pinMode(DS18B20_PIN, INPUT); // 하이 비트 전송 (릴리즈)
		hyDelayUS(55);
	  } else {
		hyDelayUS(65);       // 로우 비트 전송 (로우 유지)
		pinMode(DS18B20_PIN, INPUT);
	  }
	  data >>= 1;
	  hyDelayUS(5); // 비트 간 인터벌
	}
  }
  
  // 1바이트 데이터 읽기
  byte ds_read_byte() {
	byte data = 0;
	for (int i = 0; i < 8; i++) {
	  pinMode(DS18B20_PIN, OUTPUT);
	  digitalWrite(DS18B20_PIN, LOW);
	  hyDelayUS(3); // 마이크로컨트롤러가 스트로브(Strobe) 신호 발생
	  
	  pinMode(DS18B20_PIN, INPUT); // 데이터 핀 양보
	  hyDelayUS(10);       // 센서 데이터 안정화 대기
	  
	  if (digitalRead(DS18B20_PIN)) {
		data |= (1 << i); // 하이 비트 읽기
	  }
	  hyDelayUS(53); // 타임슬롯 마무리를 위한 대기
	}
	return data;
  }
  
  // 라이브러리 없이 온도 값 받아오기 함수
  float getTempWithoutLibrary() {
	if (!ds_reset()) return -1000; // 센서 인식 실패 시 에러값 반환
	
	ds_write_byte(0xCC); // Skip ROM (단일 센서 통신 명령)
	ds_write_byte(0x44); // Convert T (온도 변환 시작 명령)
	
	// 온도 변환 시간 대기 (12비트 해상도 기준 최대 750ms 소요)
	delay(750); 
	
	if (!ds_reset()) return -1000;
	
	ds_write_byte(0xCC); // Skip ROM
	ds_write_byte(0xBE); // Read Scratchpad (저장된 데이터 읽기 명령)
	
	byte lsb = ds_read_byte(); // 온도 데이터 LSB (낮은 바이트)
	byte msb = ds_read_byte(); // 온도 데이터 MSB (높은 바이트)
	
	// 나머지 7바이트 스크래치패드 데이터는 버림 처리 (통신 종료를 위한 리셋)
	ds_reset(); 
	
	// 두 바이트 결합 및 온도 계산 (2의 보수 처리 포함)
	int16_t raw_temp = (msb << 8) | lsb;
	float final_temp = (float)raw_temp / 16.0;
	
	return final_temp;
  }

// ATLM Get Function with OneWire //
void hy_DS18B20_To_ATlm_Get(void)
{
	unsigned char Temp = 0 ;
	ad_data[0] = 0 ;
	if (!ds_reset()) return ; // 센서 인식 실패 시 에러값 반환
	ad_data[0] = 1 ;
	
	ds_write_byte(0xCC); // Skip ROM (단일 센서 통신 명령)
	ds_write_byte(0x44); // Convert T (온도 변환 시작 명령)
	
	// 온도 변환 시간 대기 (12비트 해상도 기준 최대 750ms 소요)
	delay(750); 
	
	if (!ds_reset()) return ;
	ad_data[0] = 2 ;
	
	ds_write_byte(0xCC); // Skip ROM
	ds_write_byte(0xBE); // Read Scratchpad (저장된 데이터 읽기 명령)
	
	byte lsb = ds_read_byte(); // 온도 데이터 LSB (낮은 바이트)
	byte msb = ds_read_byte(); // 온도 데이터 MSB (높은 바이트)
	
	// 나머지 7바이트 스크래치패드 데이터는 버림 처리 (통신 종료를 위한 리셋)
	ds_reset(); 
	
	// 두 바이트 결합 및 온도 계산 (2의 보수 처리 포함)
	int16_t raw_temp = (msb << 8) | lsb;
	float final_temp = (float)raw_temp / 16.0;
	
	// return final_temp;
	// Temp = raw_temp >> 4 ; 
	// Temp = ( (int)(final_temp + 100) )  & 0xFF ;
	// Temp = (int) final_temp ;
	// Temp = ( raw_temp >> 4 ) ; // for   1 degs  : 0 ~ 256 //
	Temp = ( raw_temp >> 3 )    ; // for 0.5 degs  : 0 ~ 128 //
	// Temp = ( raw_temp >> 2 )    ; // for 0.25 degs : 0 ~ 64  //
	// Insert the Temp Data to ad_data[0]
	ad_data[0] = 3 + ( msb != 0xFF ? 1 : 0 );
	ad_data[1] = Temp & 0xFF ;
}