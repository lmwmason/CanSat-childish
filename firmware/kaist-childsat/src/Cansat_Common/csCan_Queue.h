#ifndef _CS_QUEUE_H_
#define _CS_QUEUE_H_


// Pl_Rx_Queue :: for Pl data
unsigned char Pl_Rx_QueueInIdx = 0;
unsigned char Pl_Rx_QueueOutIdx = 0;
unsigned char Pl_Rx_Queue[MAX_PL_RX_QUEUE];	

// Gs_Rx_Queue :: for Gs Data
unsigned char Gs_Rx_QueueInIdx = 0;
unsigned char Gs_Rx_QueueOutIdx = 0;
unsigned char Gs_Rx_Queue[MAX_GS_RX_QUEUE];	

// Pl_Tx_Queue :: for Pl data 
unsigned char Pl_Tx_QueueInIdx = 0;
unsigned char Pl_Tx_QueueOutIdx = 0;
unsigned char Pl_Tx_Queue[MAX_PL_TX_QUEUE];	

// Gs_Tx_Queue :: for Gs Tx data
unsigned char Gs_Tx_QueueInIdx = 0;
unsigned char Gs_Tx_QueueOutIdx = 0;
unsigned char Gs_Tx_Queue[MAX_GS_TX_QUEUE];

// Gs_Tx_Frame :: for Gx Tx Frame 
unsigned char Gs_Tx_Frame_QueueInIdx = 0;
unsigned char Gs_Tx_Frame_QueueOutIdx = 0;
unsigned char Gs_Tx_Frame_Queue[MAX_GS_TX_FRAME_QUEUE];	


// Pl_Rx_Queue :: Operations //
#define Pl_Rx_QueueIn(macData)  { Pl_Rx_QueueInIdx  &= PL_RX_QUEUE_IDX_MASK;	Pl_Rx_Queue[Pl_Rx_QueueInIdx] = (macData) ; Pl_Rx_QueueInIdx++   ; }
#define Pl_Rx_QueueOut(macData) { Pl_Rx_QueueOutIdx &= PL_RX_QUEUE_IDX_MASK;	(macData) = Pl_Rx_Queue[Pl_Rx_QueueOutIdx]; Pl_Rx_QueueOutIdx++  ; }
#define Pl_Rx_QueueFlush()      { Pl_Rx_QueueInIdx = Pl_Rx_QueueOutIdx; }

// Gs_Rx_Queue :: Operations //
#define Gs_Rx_QueueIn(macData)  { Gs_Rx_QueueInIdx  &= GS_RX_QUEUE_IDX_MASK;	Gs_Rx_Queue[Gs_Rx_QueueInIdx] = (macData) ; Gs_Rx_QueueInIdx++   ; }
#define Gs_Rx_QueueOut(macData) { Gs_Rx_QueueOutIdx &= GS_RX_QUEUE_IDX_MASK;	(macData) = Gs_Rx_Queue[Gs_Rx_QueueOutIdx]; Gs_Rx_QueueOutIdx++  ; }
#define Gs_Rx_QueueFlush()      { Gs_Rx_QueueInIdx = Gs_Rx_QueueOutIdx; }

// Pl_Tx_Queue :: Operations //
#define Pl_Tx_QueueIn(macData)  { Pl_Tx_QueueInIdx  &= PL_TX_QUEUE_IDX_MASK;	Pl_Tx_Queue[Pl_Tx_QueueInIdx] = (macData) ; Pl_Tx_QueueInIdx++   ; }
#define Pl_Tx_QueueOut(macData) { Pl_Tx_QueueOutIdx &= PL_TX_QUEUE_IDX_MASK;	(macData) = Pl_Tx_Queue[Pl_Tx_QueueOutIdx]; Pl_Tx_QueueOutIdx++  ; }
#define Pl_Tx_QueueFlush()      { Pl_Tx_QueueInIdx = Pl_Tx_QueueOutIdx; }

// Gs_Tx_Queue :: Operations //
#define Gs_Tx_QueueIn(macData)  { Gs_Tx_QueueInIdx  &= GS_TX_QUEUE_IDX_MASK;	Gs_Tx_Queue[Gs_Tx_QueueInIdx] = (macData) ; Gs_Tx_QueueInIdx++   ; }
#define Gs_Tx_QueueOut(macData) { Gs_Tx_QueueOutIdx &= GS_TX_QUEUE_IDX_MASK;	(macData) = Gs_Tx_Queue[Gs_Tx_QueueOutIdx]; Gs_Tx_QueueOutIdx++  ; }
#define Gs_Tx_QueueFlush()      { Gs_Tx_QueueInIdx = Gs_Tx_QueueOutIdx; }

