#include <Servo.h>. 

const int trigPin = 10;
const int echoPin = 11;

long duration;
int distance = 0;
Servo myServo;
void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  Serial.begin(9600);
  myServo.attach(9);
}
void loop() {
  for(int i=0;i<=180;i++){  
  myServo.write(i);
  delay(10);
  
  Serial.print(i); // Sends the current degree into the Serial Port
  Serial.print(":");
  Serial.print(distance); // Sends the distance value into the Serial Port
  Serial.print(",");
  }
  for(int i=180;i>0;i--){  
  myServo.write(i);
  delay(10);
  Serial.print(i);
  Serial.print(":");
  Serial.print(distance);
  Serial.print(",");
  }

}