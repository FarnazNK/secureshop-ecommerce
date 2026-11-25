import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api, isApiError } from '../utils/api';
import { fetchPaymentConfig, goToStripe, PaymentConfig } from '../utils/payments';

interface BackendOrderItem {
  id: string;
  product_id: string | null;
  product_name: string;
  product_slug: string;
  unit_price: string | number;
  quantity: number;
  line_total: string | number;
}

interface BackendOrder {
  id: string;
  order_number: string;
  status: string;
  subtotal: string | number;
  tax: string | number;
  shipping: string | number;
  total: string | number;
  items: BackendOrderItem[];
  notes?: string | null;
  created_at: string;
  paid_at?: string | null;
  amount_refunded?: string | number;
  dispute_status?: string | null;
}

interface OrderItem {
  id: string;
  productId: string | null;
  productName: string;
  productSlug: string;
  unitPrice: number;
  quantity: number;
  lineTotal: number;
}

interface Order {
  id: string;
  orderNumber: string;
  status: string;
  subtotal: number;
  tax: number;
  shipping: number;
  total: number;
  items: OrderItem[];
  notes?: string | null;
  createdAt: string;
  paidAt?: string | null;
  amountRefunded: number;
  disputeStatus?: string | null;
}

type PaymentNotice = 'confirming' | 'paid' | 'processing' | 'cancelled' | null;

const SYNC_ATTEMPTS = 6;
const SYNC_INTERVAL_MS = 2000;

function mapOrder(order: BackendOrder): Order {
  return {
    id: order.id,
    orderNumber: order.order_number,
    status: order.status,
    subtotal: Number(order.subtotal),
    tax: Number(order.tax),
    shipping: Number(order.shipping),
    total: Number(order.total),
    items: order.items.map((item) => ({
      id: item.id,
      productId: item.product_id,
      productName: item.product_name,
      productSlug: item.product_slug,
      unitPrice: Number(item.unit_price),
      quantity: item.quantity,
      lineTotal: Number(item.line_total),
    })),
    notes: order.notes,
    createdAt: order.created_at,
    paidAt: order.paid_at,
    amountRefunded: Number(order.amount_refunded ?? 0),
    disputeStatus: order.dispute_status,
  };
}

