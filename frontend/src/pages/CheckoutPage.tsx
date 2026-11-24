import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { api, isApiError } from '../utils/api';
import { fetchPaymentConfig, goToStripe, PaymentConfig, TEST_CARD } from '../utils/payments';

interface CreateOrderResponse {
  order: {
    id: string;
    order_number: string;
  };
  checkout_url: string | null;
}

export function CheckoutPage() {
  const { cart, refreshCart } = useCart();
  const navigate = useNavigate();
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payment, setPayment] = useState<PaymentConfig | null>(null);

  useEffect(() => {
    fetchPaymentConfig().then(setPayment);
  }, []);

  useEffect(() => {
    // Don't bounce to /cart while redirecting to Stripe (the cart is cleared then).
    if (cart && cart.items.length === 0 && !processing) {
      navigate('/cart');
    }
  }, [cart, navigate, processing]);

  const formatPrice = (price: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price);

  const handlePlaceOrder = async () => {
    setProcessing(true);
    setError(null);

    try {
      const response = await api.post<CreateOrderResponse>('/orders', {
        notes: payment?.enabled ? null : 'Portfolio demo checkout',
      });
      if (response.data.checkout_url) {
        // Card details are entered on Stripe's page, never on this site.
        goToStripe(response.data.checkout_url);
        return;
      }
      await refreshCart();
      navigate(`/orders/${response.data.order.id}?success=true`);
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Failed to place order');
      setProcessing(false);
    }
  };

  if (!cart || !payment) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-accent-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  const subtotal = cart.subtotal;

  return (
    <div className="min-h-screen bg-sand-50">
      <div className="bg-white border-b border-ink-100">
        <div className="container-page py-8">
          <h1 className="text-display-lg font-display text-ink-900">
            {payment.enabled ? 'Checkout' : 'Demo Checkout'}
          </h1>
          <p className="text-ink-600 mt-2">
            {payment.enabled
              ? 'You will pay on a secure Stripe page, then come back here.'
              : 'Portfolio mode: no real payment or shipping information is collected.'}
          </p>
        </div>
      </div>

      <div className="container-page py-12">
        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                {error}
              </div>
            )}

            <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100">
              {payment.enabled ? (
                <>
                  <h2 className="font-display text-xl text-ink-900 mb-2">Payment</h2>
                  <p className="text-ink-600">
                    Your items are reserved when you continue. Stripe handles the card
                    details, and your order is marked paid as soon as Stripe confirms it.
                  </p>
                  {payment.testMode && (
                    <div className="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-900">
                      <p className="font-medium">Test mode: no real money is charged.</p>
                      <p className="mt-1">
                        Use card <span className="font-mono">{TEST_CARD}</span>, any future
                        expiry date, any 3-digit CVC and any postal code.
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <h2 className="font-display text-xl text-ink-900 mb-2">Demo Payment</h2>
                  <p className="text-ink-600">
                    This deployment does not charge a card. Placing the order creates a
                    synthetic portfolio order in PostgreSQL and clears the authenticated
                    cart.
                  </p>
                </>
              )}
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100">
              <div className="flex justify-between items-center mb-4">
                <h2 className="font-display text-xl text-ink-900">Order Items</h2>
                <Link to="/cart" className="text-accent-600 hover:text-accent-700">
                  Edit cart
                </Link>
              </div>

              <div className="divide-y divide-ink-100">
                {cart.items.map((item) => (
                  <div key={item.id} className="py-4 flex gap-4 items-center">
                    <div className="w-16 h-16 bg-ink-100 rounded overflow-hidden flex-shrink-0">
                      {item.product.images?.[0] ? (
                        <img
                          src={item.product.images[0].url}
                          alt={item.product.name}
                          className="w-full h-full object-cover"
                        />
                      ) : null}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-ink-900">{item.product.name}</p>
                      <p className="text-sm text-ink-600">Qty: {item.quantity}</p>
                    </div>
                    <p className="font-medium text-ink-900">
                      {formatPrice(item.quantity * item.price)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100 sticky top-24">
              <h2 className="font-display text-xl text-ink-900 mb-6">
                Order Summary
              </h2>
              <div className="flex justify-between text-ink-600 mb-4">
                <span>Subtotal</span>
                <span>{formatPrice(subtotal)}</span>
              </div>
              <div className="flex justify-between text-ink-600 mb-4">
                <span>Tax</span>
                <span>{formatPrice(0)}</span>
              </div>
              <div className="flex justify-between text-ink-600 mb-6">
                <span>Shipping</span>
                <span>{formatPrice(0)}</span>
              </div>
              <div className="border-t border-ink-100 pt-4 flex justify-between text-lg font-display font-bold text-ink-900 mb-6">
                <span>Total</span>
                <span>{formatPrice(subtotal)}</span>
              </div>

              <button
                onClick={handlePlaceOrder}
                disabled={processing || cart.items.length === 0}
                className="w-full btn-primary py-4 text-lg disabled:opacity-50"
              >
                {processing
                  ? payment.enabled
                    ? 'Opening secure payment…'
                    : 'Creating order…'
                  : payment.enabled
                    ? 'Continue to payment'
                    : 'Place Demo Order'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
