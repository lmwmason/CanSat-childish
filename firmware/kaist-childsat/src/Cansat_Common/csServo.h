#ifndef _CS_SERVO_H_
#define _CS_SERVO_H_

// SERVO OPERATION
Servo csServo[2];
void hyCANSAT_SERVO_ATTACH()
{
#if defined(SERVO_TEST_TA) || defined(SERVO_TEST_AT) || defined(SERVO_TEST_DT)
    return;
#endif
	if (!csServo[0].attached())   csServo[0].attach(D0);
	if (!csServo[1].attached())   csServo[1].attach(D1);
}

void hyCANSAT_SERVO_DETACH()
{
	if (csServo[0].attached())   csServo[0].detach();
	if (csServo[1].attached())   csServo[1].detach();
}

#endif
