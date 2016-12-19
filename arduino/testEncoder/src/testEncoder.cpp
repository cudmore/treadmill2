#include "Arduino.h"

#include <Encoder.h> // http://www.pjrc.com/teensy/td_libs_Encoder.html

const int encoderPinA = 15;
const int encoderPinB = 16;

struct rotaryencoder
{
	//int pinA; // use pin 2
	//int pinB; // use pin 3
	long position;
	unsigned long updateInterval; //ms
	unsigned long lastUpdateTime; //now - trial.trialStartMillis
};

typedef struct rotaryencoder RotaryEncoder;

RotaryEncoder rotaryencoder; //structure

Encoder myEncoder(encoderPinA, encoderPinB);

/////////////////////////////////////////////////////////////
void setup()
{
  //rotaryencoder.pinA = encoderPinA;
  //rotaryencoder.pinB = encoderPinB;
  rotaryencoder.position = -999;
  rotaryencoder.updateInterval = 30; //ms
  rotaryencoder.lastUpdateTime = -999;

  //Encoder myEncoder(rotaryencoder.pinA, rotaryencoder.pinB);

  Serial.begin(115200);
}

/////////////////////////////////////////////////////////////
void serialOut(unsigned long now, String str, unsigned long val) {
	Serial.println(String(now) + "," + str + "," + val);
}

/////////////////////////////////////////////////////////////
//respond to incoming serial
void SerialIn(unsigned long now, String str) {
	serialOut(now, str, 1); //just echo serial input
	serialOut(now, "rotaryencoder.position", rotaryencoder.position);

}

/////////////////////////////////////////////////////////////
void updateEncoder(unsigned long now, long newPosition) {

	//only deal with rotary encoder when motor is off (wheel is free to turn)
	//if (trial.useMotor == 0) {
		long encoderDiff = abs(newPosition - rotaryencoder.position);
		if (encoderDiff > 0) {
			serialOut(now, "encoderTurn", newPosition);
			rotaryencoder.position = newPosition;
			//if ( (g_msIntoTrial - rotaryencoder.lastUpdateTime) > rotaryencoder.updateInterval ) {
			//	rotaryencoder.lastUpdateTime = g_msIntoTrial;
			//	newevent(now, "encoder", newPosition);
			//	//pulse
			//	digitalWrite(encoderOutPin, HIGH);
			//	digitalWrite(encoderOutPin, LOW);
			//}
		} //encoderDiff
	//} // useMotor
}

long newEncoderPos = -999;
String inString;
unsigned long now;

/////////////////////////////////////////////////////////////
void loop()
{
	now = millis();

	//
	//encoder
	newEncoderPos = myEncoder.read();
	updateEncoder(now, newEncoderPos);

	if (Serial.available() > 0) {
		inString = Serial.readStringUntil('\n');
		inString.replace("\n","");
		inString.replace("\r","");
		SerialIn(now, inString);
	}
}