// Gs_Tx_Frame_Queue :: Operation //
#define Gs_Tx_Frame_QueueIn(macData)  { Gs_Tx_Frame_QueueInIdx  &= GS_TX_FRAME_QUEUE_IDX_MASK;	Gs_Tx_Frame_Queue[Gs_Tx_Frame_QueueInIdx] = (macData) ; Gs_Tx_Frame_QueueInIdx++   ; }
#define Gs_Tx_Frame_QueueOut(macData) { Gs_Tx_Frame_QueueOutIdx &= GS_TX_FRAME_QUEUE_IDX_MASK;	(macData) = Gs_Tx_Frame_Queue[Gs_Tx_Frame_QueueOutIdx]; Gs_Tx_Frame_QueueOutIdx++  ; }
#define Gs_Tx_Frame_QueueFlush()      { Gs_Tx_Frame_QueueInIdx = Gs_Tx_Frame_QueueOutIdx; }


// QueueIsEmpty()
#define Pl_Rx_QueueIsEmpty() ( Pl_Rx_QueueInIdx == Pl_Rx_QueueOutIdx )
#define Gs_Rx_QueueIsEmpty() ( Gs_Rx_QueueInIdx == Gs_Rx_QueueOutIdx )
#define Pl_Tx_QueueIsEmpty() ( Pl_Tx_QueueInIdx == Pl_Tx_QueueOutIdx )
#define Gs_Tx_QueueIsEmpty() ( Gs_Tx_QueueInIdx == Gs_Tx_QueueOutIdx )
#define Gs_Tx_Frame_QueueIsEmpty()    ( Gs_Tx_Frame_QueueInIdx == Gs_Tx_Frame_QueueOutIdx )

// QueueIsNotEmpty()
#define Pl_Rx_QueueIsNotEmpty() ( Pl_Rx_QueueInIdx != Pl_Rx_QueueOutIdx )
#define Gs_Rx_QueueIsNotEmpty() ( Gs_Rx_QueueInIdx != Gs_Rx_QueueOutIdx )
#define Pl_Tx_QueueIsNotEmpty() ( Pl_Tx_QueueInIdx != Pl_Tx_QueueOutIdx )
#define Gs_Tx_QueueIsNotEmpty() ( Gs_Tx_QueueInIdx != Gs_Tx_QueueOutIdx )
#define Gs_Tx_Frame_QueueIsNotEmpty() ( Gs_Tx_Frame_QueueInIdx != Gs_Tx_Frame_QueueOutIdx )

////////////////////////////////////////////////////////////////////////
unsigned char Cam_TxFrameData[MAX_TX_FRAME_DATA_SIZE];
inline void PUT_BYTE(unsigned char iByte) { Gs_Tx_Frame_QueueIn(iByte); }

inline void SEND_CAMERA_PACKET(unsigned char *iData, unsigned char iSize)
{
	if (iSize == 0) return;
	for (unsigned char i = 0; i < iSize; i++)
		Cam_TxFrameData[i] = iData[i];

	for (unsigned char i = 0; i < iSize; i++)
	{
		unsigned char b = Cam_TxFrameData[i];
		PUT_BYTE(b);
	}
}


#define GTX_BUFF_SIZE (CAMERA_ONE_BLOCK_SIZE+16)
unsigned char gTx_buff[2][GTX_BUFF_SIZE];
unsigned char gTx_page = 0;
unsigned char gTx_idx = 0;

inline void TX_CAMERA_BYTE_IN_TX_BUFF()
{
	if (gTx_idx)
	{
		unsigned char w_page = gTx_page;
		unsigned char w_idx = gTx_idx;

		gTx_page = 1 - w_page;
		gTx_idx = 0;

		SEND_CAMERA_PACKET(gTx_buff[w_page], ((w_idx < GTX_BUFF_SIZE) ? w_idx : GTX_BUFF_SIZE));
	}
}

// Buffered Version 
#if 1
inline void TX_CAMERA_BYTE(unsigned char uc)
{
	if (gTx_idx < GTX_BUFF_SIZE)
	{
		gTx_buff[gTx_page][gTx_idx] = uc;
		gTx_idx++;
	}
	if (GTX_BUFF_SIZE <= gTx_idx)
	{
		TX_CAMERA_BYTE_IN_TX_BUFF();
	}
}
#else
// Direct Send Version
inline void TX_CAMERA_BYTE(unsigned char uc) { hyGsTxByte(uc); }
#endif

#endif