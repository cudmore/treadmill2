#include "Arduino.h"

const int startTrialPin = 3; //start trial when this pin goes ho
const int framePin = 4; //receive frame on this pin

volatile unsigned long newTrialTime = 0;

/////////////////////////////////////////////////////////////
void serialOut(unsigned long now, String str, unsigned long val) {
	Serial.println(String(now) + "," + str + "," + val);
}

/////////////////////////////////////////////////////////////
void startTrial_ISR() {
	//start trial received
	serialOut(millis(),"startTrial_ISR()",0);
}

/////////////////////////////////////////////////////////////
void frame_ISR() {
	serialOut(millis(),"frame_ISR()",0);
}

/////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////
void setup()
{
  pinMode(startTrialPin, INPUT);
  pinMode(framePin, INPUT);

  attachInterrupt(startTrialPin, startTrial_ISR, RISING);
  attachInterrupt(framePin, frame_ISR, RISING);

  pinMode(13, OUTPUT);

  Serial.begin(115200);
}

/////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////
void loop()
{

	if (digitalRead(startTrialPin)==HIGH) {
		digitalWrite(13,1);
		//serialOut(millis(),"YYY yyy",0);
	} else {
		digitalWrite(13,0);
	}
	delay(100);
}