#ifndef _CS_EEPROM_H_
#define _CS_EEPROM_H_

//////////////////////////////////////////////////////////////////////////////	
// EEPROM :: 
#define OP_EEPROM_ADDR     0x10
#define OP_TO_EEPROM()     { EEPROM.write(OP_EEPROM_ADDR, cansat_dcmd_0); } 
#define OP_FROM_EEPROM()   { cansat_dcmd_0 = EEPROM.read(OP_EEPROM_ADDR); }

#endif