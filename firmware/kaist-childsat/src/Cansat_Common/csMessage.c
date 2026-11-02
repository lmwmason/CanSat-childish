// 76 00 MSG_TYPE MSG_LEN MSG //
//unsigned char msg_data[96];
//unsigned char msg_data_idx = 0;
//unsigned char msg_recv_flag = 0;
void hyMsg_RecvByte(unsigned char b)
{
    static unsigned char msg_state = 0;
    static unsigned char msg_type = 0;
    static unsigned char msg_len = 0;
    unsigned char idx;

    switch (msg_state)
    {
    case 0: msg_state = (b == 0x76) ? 1 : 0;                        break;  // 0x76
    case 1: msg_state = (b == 0x00) ? 2 : ((b == 0x76) ? 1 : 0);   break;  // 0x00
    case 2: msg_state = (0xA0 <= b && b <= 0xAF) ? 3 : ((b == 0x76) ? 1 : 0); msg_type = b;  break;  // MSG_TYPE
    case 3: msg_state = 4; msg_len = (b < 96) ? b : 95; msg_data_idx = 0;                       break;  // MSG_LEN
    case 4: if (msg_data_idx < msg_len) { msg_data[msg_data_idx] = b; msg_data_idx++; }
          if (msg_len <= msg_data_idx)
          {
              msg_recv_flag = 1;
              Gs_Tx_QueueIn(0x76);
              Gs_Tx_QueueIn(0x00);
              Gs_Tx_QueueIn(msg_type);
              Gs_Tx_QueueIn(msg_data_idx);
              for (idx = 0; idx < msg_data_idx; idx++)
              {
                  Gs_Tx_QueueIn(msg_data[idx]);
              }
              msg_state = 0;
          }
          break;
    default: msg_len = 0; break;
    }
}
