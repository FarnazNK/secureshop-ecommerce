import { useState, useEffect } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../utils/api';

interface Order {
  id: string;
  orderNumber: string;
  status: string;
  total: number;
  createdAt: string;
  _count?: { items: number };
  items?: {
    id: string;
    productName: string;
    quantity: number;
    price: number;
    total: number;
    product?: {
      id: string;
      slug: string;
      images?: { url: string }[];
    };
  }[];
  shippingAddress?: {
    firstName: string;
    lastName: string;
    addressLine1: string;
    city: string;
    state: string;
    postalCode: string;
  };
}

export function OrdersPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { orderId } = useParams();
  const [searchParams] = useSearchParams();
  const isSuccess = searchParams.get('success') === 'true';

  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price);
  };

  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-amber-100 text-amber-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'shipped':
        return 'bg-purple-100 text-purple-800';
      case 'delivered':
        return 'bg-green-100 text-green-800';
      case 'cancelled':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-ink-100 text-ink-800';
    }
  };

  useEffect(() => {
    if (!user) {
      navigate('/login?redirect=/orders');
      return;
    }

    if (orderId) {
      // Fetch specific order
      api.get(`/orders/${orderId}`)
        .then((res) => setSelectedOrder(res.data.data.order))
        .catch((err) => {
          setError(err.response?.data?.error?.message || 'Order not found');
        })
        .finally(() => setLoading(false));
    } else {
      // Fetch all orders
      api.get('/orders?limit=50')
        .then((res) => setOrders(res.data.data.orders))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [user, navigate, orderId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-accent-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  // Order Detail View
  if (orderId && selectedOrder) {
    return (
      <div className="min-h-screen bg-sand-50">
        {/* Success Banner */}
        {isSuccess && (
          <div className="bg-green-600 text-white py-4">
            <div className="container-page flex items-center gap-3">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <p className="font-medium">Order placed successfully! Thank you for your purchase.</p>
            </div>
          </div>
        )}

        {/* Header */}
        <div className="bg-white border-b border-ink-100">
          <div className="container-page py-8">
            <Link
              to="/orders"
              className="text-accent-600 hover:text-accent-700 flex items-center gap-2 mb-4"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Orders
            </Link>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h1 className="text-display-md font-display text-ink-900">
                  Order {selectedOrder.orderNumber}
                </h1>
                <p className="text-ink-600 mt-1">Placed on {formatDate(selectedOrder.createdAt)}</p>
              </div>
              <span className={`inline-block px-4 py-2 rounded-full text-sm font-medium ${getStatusColor(selectedOrder.status)}`}>
                {selectedOrder.status}
              </span>
            </div>
          </div>
        </div>

        <div className="container-page py-12">
          <div className="grid lg:grid-cols-3 gap-8">
            {/* Order Items */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-xl shadow-sm border border-ink-100 overflow-hidden">
                <div className="p-6 border-b border-ink-100">
                  <h2 className="font-display text-xl text-ink-900">Order Items</h2>
                </div>
                <div className="divide-y divide-ink-100">
                  {selectedOrder.items?.map((item) => (
                    <div key={item.id} className="p-6 flex gap-4">
                      <div className="w-20 h-20 bg-ink-100 rounded-lg overflow-hidden flex-shrink-0">
                        {item.product?.images?.[0] ? (
                          <img
                            src={item.product.images[0].url}
                            alt={item.productName}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-ink-300">
                            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                          </div>
                        )}
                      </div>
                      <div className="flex-1">
                        {item.product?.slug ? (
                          <Link
                            to={`/products/${item.product.slug}`}
                            className="font-medium text-ink-900 hover:text-accent-600 transition-colors"
                          >
                            {item.productName}
                          </Link>
                        ) : (
                          <p className="font-medium text-ink-900">{item.productName}</p>
                        )}
                        <p className="text-ink-600 text-sm mt-1">
                          Qty: {item.quantity} × {formatPrice(item.price)}
                        </p>
                      </div>
                      <p className="font-display font-bold text-ink-900">
                        {formatPrice(item.total)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Order Summary */}
            <div className="lg:col-span-1 space-y-6">
              {/* Summary */}
              <div className="bg-white rounded-xl shadow-sm border border-ink-100 p-6">
                <h2 className="font-display text-xl text-ink-900 mb-4">Order Summary</h2>
                <div className="space-y-3">
                  <div className="flex justify-between text-ink-600">
                    <span>Subtotal</span>
                    <span>{formatPrice(selectedOrder.total * 0.85)}</span>
                  </div>
                  <div className="flex justify-between text-ink-600">
                    <span>Shipping</span>
                    <span>FREE</span>
                  </div>
                  <div className="flex justify-between text-ink-600">
                    <span>Tax</span>
                    <span>{formatPrice(selectedOrder.total * 0.1)}</span>
                  </div>
                  <div className="border-t border-ink-100 pt-3 flex justify-between text-lg font-display font-bold text-ink-900">
                    <span>Total</span>
                    <span>{formatPrice(selectedOrder.total)}</span>
                  </div>
                </div>
              </div>

              {/* Shipping Address */}
              {selectedOrder.shippingAddress && (
                <div className="bg-white rounded-xl shadow-sm border border-ink-100 p-6">
                  <h2 className="font-display text-xl text-ink-900 mb-4">Shipping Address</h2>
                  <div className="text-ink-600">
                    <p className="font-medium text-ink-900">
                      {selectedOrder.shippingAddress.firstName} {selectedOrder.shippingAddress.lastName}
                    </p>
                    <p>{selectedOrder.shippingAddress.addressLine1}</p>
                    <p>
                      {selectedOrder.shippingAddress.city}, {selectedOrder.shippingAddress.state}{' '}
                      {selectedOrder.shippingAddress.postalCode}
                    </p>
                  </div>
                </div>
              )}

              {/* Actions */}
              {selectedOrder.status === 'PENDING' && (
                <button className="w-full py-3 border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition-colors font-medium">
                  Cancel Order
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Orders List View
  return (
    <div className="min-h-screen bg-sand-50">
      {/* Header */}
      <div className="bg-ink-900 text-white py-16">
        <div className="container-page">
          <h1 className="text-display-lg font-display">Your Orders</h1>
          <p className="text-ink-300 mt-2">Track, return, or buy things again</p>
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
            <div className="w-24 h-24 mx-auto mb-6 text-ink-200">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <h2 className="text-display-sm font-display text-ink-900 mb-4">No orders yet</h2>
            <p className="text-ink-600 mb-8 max-w-md mx-auto">
              When you place orders, they will appear here for you to track.
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
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                    <div>
                      <p className="font-display font-bold text-ink-900">
                        Order {order.orderNumber}
                      </p>
                      <p className="text-sm text-ink-500">
                        Placed on {formatDate(order.createdAt)}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(order.status)}`}>
                        {order.status}
                      </span>
                      <p className="font-display font-bold text-ink-900">
                        {formatPrice(order.total)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center text-sm text-ink-500">
                    <span>{order._count?.items || 0} items</span>
                    <svg className="w-4 h-4 ml-auto text-ink-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
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
