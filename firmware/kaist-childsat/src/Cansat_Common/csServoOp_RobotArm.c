void hyCANSAT_SERVO_ROBOT_ARM_OPERATION_WITH_ATLM()
{
	hyCANSAT_SERVO_ROBOT_ARM_ATTACH();

	csServo[0].write(255-ad_data[0]);
	csServo[1].write(ad_data[1]); // when use 
	csServoRobotArm[0].write(ad_data[1]); // when use // same
	csServoRobotArm[1].write(ad_data[2]); // when use 
	csServoRobotArm[2].write(255-ad_data[3]); // when use 
	csServoRobotArm[3].write(255-ad_data[4]); // when use 
	csServoRobotArm[4].write(255-ad_data[5]); // when use 
}