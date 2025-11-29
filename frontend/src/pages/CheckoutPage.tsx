import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../utils/api';

interface Address {
  id: string;
  label?: string;
  firstName: string;
  lastName: string;
  addressLine1: string;
  addressLine2?: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
  phone?: string;
  isDefault: boolean;
}

type CheckoutStep = 'shipping' | 'payment' | 'review';

export function CheckoutPage() {
  const { cart, clearCart } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState<CheckoutStep>('shipping');
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddress, setSelectedAddress] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New address form
  const [showAddressForm, setShowAddressForm] = useState(false);
  const [newAddress, setNewAddress] = useState({
    firstName: '',
    lastName: '',
    addressLine1: '',
    addressLine2: '',
    city: '',
    state: '',
    postalCode: '',
    country: 'US',
    phone: '',
  });

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price);
  };

  // Redirect if not logged in or cart is empty
  useEffect(() => {
    if (!user) {
      navigate('/login?redirect=/checkout');
      return;
    }
    if (!cart || cart.items.length === 0) {
      navigate('/cart');
      return;
    }
  }, [user, cart, navigate]);

  // Fetch addresses
  useEffect(() => {
    if (!user) return;

    api.get('/users/addresses')
      .then((res) => {
        const addrs = res.data.data.addresses;
        setAddresses(addrs);
        // Auto-select default address
        const defaultAddr = addrs.find((a: Address) => a.isDefault);
        if (defaultAddr) {
          setSelectedAddress(defaultAddr.id);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user]);

  const handleAddAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      const res = await api.post('/users/addresses', newAddress);
      const addr = res.data.data.address;
      setAddresses([...addresses, addr]);
      setSelectedAddress(addr.id);
      setShowAddressForm(false);
      setNewAddress({
        firstName: '',
        lastName: '',
        addressLine1: '',
        addressLine2: '',
        city: '',
        state: '',
        postalCode: '',
        country: 'US',
        phone: '',
      });
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to add address');
    }
  };

  const handlePlaceOrder = async () => {
    if (!selectedAddress) {
      setError('Please select a shipping address');
      return;
    }

    setProcessing(true);
    setError(null);

    try {
      const res = await api.post('/orders', {
        shippingAddressId: selectedAddress,
        paymentMethodId: 'demo_payment', // Demo mode
        shippingMethodId: 'standard',
      });

      await clearCart();
      navigate(`/orders/${res.data.data.order.id}?success=true`);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to place order');
      setProcessing(false);
    }
  };

  if (loading || !cart) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-accent-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  const subtotal = cart.items.reduce(
    (sum, item) => sum + item.quantity * item.price,
    0
  );
  const shipping = subtotal >= 100 ? 0 : 9.99;
  const tax = subtotal * 0.1;
  const total = subtotal + shipping + tax;

  const selectedAddressData = addresses.find((a) => a.id === selectedAddress);

  const steps = [
    { id: 'shipping', label: 'Shipping', number: 1 },
    { id: 'payment', label: 'Payment', number: 2 },
    { id: 'review', label: 'Review', number: 3 },
  ];

  return (
    <div className="min-h-screen bg-sand-50">
      {/* Header */}
      <div className="bg-white border-b border-ink-100">
        <div className="container-page py-8">
          <h1 className="text-display-lg font-display text-ink-900">Checkout</h1>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="bg-white border-b border-ink-100">
        <div className="container-page py-4">
          <div className="flex items-center justify-center gap-4">
            {steps.map((s, idx) => (
              <div key={s.id} className="flex items-center">
                <button
                  onClick={() => {
                    if (s.id === 'shipping') setStep('shipping');
                    else if (s.id === 'payment' && selectedAddress) setStep('payment');
                    else if (s.id === 'review' && selectedAddress) setStep('review');
                  }}
                  className={`flex items-center gap-2 ${
                    step === s.id ? 'text-accent-600' : 'text-ink-400'
                  }`}
                >
                  <span
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      step === s.id
                        ? 'bg-accent-600 text-white'
                        : 'bg-ink-100 text-ink-500'
                    }`}
                  >
                    {s.number}
                  </span>
                  <span className="hidden sm:inline font-medium">{s.label}</span>
                </button>
                {idx < steps.length - 1 && (
                  <div className="w-12 sm:w-24 h-px bg-ink-200 mx-2 sm:mx-4" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="container-page py-12">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                {error}
              </div>
            )}

            {/* Shipping Step */}
            {step === 'shipping' && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100">
                <h2 className="font-display text-xl text-ink-900 mb-6">Shipping Address</h2>

                {addresses.length > 0 && !showAddressForm && (
                  <div className="space-y-4 mb-6">
                    {addresses.map((addr) => (
                      <label
                        key={addr.id}
                        className={`block p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                          selectedAddress === addr.id
                            ? 'border-accent-600 bg-accent-50'
                            : 'border-ink-200 hover:border-ink-300'
                        }`}
                      >
                        <input
                          type="radio"
                          name="address"
                          value={addr.id}
                          checked={selectedAddress === addr.id}
                          onChange={() => setSelectedAddress(addr.id)}
                          className="sr-only"
                        />
                        <div className="flex justify-between">
                          <div>
                            {addr.label && (
                              <span className="text-sm font-medium text-accent-600 mb-1 block">
                                {addr.label}
                              </span>
                            )}
                            <p className="font-medium text-ink-900">
                              {addr.firstName} {addr.lastName}
                            </p>
                            <p className="text-ink-600 text-sm">
                              {addr.addressLine1}
                              {addr.addressLine2 && `, ${addr.addressLine2}`}
                            </p>
                            <p className="text-ink-600 text-sm">
                              {addr.city}, {addr.state} {addr.postalCode}
                            </p>
                          </div>
                          {addr.isDefault && (
                            <span className="text-xs bg-ink-100 text-ink-600 px-2 py-1 rounded h-fit">
                              Default
                            </span>
                          )}
                        </div>
                      </label>
                    ))}
                  </div>
                )}

                {showAddressForm ? (
                  <form onSubmit={handleAddAddress} className="space-y-4">
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-ink-700 mb-1">
                          First Name *
                        </label>
                        <input
                          type="text"
                          required
                          value={newAddress.firstName}
                          onChange={(e) =>
                            setNewAddress({ ...newAddress, firstName: e.target.value })
                          }
                          className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-ink-700 mb-1">
                          Last Name *
                        </label>
                        <input
                          type="text"
                          required
                          value={newAddress.lastName}
                          onChange={(e) =>
                            setNewAddress({ ...newAddress, lastName: e.target.value })
                          }
                          className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-ink-700 mb-1">
                        Address Line 1 *
                      </label>
                      <input
                        type="text"
                        required
                        value={newAddress.addressLine1}
                        onChange={(e) =>
                          setNewAddress({ ...newAddress, addressLine1: e.target.value })
                        }
                        className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-ink-700 mb-1">
                        Address Line 2
                      </label>
                      <input
                        type="text"
                        value={newAddress.addressLine2}
                        onChange={(e) =>
                          setNewAddress({ ...newAddress, addressLine2: e.target.value })
                        }
                        className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                      />
                    </div>

                    <div className="grid sm:grid-cols-3 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-ink-700 mb-1">
                          City *
                        </label>
                        <input
                          type="text"
                          required
                          value={newAddress.city}
                          onChange={(e) =>
                            setNewAddress({ ...newAddress, city: e.target.value })
                          }
                          className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-ink-700 mb-1">
                          State *
                        </label>
                        <input
                          type="text"
                          required
                          value={newAddress.state}
                          onChange={(e) =>
                            setNewAddress({ ...newAddress, state: e.target.value })
                          }
                          className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-ink-700 mb-1">
                          ZIP Code *
                        </label>
                        <input
                          type="text"
                          required
                          value={newAddress.postalCode}
                          onChange={(e) =>
                            setNewAddress({ ...newAddress, postalCode: e.target.value })
                          }
                          className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-ink-700 mb-1">
                        Phone
                      </label>
                      <input
                        type="tel"
                        value={newAddress.phone}
                        onChange={(e) =>
                          setNewAddress({ ...newAddress, phone: e.target.value })
                        }
                        className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                      />
                    </div>

                    <div className="flex gap-4 pt-4">
                      <button type="submit" className="btn-primary">
                        Save Address
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowAddressForm(false)}
                        className="btn-secondary"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    onClick={() => setShowAddressForm(true)}
                    className="text-accent-600 hover:text-accent-700 font-medium flex items-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add New Address
                  </button>
                )}

                <div className="mt-8 pt-6 border-t border-ink-100">
                  <button
                    onClick={() => setStep('payment')}
                    disabled={!selectedAddress}
                    className="btn-primary w-full sm:w-auto disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Continue to Payment
                  </button>
                </div>
              </div>
            )}

            {/* Payment Step */}
            {step === 'payment' && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100">
                <h2 className="font-display text-xl text-ink-900 mb-6">Payment Method</h2>

                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
                  <p className="text-amber-800 text-sm">
                    <strong>Demo Mode:</strong> This is a portfolio project. No real payments will be processed.
                  </p>
                </div>

                <div className="p-4 border-2 border-accent-600 bg-accent-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-6 bg-gradient-to-r from-blue-600 to-blue-800 rounded flex items-center justify-center text-white text-xs font-bold">
                      DEMO
                    </div>
                    <div>
                      <p className="font-medium text-ink-900">Demo Payment</p>
                      <p className="text-sm text-ink-600">Simulate a successful payment</p>
                    </div>
                  </div>
                </div>

                <div className="mt-8 pt-6 border-t border-ink-100 flex gap-4">
                  <button
                    onClick={() => setStep('shipping')}
                    className="btn-secondary"
                  >
                    Back
                  </button>
                  <button
                    onClick={() => setStep('review')}
                    className="btn-primary"
                  >
                    Review Order
                  </button>
                </div>
              </div>
            )}

            {/* Review Step */}
            {step === 'review' && (
              <div className="space-y-6">
                {/* Shipping Address Review */}
                <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100">
                  <div className="flex justify-between items-start mb-4">
                    <h2 className="font-display text-xl text-ink-900">Shipping Address</h2>
                    <button
                      onClick={() => setStep('shipping')}
                      className="text-accent-600 hover:text-accent-700 text-sm font-medium"
                    >
                      Edit
                    </button>
                  </div>
                  {selectedAddressData && (
                    <div className="text-ink-600">
                      <p className="font-medium text-ink-900">
                        {selectedAddressData.firstName} {selectedAddressData.lastName}
                      </p>
                      <p>{selectedAddressData.addressLine1}</p>
                      {selectedAddressData.addressLine2 && <p>{selectedAddressData.addressLine2}</p>}
                      <p>
                        {selectedAddressData.city}, {selectedAddressData.state}{' '}
                        {selectedAddressData.postalCode}
                      </p>
                    </div>
                  )}
                </div>

                {/* Order Items Review */}
                <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100">
                  <div className="flex justify-between items-start mb-4">
                    <h2 className="font-display text-xl text-ink-900">Order Items</h2>
                    <Link
                      to="/cart"
                      className="text-accent-600 hover:text-accent-700 text-sm font-medium"
                    >
                      Edit
                    </Link>
                  </div>
                  <div className="divide-y divide-ink-100">
                    {cart.items.map((item) => (
                      <div key={item.id} className="py-4 flex gap-4">
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

                {/* Place Order Button */}
                <div className="flex gap-4">
                  <button onClick={() => setStep('payment')} className="btn-secondary">
                    Back
                  </button>
                  <button
                    onClick={handlePlaceOrder}
                    disabled={processing}
                    className="btn-primary flex-1 py-4 text-lg disabled:opacity-50"
                  >
                    {processing ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Processing...
                      </span>
                    ) : (
                      `Place Order • ${formatPrice(total)}`
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Order Summary Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100 sticky top-24">
              <h2 className="font-display text-xl text-ink-900 mb-6">Order Summary</h2>

              <div className="space-y-3 text-sm">
                {cart.items.map((item) => (
                  <div key={item.id} className="flex justify-between text-ink-600">
                    <span>
                      {item.product.name} × {item.quantity}
                    </span>
                    <span>{formatPrice(item.quantity * item.price)}</span>
                  </div>
                ))}
              </div>

              <div className="border-t border-ink-100 my-4" />

              <div className="space-y-3">
                <div className="flex justify-between text-ink-600">
                  <span>Subtotal</span>
                  <span>{formatPrice(subtotal)}</span>
                </div>
                <div className="flex justify-between text-ink-600">
                  <span>Shipping</span>
                  <span>
                    {shipping === 0 ? (
                      <span className="text-green-600">FREE</span>
                    ) : (
                      formatPrice(shipping)
                    )}
                  </span>
                </div>
                <div className="flex justify-between text-ink-600">
                  <span>Tax</span>
                  <span>{formatPrice(tax)}</span>
                </div>
                <div className="border-t border-ink-100 pt-3 flex justify-between text-lg font-display font-bold text-ink-900">
                  <span>Total</span>
                  <span>{formatPrice(total)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
