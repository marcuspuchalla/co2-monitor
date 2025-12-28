"""
CO2 Reader Module for TFA Dostmann AirControl Mini (31.5006)

Reads CO2 concentration and temperature from the USB HID device.
Based on reverse-engineered protocol from:
- https://github.com/JsBergbau/TFACO2AirCO2ntrol_CO2Meter
- https://github.com/MathieuSchopfer/tfa-airco2ntrol-mini
"""

import hid
import time
from dataclasses import dataclass
from typing import Optional

# Device identifiers
VENDOR_ID = 0x04D9
PRODUCT_ID = 0xA052

# Data type codes
CO2_CODE = 0x50  # 80 decimal
TEMP_CODE = 0x42  # 66 decimal

# Encryption key (sent to device to initialize)
KEY = bytes([0xC4, 0xC6, 0xC0, 0x92, 0x40, 0x23, 0xDC, 0x96])


@dataclass
class Reading:
    """A single reading from the CO2 monitor."""
    co2_ppm: Optional[int] = None
    temperature_celsius: Optional[float] = None
    timestamp: float = 0.0

    def is_complete(self) -> bool:
        """Check if both CO2 and temperature have been read."""
        return self.co2_ppm is not None and self.temperature_celsius is not None


class CO2Reader:
    """Reader for TFA Dostmann AirControl Mini CO2 Monitor."""

    def __init__(self):
        self.device: Optional[hid.device] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to the CO2 monitor device."""
        try:
            self.device = hid.device()
            self.device.open(VENDOR_ID, PRODUCT_ID)
            self.device.set_nonblocking(False)

            # Send key to initialize device (feature report)
            # Report ID 0x00 followed by the key
            self.device.send_feature_report(bytes([0x00]) + KEY)

            self._connected = True
            return True
        except IOError as e:
            print(f"Failed to connect to CO2 monitor: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from the device."""
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
        self.device = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected and self.device is not None

    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt data from device using XOR with key."""
        # The device uses a simple XOR encryption with shuffled bytes
        # Shuffle order: [2, 4, 0, 7, 1, 6, 5, 3]
        shuffle = [2, 4, 0, 7, 1, 6, 5, 3]
        phase1 = bytes([data[shuffle[i]] for i in range(8)])

        # XOR with key
        phase2 = bytes([phase1[i] ^ KEY[i] for i in range(8)])

        # Final transformation
        result = bytes([
            ((phase2[i] >> 3) | (phase2[(i - 1) % 8] << 5)) & 0xFF
            for i in range(8)
        ])

        return result

    def _parse_value(self, data: bytes) -> tuple[int, int]:
        """Parse decrypted data to extract type and value."""
        # First byte is the data type
        data_type = data[0]
        # Value is in bytes 1-2 (big endian)
        value = (data[1] << 8) | data[2]
        return data_type, value

    def read(self, timeout_seconds: float = 5.0) -> Reading:
        """
        Read CO2 and temperature from the device.

        Args:
            timeout_seconds: Maximum time to wait for complete reading

        Returns:
            Reading object with CO2 and temperature values
        """
        if not self.is_connected():
            raise IOError("Device not connected")

        reading = Reading(timestamp=time.time())
        start_time = time.time()

        while not reading.is_complete():
            if time.time() - start_time > timeout_seconds:
                break

            try:
                # Read 8 bytes from device
                data = self.device.read(8, timeout_ms=1000)
                if not data or len(data) < 8:
                    continue

                # Decrypt the data
                decrypted = self._decrypt(bytes(data))

                # Validate checksum (byte 3 should equal byte 0 + byte 1 + byte 2)
                checksum = (decrypted[0] + decrypted[1] + decrypted[2]) & 0xFF
                if checksum != decrypted[3]:
                    # Try without decryption (newer firmware)
                    data_type, value = self._parse_value(bytes(data))
                else:
                    data_type, value = self._parse_value(decrypted)

                # Parse based on data type
                if data_type == CO2_CODE:
                    reading.co2_ppm = value
                elif data_type == TEMP_CODE:
                    # Temperature formula: value / 16.0 - 273.15
                    reading.temperature_celsius = round(value / 16.0 - 273.15, 1)

            except IOError:
                # Device may have disconnected
                self._connected = False
                break

        return reading

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False


def list_devices():
    """List all compatible CO2 monitor devices."""
    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    return devices


if __name__ == "__main__":
    # Test reading
    print("Searching for CO2 monitor...")
    devices = list_devices()

    if not devices:
        print("No CO2 monitor found!")
        print(f"Looking for VID: 0x{VENDOR_ID:04X}, PID: 0x{PRODUCT_ID:04X}")
        exit(1)

    print(f"Found {len(devices)} device(s)")

    with CO2Reader() as reader:
        if reader.is_connected():
            print("Connected! Reading data...")
            reading = reader.read()
            print(f"CO2: {reading.co2_ppm} ppm")
            print(f"Temperature: {reading.temperature_celsius} °C")
        else:
            print("Failed to connect to device")
