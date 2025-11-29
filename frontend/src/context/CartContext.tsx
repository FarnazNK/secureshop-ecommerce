import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
} from 'react';
import { api } from '../utils/api';
import { useAuth } from './AuthContext';

interface CartItem {
  id: string;
  productId: string;
  quantity: number;
  price: number;
  product: {
    id: string;
    name: string;
    slug: string;
    price: number;
    images: { url: string; alt?: string }[];
    quantity: number; // Available stock
  };
}

interface Cart {
  items: CartItem[];
  subtotal: number;
  itemCount: number;
}

interface CartContextType {
  cart: Cart | null;
  isLoading: boolean;
  itemCount: number;
  subtotal: number;
  addItem: (productId: string, quantity?: number) => Promise<void>;
  updateItem: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
  clearCart: () => Promise<void>;
  refreshCart: () => Promise<void>;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

// Local storage key for guest cart
const GUEST_CART_KEY = 'secureshop_guest_cart';

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { isAuthenticated } = useAuth();

  // Load cart on mount and auth change
  useEffect(() => {
    loadCart();
  }, [isAuthenticated]);

  const loadCart = async () => {
    setIsLoading(true);
    try {
      if (isAuthenticated) {
        const response = await api.get('/cart');
        setCart(response.data.data.cart);
      } else {
        // Load from local storage for guests
        const guestCart = localStorage.getItem(GUEST_CART_KEY);
        if (guestCart) {
          setCart(JSON.parse(guestCart));
        } else {
          setCart({ items: [], subtotal: 0, itemCount: 0 });
        }
      }
    } catch {
      setCart({ items: [], subtotal: 0, itemCount: 0 });
    } finally {
      setIsLoading(false);
    }
  };

  const refreshCart = useCallback(async () => {
    await loadCart();
  }, [isAuthenticated]);

  const addItem = useCallback(
    async (productId: string, quantity = 1) => {
      if (isAuthenticated) {
        await api.post('/cart/items', { productId, quantity });
        await refreshCart();
      } else {
        // Handle guest cart locally
        // In a real app, you'd fetch product details
        const guestCart = localStorage.getItem(GUEST_CART_KEY);
        const currentCart: Cart = guestCart
          ? JSON.parse(guestCart)
          : { items: [], subtotal: 0, itemCount: 0 };

        const existingItem = currentCart.items.find(
          (item) => item.productId === productId
        );

        if (existingItem) {
          existingItem.quantity += quantity;
        } else {
          // Would need to fetch product details in real implementation
          currentCart.items.push({
            id: `guest-${Date.now()}`,
            productId,
            quantity,
            price: 0, // Would be fetched
            product: {} as CartItem['product'], // Would be fetched
          });
        }

        currentCart.itemCount = currentCart.items.reduce(
          (sum, item) => sum + item.quantity,
          0
        );
        currentCart.subtotal = currentCart.items.reduce(
          (sum, item) => sum + item.quantity * item.price,
          0
        );

        localStorage.setItem(GUEST_CART_KEY, JSON.stringify(currentCart));
        setCart(currentCart);
      }
    },
    [isAuthenticated, refreshCart]
  );

  const updateItem = useCallback(
    async (itemId: string, quantity: number) => {
      if (isAuthenticated) {
        if (quantity === 0) {
          await api.delete(`/cart/items/${itemId}`);
        } else {
          await api.put(`/cart/items/${itemId}`, { quantity });
        }
        await refreshCart();
      } else {
        const guestCart = localStorage.getItem(GUEST_CART_KEY);
        if (!guestCart) return;

        const currentCart: Cart = JSON.parse(guestCart);

        if (quantity === 0) {
          currentCart.items = currentCart.items.filter(
            (item) => item.id !== itemId
          );
        } else {
          const item = currentCart.items.find((item) => item.id === itemId);
          if (item) {
            item.quantity = quantity;
          }
        }

        currentCart.itemCount = currentCart.items.reduce(
          (sum, item) => sum + item.quantity,
          0
        );
        currentCart.subtotal = currentCart.items.reduce(
          (sum, item) => sum + item.quantity * item.price,
          0
        );

        localStorage.setItem(GUEST_CART_KEY, JSON.stringify(currentCart));
        setCart(currentCart);
      }
    },
    [isAuthenticated, refreshCart]
  );

  const removeItem = useCallback(
    async (itemId: string) => {
      await updateItem(itemId, 0);
    },
    [updateItem]
  );

  const clearCart = useCallback(async () => {
    if (isAuthenticated) {
      await api.delete('/cart');
      await refreshCart();
    } else {
      localStorage.removeItem(GUEST_CART_KEY);
      setCart({ items: [], subtotal: 0, itemCount: 0 });
    }
  }, [isAuthenticated, refreshCart]);

  return (
    <CartContext.Provider
      value={{
        cart,
        isLoading,
        itemCount: cart?.itemCount ?? 0,
        subtotal: cart?.subtotal ?? 0,
        addItem,
        updateItem,
        removeItem,
        clearCart,
        refreshCart,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);
  if (context === undefined) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
}
