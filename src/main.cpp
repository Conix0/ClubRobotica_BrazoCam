#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  Serial.println("Nodo inicializado en reposo.");
}

void loop() {
  delay(1000);
}