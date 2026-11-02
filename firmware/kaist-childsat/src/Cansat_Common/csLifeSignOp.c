// 2024.09.03 : Version Inserted
// Send time_sec to GS //
extern unsigned char gProgramType ; 
void hyCANSAT_LIFE_SIGN_OPERATION()
{
    static long previousTime = 0;
    long now = millis();
    unsigned char b; unsigned char cs = 0;

    if (1000 < (now - previousTime) || now < previousTime)  // time is different 
    {
        previousTime = now;
        // time_sec = time_sec + time_run - (now / 1000);
		time_sec = time_sec + (now / 1000) - time_run ; // new_time - old_time //
        time_run = now / 1000;
        //          if( ls_state )
        {
            Gs_Tx_QueueIn(0x76);
            Gs_Tx_QueueIn(0x00);
            Gs_Tx_QueueIn(0x4C);
            Gs_Tx_QueueIn(0x0A); // 10 bytes : 20240903
            b = (time_sec >> 24) & 0xFF; Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_sec >> 16) & 0xFF; Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_sec >>  8) & 0xFF; Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_sec >>  0) & 0xFF; Gs_Tx_QueueIn(b); cs ^= b;
#if 1	
            b = (time_run >> 24) & 0xFF;	Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_run >> 16) & 0xFF;	Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_run >>  8) & 0xFF;	Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_run >>  0) & 0xFF;	Gs_Tx_QueueIn(b); cs ^= b;
#else
            b = 0;	Gs_Tx_QueueIn(b); cs ^= b;
            b = 0;	Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_msec >> 8) & 0xFF;	Gs_Tx_QueueIn(b); cs ^= b;
            b = (time_msec >> 0) & 0xFF;	Gs_Tx_QueueIn(b); cs ^= b;
#endif	
#if 1
			b = gProgramType & 0xFF   ; 	Gs_Tx_QueueIn(b); cs ^= b;
#endif
            b = cs;	Gs_Tx_QueueIn(b);
            hyTransUartWait(WAIT_CNT_SEND);
            hyLOG_LIFE_SIGN(); // use time_sec, time_run // 
        }
    }
}
