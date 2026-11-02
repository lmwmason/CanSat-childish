// Read-only module menu query, persistent verified MCU-side EEPROM inventory.
#include <Arduino.h>
#include <string.h>
#include "bt_inventory.h"
volatile unsigned long btRxInterrupts, btRxParityErrors, btRxFrameErrors, btRxOverruns;
static unsigned long rxEdges, rxHighSamples, rxLowSamples;
static uint8_t previousRx;
static uint8_t response[BT_RECORD_CAPACITY+1];
static uint16_t used;
static bool overflowed;
static bool usbSelfTestSeen;
static void gather(unsigned long duration) {
    unsigned long start=millis();
    while(millis()-start<duration) {
        uint8_t level=PINE & _BV(PE0);
        if(level!=previousRx) { ++rxEdges;previousRx=level; }
        if(level) ++rxHighSamples; else ++rxLowSamples;
        while(Serial.available()) {
        uint8_t b=Serial.read();
        if(used<BT_RECORD_CAPACITY) response[used++]=b;
        else overflowed=true;
    }
    }
    response[used]=0;
    if(strstr((const char*)response,"USB_RX_SELFTEST")) usbSelfTestSeen=true;
}
static bool btHasWord(const char *s,const char *word);
static bool credibleMenu() {
    // Echoes and arbitrary noise are never accepted as device information.
    if(overflowed || used<30) return false;
    uint16_t printable=0;
    for(uint16_t i=0;i<used;++i) if((response[i]>=32 && response[i]<=126) || response[i]=='\r' || response[i]=='\n' || response[i]=='\t') ++printable;
    if(printable*10UL<used*9UL) return false;
    const char *s=(const char*)response;
    return btHasWord(s,"FIRMTECH") || btHasWord(s,"FB155") || btHasWord(s,"FB755") ||
           btHasWord(s,"BD ADDRESS") || btHasWord(s,"DEVICE NAME");
}
static void console() { Serial.flush(); Serial.end(); Serial.begin(115200); delay(80); }
static void dumpStored() {
    uint16_t n=btRecordLength();
    Serial.print("\r\nBT_EEPROM valid=");Serial.print(n?1:0);Serial.print(" length=");Serial.println(n);
    for(uint16_t i=0;i<n;++i) {
        if(i%16==0) {Serial.print("!BT_EEPROM_HEX ");Serial.print(i);Serial.print(' ');}
        uint8_t b=EEPROM.read(BT_RECORD_BASE+8+i);
        if(b<16) Serial.print('0');Serial.print(b,HEX);
        if(i%16==15 || i+1==n) Serial.println(" !");
    }
    Serial.flush();
}
static uint16_t attemptBytes[3];
static unsigned long attemptEdges[3], attemptHigh[3], attemptLow[3], attemptIrq[3], attemptParity[3], attemptFrame[3], attemptOverrun[3];
static bool attemptValid[3], attemptSaved[3], attemptOverflow[3];
static bool btHasWord(const char *s,const char *word) {
    for(;*s;++s) {
        const char *a=s,*b=word;
        while(*a && *b) {
            char c=*a;if(c>='a' && c<='z') c-=32;
            if(c!=*b) break;
            ++a;++b;
        }
        if(!*b) return true;
    }
    return false;
}
void setup() {
    DDRA=0xFF;PORTA=0;DDRB=0xFF;PORTB=0xFF;DDRC=0xFF;DDRD=0xFF;DDRE=0xFF;DDRF=0;
    // Read-only module identity query. This does not change Bluetooth settings.
    Serial.begin(9600);
    delay(1200);
    Serial.write((uint8_t)'t'); Serial.write((uint8_t)'\r'); Serial.flush();
    gather(2200);
    if(used<30) {
        Serial.write((uint8_t)'t'); Serial.write((uint8_t)'\r'); Serial.flush();
        gather(2200);
    }
    attemptValid[0]=credibleMenu();
    attemptSaved[0]=attemptValid[0] && btStoreRecord(response,used);
    attemptBytes[0]=used;
    // Stop sending before switching back to USB diagnostics.
    console();delay(1500);
    Serial.print("BT_READONLY rx_bytes=");Serial.print(used);
    Serial.print(" menu=");Serial.print(attemptValid[0]);Serial.print(" saved_verified=");Serial.println(attemptSaved[0]);
    Serial.print("BT_READONLY_HEX ");
    for(uint16_t i=0;i<used;++i) { if(response[i]<16) Serial.print('0');Serial.print(response[i],HEX); }
    Serial.println();
    Serial.print("USB_RX_SELFTEST seen=");Serial.println(usbSelfTestSeen);
    dumpStored();
    Serial.println("BT_READONLY_QUERY_FINISHED");Serial.flush();
}
void loop() { delay(1000); }
