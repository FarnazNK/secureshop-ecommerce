import { api, isApiError } from './api';

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

/** A random key for the Idempotency-Key header (crypto.randomUUID needs HTTPS or localhost). */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/** What to tell the shopper when placing an order fails. */
export function checkoutErrorMessage(err: unknown): string {
  if (!isApiError(err)) return 'Could not place your order. Check your connection and try again.';
  if (err.status === 503 || err.status === 429) {
    return 'Payments are busy right now. Your cart is saved; try again in a few seconds.';
  }
  if (err.status === 409) {
    return `${err.message}. Your cart has been updated; review it and try again.`;
  }
  return err.message || 'Could not place your order. Try again.';
}
