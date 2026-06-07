#include <Servo.h>. 

const int trigPin = 10;
const int echoPin = 11;

long duration;
int distance;
Servo myServo;
void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  Serial.begin(9600);
  myServo.attach(9);
}
void loop() {
  for(int i=15;i<=165;i++){  
  myServo.write(i);
  delay(30);
  distance = 0;
  
  Serial.print(i); // Sends the current degree into the Serial Port
  Serial.print(":");
  Serial.print(distance); // Sends the distance value into the Serial Port
  Serial.print(",");
  }
  for(int i=165;i>15;i--){  
  myServo.write(i);
  delay(30);
  distance = calculateDistance();
  Serial.print(i);
  Serial.print(":");
  Serial.print(distance);
  Serial.print(",");
  }
}