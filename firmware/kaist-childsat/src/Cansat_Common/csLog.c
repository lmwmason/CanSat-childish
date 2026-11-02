//char sLogFileName[10];
void hyLOG_FILE_OPEN()
{
    unsigned long t;
    unsigned long local_time = time_sec + (9 * 3600);  // KST : local time + 9 hour //
    unsigned char pos = 0;

    t = local_time / 3600 % 24;   sLogFileName[pos++] = (t / 10) + '0'; sLogFileName[pos++] = (t % 10) + '0';// hour // 
    t = local_time / 60 % 60;   sLogFileName[pos++] = (t / 10) + '0'; sLogFileName[pos++] = (t % 10) + '0';// min  // 
    sLogFileName[pos++] = '.';
    sLogFileName[pos++] = 'C';
    sLogFileName[pos++] = 'S';
    sLogFileName[pos++] = 'V';
    sLogFileName[pos++] = 0;

    csLogFile = SD.open(sLogFileName, FILE_WRITE);
    if (csLogFile) SET_LED(LED_MASK_LOG);
}

void hyLOG_FILE_CLOSE()
{
    if (csLogFile) csLogFile.close();
}

void hyLOG_GPS_DATA()
{
    if (csLogFile)
    {
        //    csLogFile.println("GPS DATA");
        csLogFile.write(gps_data, gps_data_idx);
        csLogFile.println();
    }
}

void hyLOG_IMU_DATA()
{
    if (csLogFile)
    {
        csLogFile.print("IMU_DATA,");
        csLogFile.write(imu_data, imu_data_idx);
        csLogFile.println();
    }
}

void hyLOG_CAMERA_INIT()
{
    if (csLogFile)
    {
        csLogFile.println("CAMERA_INIT");
    }
}

void hyLOG_CAMERA_SIZE()
{
    if (csLogFile)
    {
        unsigned short us = hyCameraImageSize[0];
        us <<= 8; us += hyCameraImageSize[1];
        csLogFile.print("IMAGE_SIZE,");
        csLogFile.print(us);
        csLogFile.println();
    }
}

void hyLOG_CAMERA_IMAGE()
{
    if (csLogFile)
    {
        csLogFile.println("IMAGE_RECEIVED");
    }
}

void hyLOG_ATLM_DATA()
{
    if (csLogFile)
    {
        csLogFile.print("ATLM,");
        csLogFile.print(ad_data[0]); csLogFile.print(',');
        csLogFile.print(ad_data[1]); csLogFile.print(',');
        csLogFile.print(ad_data[2]); csLogFile.print(',');
        csLogFile.print(ad_data[3]); csLogFile.print(',');
        csLogFile.print(ad_data[4]); csLogFile.print(',');
        csLogFile.print(ad_data[5]); csLogFile.print(',');
        csLogFile.print(ad_data[6]); csLogFile.print(',');
        csLogFile.print(ad_data[7]);
        csLogFile.println();
    }
}

void hyLOG_DTLM_DATA()
{
    if (csLogFile)
    {
        csLogFile.print("DTLM4,");
        csLogFile.print((cansat_dcmd_0 & 0x80) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_0 & 0x40) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_0 & 0x20) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_0 & 0x10) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_0 & 0x08) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_0 & 0x04) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_0 & 0x02) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_0 & 0x01) ? '1' : '0'); csLogFile.print(',');

        csLogFile.print((cansat_dcmd_1 & 0x80) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_1 & 0x40) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_1 & 0x20) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_1 & 0x10) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_1 & 0x08) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_1 & 0x04) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_1 & 0x02) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_1 & 0x01) ? '1' : '0'); csLogFile.print(',');

        csLogFile.print((cansat_dcmd_2 & 0x80) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_2 & 0x40) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_2 & 0x20) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_2 & 0x10) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_2 & 0x08) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_2 & 0x04) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_2 & 0x02) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_2 & 0x01) ? '1' : '0'); csLogFile.print(',');

        csLogFile.print((cansat_dcmd_3 & 0x80) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_3 & 0x40) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_3 & 0x20) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_3 & 0x10) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_3 & 0x08) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_3 & 0x04) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_3 & 0x02) ? '1' : '0'); csLogFile.print(',');
        csLogFile.print((cansat_dcmd_3 & 0x01) ? '1' : '0'); csLogFile.print(',');

        csLogFile.println();
    }
}

extern unsigned char gProgramType ;

void hyLOG_LIFE_SIGN()
{
    unsigned long local_time = time_sec + (9 * 3600); // KST : 9 hour 
    hyLOG_FILE_CLOSE();
    hyLOG_FILE_OPEN();
    if (csLogFile)
    {
        // hh,mm,ss, hh,mm,ss, pt //
        csLogFile.print("LIFESIGN,");
        csLogFile.print(local_time / 3600 % 24); csLogFile.print(':'); // hh
        csLogFile.print(local_time / 60 % 60); csLogFile.print(':');   // mm
        csLogFile.print(local_time % 60); csLogFile.print(',');        // ss
        csLogFile.print(time_run / 3600 % 24); csLogFile.print(':');   // hh
        csLogFile.print(time_run / 60 % 60); csLogFile.print(':');     // mm
        csLogFile.print(time_run % 60); csLogFile.print(',');          // ss
		csLogFile.print(gProgramType) ;
        csLogFile.println();
    }
}
