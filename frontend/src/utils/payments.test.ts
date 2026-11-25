import { describe, expect, it } from 'vitest';
import { checkoutErrorMessage, newIdempotencyKey } from './payments';

const apiError = (status: number, message: string) => ({ status, code: 'X', message });

describe('newIdempotencyKey', () => {
  it('returns a different key each time, long enough for the API', () => {
    const a = newIdempotencyKey();
    const b = newIdempotencyKey();
    expect(a).not.toBe(b);
    expect(a.length).toBeGreaterThanOrEqual(8);
  });
});

describe('checkoutErrorMessage', () => {
  it('tells the shopper the cart is saved when payments are busy', () => {
    expect(checkoutErrorMessage(apiError(503, 'unavailable'))).toMatch(/cart is saved/);
    expect(checkoutErrorMessage(apiError(429, 'slow down'))).toMatch(/cart is saved/);
  });

  it('explains stock problems', () => {
    expect(checkoutErrorMessage(apiError(409, 'insufficient stock for Mug'))).toMatch(
      /^insufficient stock for Mug\. Your cart has been updated/,
    );
  });

  it('handles network failures', () => {
    expect(checkoutErrorMessage(new Error('Network Error'))).toMatch(/connection/);
  });
});
