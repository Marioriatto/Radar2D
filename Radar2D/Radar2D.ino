#include <Servo.h>
const int servoPin = 9, echo = 10, trigger = 11;

Servo servo;
// twelve Servo objects can be created on most boards

int angle = 0;    // variable to store the servo position

void setup() {
  pinMode(echo, INPUT);
  pinMode(trigger, OUTPUT);
  pinMode(servoPin, OUTPUT);
  servo.attach(servoPin);  // attaches the servo on pin 9 to the Servo object
  Serial.begin(9600);
  servo.write(0);
}

void loop() {
}
