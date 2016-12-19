#include "Arduino.h"

const int startTrialPin = 3; //start trial when this pin goes ho
const int framePin = 23; //receive frame on this pin

volatile unsigned long newTrialTime = 0;

unsigned long numFrames = 0;
unsigned long lastInterrupt = 0;
unsigned long bounceMillis = 10;
unsigned long thisInterval = 0;

/////////////////////////////////////////////////////////////
void serialOut(unsigned long now, String str, unsigned long val) {
	Serial.println(String(now) + "," + str + "," + val);
}
/////////////////////////////////////////////////////////////
void startTrial_ISR() {
	//start trial received
	unsigned long now = millis();
	serialOut(now,"startTrial_ISR() numFrames=",numFrames);
	numFrames = 0;
}
/////////////////////////////////////////////////////////////
void frame_ISR() {
	unsigned long now = millis();
	if (now < (lastInterrupt + bounceMillis)) {
		serialOut(now,"frame bounced",numFrames);
	} else {
		thisInterval = now - lastInterrupt;
		lastInterrupt = now;
		numFrames += 1;
		serialOut(now,"numFrames=",numFrames);
		serialOut(now,"   thisInterval=",thisInterval);
	}
}
/////////////////////////////////////////////////////////////
void setup()
{
  pinMode(startTrialPin, INPUT);
  pinMode(framePin, INPUT);

  attachInterrupt(startTrialPin, startTrial_ISR, FALLING);
  attachInterrupt(framePin, frame_ISR, RISING); //RISING, CHANGE

  numFrames = 0;
  
  Serial.begin(115200);
}
/////////////////////////////////////////////////////////////
void loop()
{

	//delay(100);
}