export function OrdersPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { id: routeId, orderId } = useParams();
  const activeOrderId = orderId ?? routeId;
  const [searchParams] = useSearchParams();
  const isSuccess = searchParams.get('success') === 'true';
  const checkoutResult = searchParams.get('checkout');

  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payment, setPayment] = useState<PaymentConfig | null>(null);
  const [notice, setNotice] = useState<PaymentNotice>(null);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    fetchPaymentConfig().then(setPayment);
  }, []);

  // After Stripe redirects back, confirm the payment directly with the API.
  // The webhook is the source of truth; this just avoids showing "pending"
  // for the few seconds before it arrives.
  const confirmPayment = useCallback(async (id: string) => {
    setNotice('confirming');
    for (let attempt = 0; attempt < SYNC_ATTEMPTS; attempt += 1) {
      try {
        const { data } = await api.post<BackendOrder>(`/orders/${id}/sync-payment`, {});
        const order = mapOrder(data);
        setSelectedOrder(order);
        if (order.status === 'paid') {
          setNotice('paid');
          return;
        }
        if (order.status === 'cancelled') {
          setNotice('cancelled');
          return;
        }
      } catch {
        // Keep trying; a transient error here doesn't mean the payment failed.
      }
      await new Promise((resolve) => setTimeout(resolve, SYNC_INTERVAL_MS));
    }
    setNotice('processing');
  }, []);

  const payNow = async (id: string) => {
    setPaying(true);
    setError(null);
    try {
      const { data } = await api.post<{ checkout_url: string }>(
        `/orders/${id}/checkout-session`,
        {},
      );
      goToStripe(data.checkout_url);
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Could not open the payment page');
      setPaying(false);
    }
  };

  const formatPrice = (price: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price);

  const formatDate = (date: string) =>
    new Date(date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-amber-100 text-amber-800';
      case 'paid':
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'shipped':
        return 'bg-purple-100 text-purple-800';
      case 'delivered':
        return 'bg-green-100 text-green-800';
      case 'cancelled':
        return 'bg-red-100 text-red-800';
      case 'refunded':
        return 'bg-ink-100 text-ink-700';
      default:
        return 'bg-ink-100 text-ink-800';
    }
  };

  useEffect(() => {
    if (!user) {
      navigate('/login?redirect=/orders');
      return;
    }

    setLoading(true);
    setError(null);

    if (activeOrderId) {
      api
        .get<BackendOrder>(`/orders/${activeOrderId}`)
        .then((response) => {
          setSelectedOrder(mapOrder(response.data));
          if (checkoutResult === 'success') {
            confirmPayment(activeOrderId);
          } else if (checkoutResult === 'cancelled') {
            setNotice('cancelled');
          }
        })
        .catch((err) => {
          setError(isApiError(err) ? err.message : 'Order not found');
        })
        .finally(() => setLoading(false));
    } else {
      api
        .get<BackendOrder[]>('/orders')
        .then((response) => setOrders(response.data.map(mapOrder)))
        .catch((err) => {
          setError(isApiError(err) ? err.message : 'Failed to load orders');
        })
        .finally(() => setLoading(false));
    }
  }, [user, navigate, activeOrderId, checkoutResult, confirmPayment]);

  if (loading) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-accent-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (activeOrderId && selectedOrder) {
    return (
      <div className="min-h-screen bg-sand-50">
        {isSuccess && (
          <div className="bg-green-600 text-white py-4">
            <div className="container-page">
              <p className="font-medium">
                Demo order created successfully. No real payment was processed.
              </p>
            </div>
          </div>
        )}
        {notice && (
          <div
            role="status"
            className={`py-4 ${
              notice === 'paid'
                ? 'bg-green-600 text-white'
                : notice === 'cancelled'
                  ? 'bg-amber-100 text-amber-900'
                  : 'bg-ink-900 text-white'
            }`}
          >
            <div className="container-page">
              <p className="font-medium">
                {notice === 'confirming' && 'Confirming your payment with Stripe…'}
                {notice === 'paid' && 'Payment received. Thank you, your order is confirmed.'}
                {notice === 'processing' &&
                  'Stripe is still processing your payment. This page will show Paid once it is confirmed; refresh in a minute.'}
                {notice === 'cancelled' &&
                  (selectedOrder.status === 'cancelled'
                    ? 'This checkout expired, so the order was cancelled and its items were returned to stock.'
                    : 'Payment was not completed. Your items stay reserved for about 30 minutes; use Pay now to finish.')}
              </p>
            </div>
          </div>
        )}

        <div className="bg-white border-b border-ink-100">
          <div className="container-page py-8">
            <Link
              to="/orders"
              className="text-accent-600 hover:text-accent-700 inline-block mb-4"
            >
              ← Back to Orders
            </Link>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h1 className="text-display-md font-display text-ink-900">
                  Order {selectedOrder.orderNumber}
                </h1>
                <p className="text-ink-600 mt-1">
                  Placed on {formatDate(selectedOrder.createdAt)}
                </p>
              </div>
              <span
                className={`inline-block px-4 py-2 rounded-full text-sm font-medium ${getStatusColor(
                  selectedOrder.status,
                )}`}
              >
                {selectedOrder.status}
              </span>
            </div>
          </div>
        </div>

        <div className="container-page py-12">
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              {error}
            </div>
          )}

          <div className="grid lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2">
              <div className="bg-white rounded-xl shadow-sm border border-ink-100 overflow-hidden">
                <div className="p-6 border-b border-ink-100">
                  <h2 className="font-display text-xl text-ink-900">Order Items</h2>
                </div>
                <div className="divide-y divide-ink-100">
                  {selectedOrder.items.map((item) => (
                    <div key={item.id} className="p-6 flex gap-4 items-center">
                      <div className="flex-1">
                        <Link
                          to={`/products/${item.productSlug}`}
                          className="font-medium text-ink-900 hover:text-accent-600"
                        >
                          {item.productName}
                        </Link>
                        <p className="text-ink-600 text-sm mt-1">
                          Qty: {item.quantity} × {formatPrice(item.unitPrice)}
                        </p>
                      </div>
                      <p className="font-display font-bold text-ink-900">
                        {formatPrice(item.lineTotal)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="lg:col-span-1">
              <div className="bg-white rounded-xl shadow-sm border border-ink-100 p-6">
                <h2 className="font-display text-xl text-ink-900 mb-4">
                  Order Summary
                </h2>
                <div className="space-y-3">
                  <div className="flex justify-between text-ink-600">
                    <span>Subtotal</span>
                    <span>{formatPrice(selectedOrder.subtotal)}</span>
                  </div>
                  <div className="flex justify-between text-ink-600">
                    <span>Shipping</span>
                    <span>{formatPrice(selectedOrder.shipping)}</span>
                  </div>
                  <div className="flex justify-between text-ink-600">
                    <span>Tax</span>
                    <span>{formatPrice(selectedOrder.tax)}</span>
                  </div>
                  <div className="border-t border-ink-100 pt-3 flex justify-between text-lg font-display font-bold text-ink-900">
                    <span>Total</span>
                    <span>{formatPrice(selectedOrder.total)}</span>
                  </div>
                  {selectedOrder.amountRefunded > 0 && (
                    <div className="flex justify-between text-ink-600">
                      <span>Refunded</span>
                      <span>−{formatPrice(selectedOrder.amountRefunded)}</span>
                    </div>
                  )}
                </div>
                {selectedOrder.disputeStatus && (
                  <p className="mt-4 text-sm text-amber-800">
                    {selectedOrder.disputeStatus === 'won'
                      ? 'A dispute on this payment was resolved in the shop’s favour.'
                      : selectedOrder.disputeStatus === 'lost'
                        ? 'This payment was disputed and returned to the card holder.'
                        : 'This payment is being disputed with the card issuer.'}
                  </p>
                )}
                {selectedOrder.notes && (
                  <p className="mt-4 text-sm text-ink-500">{selectedOrder.notes}</p>
                )}
                {selectedOrder.paidAt && (
                  <p className="mt-4 text-sm text-ink-600">
                    Paid on {formatDate(selectedOrder.paidAt)}
                  </p>
                )}
                {payment?.enabled &&
                  selectedOrder.status === 'pending' &&
                  notice !== 'confirming' && (
                    <button
                      type="button"
                      onClick={() => payNow(selectedOrder.id)}
                      disabled={paying}
                      className="w-full btn-primary py-3 mt-6 disabled:opacity-50"
                    >
                      {paying ? 'Opening secure payment…' : 'Pay now'}
                    </button>
                  )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-sand-50">
      <div className="bg-ink-900 text-white py-16">
        <div className="container-page">
          <h1 className="text-display-lg font-display text-white">Your Orders</h1>
          <p className="text-ink-300 mt-2">Portfolio demo order history</p>
        </div>
      </div>

      <div className="container-page py-12">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {orders.length === 0 ? (
          <div className="text-center py-16">
            <h2 className="text-display-sm font-display text-ink-900 mb-4">
              No orders yet
            </h2>
            <p className="text-ink-600 mb-8">
              Create a demo order from your cart and it will appear here.
            </p>
            <Link to="/products" className="btn-primary">
              Start Shopping
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            {orders.map((order) => (
              <Link
                key={order.id}
                to={`/orders/${order.id}`}
                className="block bg-white rounded-xl shadow-sm border border-ink-100 hover:shadow-md transition-shadow"
              >
                <div className="p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                      <p className="font-display font-bold text-ink-900">
                        Order {order.orderNumber}
                      </p>
                      <p className="text-sm text-ink-500">
                        {formatDate(order.createdAt)} · {order.items.length} items
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span
                        className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(
                          order.status,
                        )}`}
                      >
                        {order.status}
                      </span>
                      <p className="font-display font-bold text-ink-900">
                        {formatPrice(order.total)}
                      </p>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
