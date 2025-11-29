import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  ShoppingBag,
  User,
  Menu,
  X,
  Heart,
  ChevronDown,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import { cn } from '../../utils/cn';

const navigation = [
  { name: 'Shop', href: '/products' },
  { name: 'New Arrivals', href: '/products?sort=newest' },
  { name: 'Collections', href: '/collections' },
  { name: 'About', href: '/about' },
];

export function Header() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const location = useLocation();
  const { user, isAuthenticated } = useAuth();
  const { itemCount } = useCart();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <>
      <header
        className={cn(
          'fixed top-0 left-0 right-0 z-50 transition-all duration-300',
          isScrolled
            ? 'bg-sand-50/95 backdrop-blur-md shadow-soft'
            : 'bg-transparent'
        )}
      >
        {/* Announcement bar */}
        <div className="bg-ink-900 text-sand-50">
          <div className="container-page py-2">
            <p className="text-body-xs text-center">
              Free shipping on orders over $100 · Extended holiday returns
            </p>
          </div>
        </div>

        {/* Main header */}
        <div className="container-page">
          <div className="flex items-center justify-between h-16 md:h-20">
            {/* Mobile menu button */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="btn-icon md:hidden"
              aria-label="Toggle menu"
            >
              {isMobileMenuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>

            {/* Logo */}
            <Link
              to="/"
              className="flex items-center gap-2 group"
            >
              <span className="font-display text-xl md:text-2xl font-medium text-ink-900 tracking-tight">
                SecureShop
              </span>
            </Link>

            {/* Desktop navigation */}
            <nav className="hidden md:flex items-center gap-8">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'nav-link relative py-1',
                    location.pathname === item.href && 'nav-link-active'
                  )}
                >
                  {item.name}
                  {location.pathname === item.href && (
                    <motion.div
                      layoutId="nav-indicator"
                      className="absolute -bottom-0.5 left-0 right-0 h-0.5 bg-primary-500"
                      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                    />
                  )}
                </Link>
              ))}
            </nav>

            {/* Actions */}
            <div className="flex items-center gap-1 md:gap-2">
              {/* Search */}
              <button
                onClick={() => setIsSearchOpen(true)}
                className="btn-icon"
                aria-label="Search"
              >
                <Search className="w-5 h-5" />
              </button>

              {/* Wishlist (desktop only) */}
              <Link
                to="/wishlist"
                className="btn-icon hidden md:flex"
                aria-label="Wishlist"
              >
                <Heart className="w-5 h-5" />
              </Link>

              {/* Account */}
              <Link
                to={isAuthenticated ? '/account' : '/login'}
                className="btn-icon"
                aria-label="Account"
              >
                <User className="w-5 h-5" />
              </Link>

              {/* Cart */}
              <Link
                to="/cart"
                className="btn-icon relative"
                aria-label="Cart"
              >
                <ShoppingBag className="w-5 h-5" />
                {itemCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center bg-primary-500 text-white text-body-xs font-medium rounded-full">
                    {itemCount > 9 ? '9+' : itemCount}
                  </span>
                )}
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile menu */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-ink-900/40 backdrop-blur-sm z-40 md:hidden"
              onClick={() => setIsMobileMenuOpen(false)}
            />
            <motion.div
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="fixed top-0 left-0 bottom-0 w-80 max-w-[85vw] bg-sand-50 z-50 md:hidden overflow-y-auto"
            >
              <div className="p-6">
                {/* Mobile menu header */}
                <div className="flex items-center justify-between mb-8">
                  <span className="font-display text-xl font-medium">Menu</span>
                  <button
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="btn-icon"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Mobile navigation */}
                <nav className="space-y-1 mb-8">
                  {navigation.map((item) => (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={cn(
                        'block py-3 px-4 rounded-soft text-body-lg',
                        'transition-colors duration-200',
                        location.pathname === item.href
                          ? 'bg-sand-100 text-ink-900 font-medium'
                          : 'text-ink-600 hover:bg-sand-100 hover:text-ink-900'
                      )}
                    >
                      {item.name}
                    </Link>
                  ))}
                </nav>

                <div className="divider mb-8" />

                {/* Account section */}
                {isAuthenticated ? (
                  <div className="space-y-4">
                    <p className="text-body-sm text-ink-500">
                      Signed in as{' '}
                      <span className="text-ink-900 font-medium">
                        {user?.firstName}
                      </span>
                    </p>
                    <div className="space-y-1">
                      <Link
                        to="/account"
                        className="block py-2 text-body-md text-ink-700 hover:text-ink-900"
                      >
                        My Account
                      </Link>
                      <Link
                        to="/orders"
                        className="block py-2 text-body-md text-ink-700 hover:text-ink-900"
                      >
                        Orders
                      </Link>
                      <Link
                        to="/wishlist"
                        className="block py-2 text-body-md text-ink-700 hover:text-ink-900"
                      >
                        Wishlist
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <Link to="/login" className="btn-primary w-full">
                      Sign In
                    </Link>
                    <Link to="/register" className="btn-secondary w-full">
                      Create Account
                    </Link>
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Search modal */}
      <AnimatePresence>
        {isSearchOpen && (
          <SearchModal onClose={() => setIsSearchOpen(false)} />
        )}
      </AnimatePresence>

      {/* Spacer for fixed header */}
      <div className="h-[calc(2rem+4rem)] md:h-[calc(2rem+5rem)]" />
    </>
  );
}

function SearchModal({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('');

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-ink-900/40 backdrop-blur-sm z-50"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        className="fixed top-0 left-0 right-0 bg-sand-50 z-50 shadow-elevated"
      >
        <div className="container-page py-6">
          <div className="flex items-center gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search products..."
                className="input pl-12 text-body-lg"
                autoFocus
              />
            </div>
            <button onClick={onClose} className="btn-ghost">
              Cancel
            </button>
          </div>

          {/* Quick links */}
          <div className="mt-6">
            <p className="text-body-sm text-ink-500 mb-3">Popular searches</p>
            <div className="flex flex-wrap gap-2">
              {['New arrivals', 'Best sellers', 'Sale', 'Accessories'].map(
                (term) => (
                  <Link
                    key={term}
                    to={`/products?search=${encodeURIComponent(term)}`}
                    onClick={onClose}
                    className="px-4 py-2 bg-sand-100 rounded-full text-body-sm text-ink-700 hover:bg-sand-200 transition-colors"
                  >
                    {term}
                  </Link>
                )
              )}
            </div>
          </div>
        </div>
      </motion.div>
    </>
  );
}
