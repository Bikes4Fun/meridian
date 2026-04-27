#include <OneWire.h>
#include <DallasTemperature.h>

OneWire oneWire(2);
DallasTemperature sensors(&oneWire);

void setup() {
  Serial.begin(9600);
  sensors.begin();
  Serial.println("boot"); 
  Serial.print("deviceCount=");
  Serial.println(sensors.getDeviceCount());
  if (sensors.getDeviceCount() > 0) {
    DeviceAddress addr;
    if (sensors.getAddress(addr, 0)) {
      Serial.print("addr0=");
      for (uint8_t i = 0; i < 8; i++) {
        if (addr[i] < 16) Serial.print("0");
        Serial.print(addr[i], HEX);
      }
      Serial.println();
    } else {
      Serial.println("addr0=unavailable");
    }
  }
}

void loop() {
  sensors.requestTemperatures();
  float tempC = sensors.getTempCByIndex(0);
  Serial.print("tempC=");
  Serial.println(tempC, 2);
  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("status=DISCONNECTED");
  }
  delay(1000);
}