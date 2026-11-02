#ifndef _CS_SERVO_ROBOT_ARM_H_
#define _CS_SERVO_ROBOT_ARM_H_

#include "csServo.h"

// SERVO OPERATION
Servo csServoRobotArm[5];
void hyCANSAT_SERVO_ROBOT_ARM_ATTACH()
{
	hyCANSAT_SERVO_ATTACH();
	if (!csServoRobotArm[0].attached())   csServoRobotArm[0].attach(D2);
	if (!csServoRobotArm[1].attached())   csServoRobotArm[1].attach(D3);
	if (!csServoRobotArm[2].attached())   csServoRobotArm[2].attach(D4);
	if (!csServoRobotArm[3].attached())   csServoRobotArm[3].attach(D5);
	if (!csServoRobotArm[4].attached())   csServoRobotArm[4].attach(D6);
}
void hyCANSAT_SERVO_ROBOT_ARM_DETACH()
{
	hyCANSAT_SERVO_DETACH();
	if (csServoRobotArm[0].attached())   csServoRobotArm[0].detach();
	if (csServoRobotArm[1].attached())   csServoRobotArm[1].detach();
	if (csServoRobotArm[2].attached())   csServoRobotArm[2].detach();
	if (csServoRobotArm[3].attached())   csServoRobotArm[3].detach();
	if (csServoRobotArm[4].attached())   csServoRobotArm[4].detach();
}

#endif
