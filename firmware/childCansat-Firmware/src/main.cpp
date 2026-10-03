#include <Arduino.h>
#include "dht11.h"

constexpr uint8_t DHT_PIN = 2;

dht11 sensor(DHT_PIN);

void setup() {
  Serial.begin(9600);
  sensor.begin();
  delay(1000); // DHT11 needs ~1 s to settle after power-up
}

void loop() {
  switch (sensor.read()) {
    case dht11::OK:
      Serial.print(F("Humidity: "));
      Serial.print(sensor.humidity());
      Serial.print(F(" %  Temperature: "));
      Serial.print(sensor.temperature());
      Serial.println(F(" C"));
      break;
    case dht11::ERROR_CHECKSUM:
      Serial.println(F("DHT11 checksum error"));
      break;
    case dht11::ERROR_TIMEOUT:
      Serial.println(F("DHT11 timeout (check wiring)"));
      break;
  }
  delay(2000);
}
