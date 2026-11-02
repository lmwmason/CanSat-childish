#ifndef BT_INVENTORY_H
#define BT_INVENTORY_H
#include <Arduino.h>
#include <EEPROM.h>
// Keep clear of the official operation flags at EEPROM 0x10.
static const uint16_t BT_RECORD_BASE = 0x100;
static const uint16_t BT_RECORD_CAPACITY = 1024;
static uint16_t btCrcByte(uint16_t crc, uint8_t b) {
    crc ^= b;
    for(uint8_t i=0;i<8;++i) crc=(crc&1)?(crc>>1)^0xA001:crc>>1;
    return crc;
}
static uint16_t btRecordLength() {
    if(EEPROM.read(BT_RECORD_BASE)!='B' || EEPROM.read(BT_RECORD_BASE+1)!='T' ||
       EEPROM.read(BT_RECORD_BASE+2)!='I' || EEPROM.read(BT_RECORD_BASE+3)!=1) return 0;
    uint16_t n=EEPROM.read(BT_RECORD_BASE+4)|(uint16_t(EEPROM.read(BT_RECORD_BASE+5))<<8);
    if(!n || n>BT_RECORD_CAPACITY) return 0;
    uint16_t crc=0xFFFF;
    for(uint16_t i=0;i<n;++i) crc=btCrcByte(crc,EEPROM.read(BT_RECORD_BASE+8+i));
    uint16_t saved=EEPROM.read(BT_RECORD_BASE+6)|(uint16_t(EEPROM.read(BT_RECORD_BASE+7))<<8);
    return crc==saved?n:0;
}
static bool btStoreRecord(const uint8_t *data,uint16_t n) {
    if(!n || n>BT_RECORD_CAPACITY) return false;
    uint16_t crc=0xFFFF;
    for(uint16_t i=0;i<n;++i) crc=btCrcByte(crc,data[i]);
    // Identical content requires no EEPROM writes.
    bool same=btRecordLength()==n;
    for(uint16_t i=0;same && i<n;++i) if(EEPROM.read(BT_RECORD_BASE+8+i)!=data[i]) same=false;
    if(same) return true;
    EEPROM.update(BT_RECORD_BASE,0); // invalid until payload and checksum are committed
    for(uint16_t i=0;i<n;++i) EEPROM.update(BT_RECORD_BASE+8+i,data[i]);
    EEPROM.update(BT_RECORD_BASE+4,n&255); EEPROM.update(BT_RECORD_BASE+5,n>>8);
    EEPROM.update(BT_RECORD_BASE+6,crc&255); EEPROM.update(BT_RECORD_BASE+7,crc>>8);
    EEPROM.update(BT_RECORD_BASE+1,'T'); EEPROM.update(BT_RECORD_BASE+2,'I');
    EEPROM.update(BT_RECORD_BASE+3,1); EEPROM.update(BT_RECORD_BASE,'B');
    if(btRecordLength()!=n) return false;
    for(uint16_t i=0;i<n;++i) if(EEPROM.read(BT_RECORD_BASE+8+i)!=data[i]) return false;
    return true;
}
#endif
