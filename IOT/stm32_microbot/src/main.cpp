#include <Arduino.h>

void setup() {
  pinMode(PC13, OUTPUT); // Set the LED pin as output
}

void loop() {
  digitalWrite(PC13, HIGH); // Turn the LED on
  delay(500); // Wait for one second
  digitalWrite(PC13, LOW);  // Turn the LED off
  delay(500); // Wait for one second
}
