/**
 * CO2 Reader Module
 *
 * Handles USB HID communication with TFA Dostmann AirControl Mini CO2 Meter.
 * Device: TFA 31.5006
 * Vendor ID: 0x04D9
 * Product ID: 0xA052
 */

import HID from 'node-hid';

// Device identifiers
const VENDOR_ID = 0x04d9;
const PRODUCT_ID = 0xa052;

// XOR encryption key (used by the device)
const XOR_KEY = new Uint8Array([
  0x86, 0x41, 0xc9, 0xa8, 0x7f, 0x41, 0x3c, 0xac
]);

export interface CO2Reading {
  co2Ppm: number | null;
  temperatureCelsius: number | null;
  timestamp: Date;
}

export interface DeviceInfo {
  product: string;
  vendorId: string;
  productId: string;
  path: string;
}

/**
 * Decrypt data from the CO2 sensor using XOR cipher.
 */
function decrypt(data: Buffer): Buffer {
  const result = Buffer.alloc(8);
  const shuffle = [2, 4, 0, 7, 1, 6, 5, 3];

  // Phase 1: Shuffle
  for (let i = 0; i < 8; i++) {
    result[shuffle[i]] = data[i];
  }

  // Phase 2: XOR with key
  for (let i = 0; i < 8; i++) {
    result[i] ^= XOR_KEY[i];
  }

  // Phase 3: Shift operations
  const temp = Buffer.alloc(8);
  for (let i = 0; i < 8; i++) {
    temp[i] = ((result[i] >> 3) | (result[(i + 7) % 8] << 5)) & 0xff;
  }

  // Phase 4: Subtract with magic number
  const magic = 0x23;
  for (let i = 0; i < 8; i++) {
    temp[i] = (temp[i] - magic) & 0xff;
  }

  return temp;
}

/**
 * List all connected CO2 devices.
 */
export function listDevices(): DeviceInfo[] {
  const devices = HID.devices();
  return devices
    .filter(d => d.vendorId === VENDOR_ID && d.productId === PRODUCT_ID)
    .map(d => ({
      product: d.product || 'CO2 Monitor',
      vendorId: `0x${d.vendorId.toString(16).padStart(4, '0').toUpperCase()}`,
      productId: `0x${d.productId.toString(16).padStart(4, '0').toUpperCase()}`,
      path: d.path || ''
    }));
}

/**
 * CO2 Reader class for reading from the sensor.
 */
export class CO2Reader {
  private device: HID.HID | null = null;
  private lastReading: CO2Reading = {
    co2Ppm: null,
    temperatureCelsius: null,
    timestamp: new Date()
  };

  /**
   * Connect to the CO2 sensor.
   */
  connect(): boolean {
    try {
      const devices = listDevices();
      if (devices.length === 0) {
        console.error('No CO2 device found');
        return false;
      }

      this.device = new HID.HID(VENDOR_ID, PRODUCT_ID);

      // Send initialization command
      const initCmd = Buffer.alloc(9);
      initCmd[0] = 0x00; // Report ID
      this.device.sendFeatureReport(Array.from(initCmd));

      console.log(`Connected to CO2 sensor: ${devices[0].product}`);
      return true;
    } catch (error) {
      console.error('Failed to connect to CO2 sensor:', error);
      return false;
    }
  }

  /**
   * Disconnect from the sensor.
   */
  disconnect(): void {
    if (this.device) {
      this.device.close();
      this.device = null;
      console.log('Disconnected from CO2 sensor');
    }
  }

  /**
   * Check if connected to the sensor.
   */
  isConnected(): boolean {
    return this.device !== null;
  }

  /**
   * Read data from the sensor.
   * Returns the latest reading after processing available data.
   */
  read(timeoutMs: number = 5000): CO2Reading {
    if (!this.device) {
      return this.lastReading;
    }

    const startTime = Date.now();
    let co2 = this.lastReading.co2Ppm;
    let temp = this.lastReading.temperatureCelsius;

    try {
      while (Date.now() - startTime < timeoutMs) {
        const data = this.device.readTimeout(100);

        if (!data || data.length < 8) {
          continue;
        }

        const buffer = Buffer.from(data);
        const decrypted = decrypt(buffer);

        // Validate checksum
        const checksum = (decrypted[0] + decrypted[1] + decrypted[2]) & 0xff;
        if (checksum !== decrypted[3]) {
          continue;
        }

        const op = decrypted[0];
        const value = (decrypted[1] << 8) | decrypted[2];

        // CO2 reading (op = 0x50)
        if (op === 0x50) {
          co2 = value;
        }
        // Temperature reading (op = 0x42)
        else if (op === 0x42) {
          temp = value / 16.0 - 273.15;
          temp = Math.round(temp * 10) / 10; // Round to 1 decimal
        }

        // If we have both readings, return
        if (co2 !== null && temp !== null) {
          this.lastReading = {
            co2Ppm: co2,
            temperatureCelsius: temp,
            timestamp: new Date()
          };
          return this.lastReading;
        }
      }
    } catch (error) {
      console.error('Error reading from sensor:', error);
    }

    // Return whatever we have
    if (co2 !== null || temp !== null) {
      this.lastReading = {
        co2Ppm: co2,
        temperatureCelsius: temp,
        timestamp: new Date()
      };
    }

    return this.lastReading;
  }

  /**
   * Get the last reading without blocking.
   */
  getLastReading(): CO2Reading {
    return this.lastReading;
  }
}

// Test if run directly
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('CO2 Reader Test');
  console.log('===============');

  const devices = listDevices();
  console.log(`Found ${devices.length} device(s):`, devices);

  if (devices.length > 0) {
    const reader = new CO2Reader();
    if (reader.connect()) {
      console.log('Reading from sensor...');
      const reading = reader.read();
      console.log(`CO2: ${reading.co2Ppm} ppm`);
      console.log(`Temperature: ${reading.temperatureCelsius}°C`);
      reader.disconnect();
    }
  }
}
