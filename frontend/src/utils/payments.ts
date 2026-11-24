import { api } from './api';

export interface PaymentConfig {
  enabled: boolean;
  testMode: boolean;
  currency: string;
}

const DEMO: PaymentConfig = { enabled: false, testMode: false, currency: 'usd' };

/** Whether the API takes real (Stripe) payments. Falls back to demo mode on error. */
export async function fetchPaymentConfig(): Promise<PaymentConfig> {
  try {
    const { data } = await api.get<{ enabled: boolean; test_mode: boolean; currency: string }>(
      '/payments/config',
    );
    return { enabled: data.enabled, testMode: data.test_mode, currency: data.currency };
  } catch {
    return DEMO;
  }
}

/** Send the browser to Stripe's hosted payment page. */
export function goToStripe(url: string): void {
  window.location.assign(url);
}

export const TEST_CARD = '4242 4242 4242 4242';
