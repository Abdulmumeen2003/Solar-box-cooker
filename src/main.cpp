
#include <Arduino.h>
#include <DHT.h>
#include <math.h>

// -------------------------------------
// MAX6675 connections
// -------------------------------------
const byte MAX6675_CS  = 9;
const byte MAX6675_SO  = 11;
const byte MAX6675_SCK = 10;

// -------------------------------------
// DHT11 connection
// -------------------------------------
#define DHTPIN 2
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);

// -------------------------------------
// Read the MAX6675 16-bit data
// -------------------------------------
uint16_t readMAX6675()
{
    uint16_t raw = 0;

    digitalWrite(MAX6675_CS, LOW);
    delayMicroseconds(10);

    for (int i = 15; i >= 0; i--)
    {
        digitalWrite(MAX6675_SCK, HIGH);
        delayMicroseconds(1);

        if (digitalRead(MAX6675_SO))
        {
            raw |= (uint16_t)(1U << i);
        }

        digitalWrite(MAX6675_SCK, LOW);
        delayMicroseconds(1);
    }

    digitalWrite(MAX6675_CS, HIGH);

    return raw;
}

// -------------------------------------
// Convert MAX6675 data to Celsius
// -------------------------------------
float readThermocoupleC()
{
    uint16_t raw = readMAX6675();

    // Bit 2 indicates an open thermocouple.
    if (raw & 0x04)
    {
        return NAN;
    }

    uint16_t temperatureData = (raw >> 3) & 0x0FFF;

    return temperatureData * 0.25;
}

// -------------------------------------
// Arduino initialization
// -------------------------------------
void setup()
{
    Serial.begin(9600);

    pinMode(MAX6675_CS, OUTPUT);
    pinMode(MAX6675_SO, INPUT);
    pinMode(MAX6675_SCK, OUTPUT);

    digitalWrite(MAX6675_CS, HIGH);
    digitalWrite(MAX6675_SCK, LOW);

    dht.begin();

    delay(1500);

    // CSV column headings
    Serial.println(
        "time_s,thermocouple_C,ambient_C,humidity_pct"
    );
}

// -------------------------------------
// Read and transmit both sensors
// -------------------------------------
void loop()
{
    unsigned long elapsedMs = millis();

    float thermocoupleC = readThermocoupleC();

    // DHT11 returns ambient temperature and humidity.
    float ambientC = dht.readTemperature();
    float humidity = dht.readHumidity();

    // Elapsed time in seconds
    Serial.print(elapsedMs / 1000.0, 1);
    Serial.print(',');

    // Thermocouple temperature
    if (isnan(thermocoupleC))
    {
        Serial.print("ERROR");
    }
    else
    {
        Serial.print(thermocoupleC, 2);
    }

    Serial.print(',');

    // DHT11 ambient temperature
    if (isnan(ambientC))
    {
        Serial.print("ERROR");
    }
    else
    {
        Serial.print(ambientC, 1);
    }

    Serial.print(',');

    // DHT11 relative humidity
    if (isnan(humidity))
    {
        Serial.println("ERROR");
    }
    else
    {
        Serial.println(humidity, 1);
    }

    // DHT11 should not be polled too frequently.
    delay(2000);
}