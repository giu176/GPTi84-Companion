#include <SoftwareSerial.h>

// Enter the module's AT mode according to its carrier instructions before reset/upload.
// Many ZS-040 boards require holding the KEY button while power is applied and use 38400 baud.
SoftwareSerial bluetooth(10, 11);

void setup() {
  Serial.begin(115200);
  bluetooth.begin(38400);
  Serial.println(F("HC-05 AT console ready."));
  Serial.println(F("Set Serial Monitor to Both NL & CR, 115200 baud."));
  Serial.println(F("Suggested commands: AT, AT+ROLE=0, AT+NAME=TI84-RELAY, AT+UART=9600,0,0"));
  Serial.println(F("Set a non-default PIN using the command supported by your firmware (often AT+PSWD=8462)."));
}

void loop() {
  while (Serial.available()) bluetooth.write(Serial.read());
  while (bluetooth.available()) Serial.write(bluetooth.read());
}
