// Placeholder pages - implement fully based on your needs

export function ProductsPage() {
  return (
    <div className="container-page section">
      <h1 className="text-display-md font-display text-ink-900 mb-8">All Products</h1>
      <p className="text-body-md text-ink-600">Product listing page - implement with filters, sorting, and pagination.</p>
    </div>
  );
}

export function ProductDetailPage() {
  return (
    <div className="container-page section">
      <h1 className="text-display-md font-display text-ink-900 mb-8">Product Detail</h1>
      <p className="text-body-md text-ink-600">Product detail page - implement with images, description, reviews, and add to cart.</p>
    </div>
  );
}

export function CartPage() {
  return (
    <div className="container-page section">
      <h1 className="text-display-md font-display text-ink-900 mb-8">Shopping Cart</h1>
      <p className="text-body-md text-ink-600">Cart page - implement with cart items, quantities, and checkout button.</p>
    </div>
  );
}

export function CheckoutPage() {
  return (
    <div className="container-page section">
      <h1 className="text-display-md font-display text-ink-900 mb-8">Checkout</h1>
      <p className="text-body-md text-ink-600">Checkout page - implement with shipping, payment (Stripe), and order review.</p>
    </div>
  );
}

export function RegisterPage() {
  return (
    <div className="container-page section">
      <h1 className="text-display-md font-display text-ink-900 mb-8">Create Account</h1>
      <p className="text-body-md text-ink-600">Registration page - implement similar to LoginPage with additional fields.</p>
    </div>
  );
}

export function AccountPage() {
  return (
    <div className="container-page section">
      <h1 className="text-display-md font-display text-ink-900 mb-8">My Account</h1>
      <p className="text-body-md text-ink-600">Account page - implement with profile settings, addresses, and preferences.</p>
    </div>
  );
}

export function OrdersPage() {
  return (
    <div className="container-page section">
      <h1 className="text-display-md font-display text-ink-900 mb-8">My Orders</h1>
      <p className="text-body-md text-ink-600">Orders page - implement with order history and order details.</p>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div className="container-page section text-center">
      <h1 className="text-display-lg font-display text-ink-900 mb-4">404</h1>
      <p className="text-body-xl text-ink-600 mb-8">Page not found</p>
      <a href="/" className="btn-primary">Go Home</a>
    </div>
  );
}
