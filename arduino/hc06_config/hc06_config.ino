#include <SoftwareSerial.h>

// HC-06 is normally always a Bluetooth slave and commonly accepts AT commands
// while unpaired at its current data baud. Commands vary between clones.
// ZS-040 TXD -> D10. D11 -> 1k -> RXD, with 2k from RXD to GND.
SoftwareSerial bluetooth(10, 11);

void setup() {
  Serial.begin(115200);
  bluetooth.begin(9600);
  Serial.println(F("HC-06 AT console ready at module baud 9600."));
  Serial.println(F("Keep the module powered but disconnected from every phone."));
  Serial.println(F("Start with AT. Common clone commands include AT+NAME..., AT+PIN..., and AT+BAUD4."));
  Serial.println(F("Use No line ending first; clone command syntax varies."));
}

void loop() {
  while (Serial.available()) bluetooth.write(Serial.read());
  while (bluetooth.available()) Serial.write(bluetooth.read());
}
