#include <Arduino.h>
#include <Servo.h>

Servo myServo;            
const int servoPin = 9;   

void setup() {
  myServo.attach(servoPin); 
  Serial.begin(9600);       
  myServo.write(0);
  Serial.println("Arduino: Ready for degree input (0-180).");
}

void loop() {
  if (Serial.available() > 0) {
    int angle = Serial.parseInt();
    while(Serial.available() > 0) { Serial.read(); }

    if (angle >= 0 && angle <= 180) {
      myServo.write(angle);
      Serial.print("SUCCESS: Servo moved to ");
      Serial.print(angle);
      Serial.println(" degrees.");
    } else {
      Serial.print("ERROR: Invalid angle (");
      Serial.print(angle);
      Serial.println("). Please send 0-180.");
    }
  }
}