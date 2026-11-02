// IMU Main Operation
// 1. UART Mode Set
// 2. IMU Data Get
// 3. IMU Data Send 
void hyCANSAT_IMU_OPERATION()
{
	imu_recv_flag = 0;
	hyRxMode_Set(RxMode_IMU);
	hyTransUartUntil(&imu_recv_flag, 0, WAIT_CNT_IMU);
	hyTransUartWait(WAIT_CNT_SEND);
}
