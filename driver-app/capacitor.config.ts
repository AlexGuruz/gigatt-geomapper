import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.gigatt.driver',
  appName: 'GIGATT Driver',
  webDir: 'www',
  server: {
    // Allow loading from your backend (CORS must allow the capacitor:// origin or use cleartext for dev).
    androidScheme: 'https',
  },
  plugins: {
    Geolocation: {
      permissions: ['location', 'locationAlways'],
    },
  },
};

export default config;
