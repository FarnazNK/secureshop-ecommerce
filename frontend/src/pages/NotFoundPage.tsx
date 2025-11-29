import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="min-h-screen bg-sand-50 flex items-center justify-center px-4">
      <div className="text-center max-w-lg">
        {/* 404 Illustration */}
        <div className="mb-8">
          <div className="relative inline-block">
            <span className="text-[12rem] font-display font-bold text-ink-100 leading-none select-none">
              404
            </span>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-32 h-32 bg-accent-100 rounded-full flex items-center justify-center">
                <svg className="w-16 h-16 text-accent-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        <h1 className="text-display-lg font-display text-ink-900 mb-4">
          Page Not Found
        </h1>
        <p className="text-ink-600 text-lg mb-8">
          Oops! The page you're looking for doesn't exist. It might have been moved or deleted.
        </p>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link to="/" className="btn-primary">
            Go to Homepage
          </Link>
          <Link to="/products" className="btn-secondary">
            Browse Products
          </Link>
        </div>

        {/* Helpful Links */}
        <div className="mt-12 pt-8 border-t border-ink-100">
          <p className="text-sm text-ink-500 mb-4">Maybe you were looking for:</p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link to="/products" className="text-accent-600 hover:text-accent-700">
              All Products
            </Link>
            <span className="text-ink-300">•</span>
            <Link to="/cart" className="text-accent-600 hover:text-accent-700">
              Shopping Cart
            </Link>
            <span className="text-ink-300">•</span>
            <Link to="/orders" className="text-accent-600 hover:text-accent-700">
              My Orders
            </Link>
            <span className="text-ink-300">•</span>
            <Link to="/account" className="text-accent-600 hover:text-accent-700">
              Account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
