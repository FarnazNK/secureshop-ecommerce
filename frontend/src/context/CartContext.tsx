import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  ReactNode,
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
    quantity: number;
  };
}

interface Cart {
  items: CartItem[];
  subtotal: number;
  itemCount: number;
}

interface BackendProduct {
  id: string;
  name: string;
  slug: string;
  price: string | number;
  stock_quantity: number;
  images?: { url: string; alt?: string | null }[];
}

interface BackendCartItem {
  id: string;
  product_id: string;
  quantity: number;
  unit_price: string | number;
  product: BackendProduct;
}

interface BackendCart {
  items: BackendCartItem[];
  subtotal: string | number;
  item_count: number;
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
const GUEST_CART_KEY = 'secureshop_guest_cart';

function mapBackendCart(cart: BackendCart): Cart {
  return {
    items: cart.items.map((item) => ({
      id: item.id,
      productId: item.product_id,
      quantity: item.quantity,
      price: Number(item.unit_price),
      product: {
        id: item.product.id,
        name: item.product.name,
        slug: item.product.slug,
        price: Number(item.product.price),
        images: (item.product.images ?? []).map((image) => ({
          url: image.url,
          alt: image.alt ?? undefined,
        })),
        quantity: item.product.stock_quantity,
      },
    })),
    subtotal: Number(cart.subtotal),
    itemCount: cart.item_count,
  };
}

function recalculateGuestCart(cart: Cart): Cart {
  cart.itemCount = cart.items.reduce((sum, item) => sum + item.quantity, 0);
  cart.subtotal = cart.items.reduce(
    (sum, item) => sum + item.quantity * item.price,
    0,
  );
  return cart;
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { isAuthenticated } = useAuth();

  const loadCart = useCallback(async () => {
    setIsLoading(true);
    try {
      if (isAuthenticated) {
        const response = await api.get<BackendCart>('/cart');
        setCart(mapBackendCart(response.data));
      } else {
        const guestCart = localStorage.getItem(GUEST_CART_KEY);
        setCart(
          guestCart
            ? JSON.parse(guestCart)
            : { items: [], subtotal: 0, itemCount: 0 },
        );
      }
    } catch {
      setCart({ items: [], subtotal: 0, itemCount: 0 });
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void loadCart();
  }, [loadCart]);

  const refreshCart = useCallback(async () => {
    await loadCart();
  }, [loadCart]);

  const addItem = useCallback(
    async (productId: string, quantity = 1) => {
      if (isAuthenticated) {
        const response = await api.post<BackendCart>('/cart/items', {
          product_id: productId,
          quantity,
        });
        setCart(mapBackendCart(response.data));
        return;
      }

      const guestCart = localStorage.getItem(GUEST_CART_KEY);
      const currentCart: Cart = guestCart
        ? JSON.parse(guestCart)
        : { items: [], subtotal: 0, itemCount: 0 };

      const existingItem = currentCart.items.find(
        (item) => item.productId === productId,
      );

      if (existingItem) {
        existingItem.quantity = Math.min(
          existingItem.quantity + quantity,
          existingItem.product.quantity,
        );
      } else {
        const response = await api.get<BackendProduct>(`/products/${productId}`);
        const product = response.data;
        currentCart.items.push({
          id: `guest-${product.id}`,
          productId: product.id,
          quantity: Math.min(quantity, product.stock_quantity),
          price: Number(product.price),
          product: {
            id: product.id,
            name: product.name,
            slug: product.slug,
            price: Number(product.price),
            images: (product.images ?? []).map((image) => ({
              url: image.url,
              alt: image.alt ?? undefined,
            })),
            quantity: product.stock_quantity,
          },
        });
      }

      const nextCart = recalculateGuestCart(currentCart);
      localStorage.setItem(GUEST_CART_KEY, JSON.stringify(nextCart));
      setCart(nextCart);
    },
    [isAuthenticated],
  );

  const updateItem = useCallback(
    async (itemId: string, quantity: number) => {
      if (isAuthenticated) {
        if (quantity === 0) {
          const response = await api.delete<BackendCart>(`/cart/items/${itemId}`);
          setCart(mapBackendCart(response.data));
        } else {
          const response = await api.patch<BackendCart>(
            `/cart/items/${itemId}`,
            { quantity },
          );
          setCart(mapBackendCart(response.data));
        }
        return;
      }

      const guestCart = localStorage.getItem(GUEST_CART_KEY);
      if (!guestCart) return;

      const currentCart: Cart = JSON.parse(guestCart);
      if (quantity === 0) {
        currentCart.items = currentCart.items.filter(
          (item) => item.id !== itemId,
        );
      } else {
        const item = currentCart.items.find((entry) => entry.id === itemId);
        if (item) {
          item.quantity = Math.min(quantity, item.product.quantity);
        }
      }

      const nextCart = recalculateGuestCart(currentCart);
      localStorage.setItem(GUEST_CART_KEY, JSON.stringify(nextCart));
      setCart(nextCart);
    },
    [isAuthenticated],
  );

  const removeItem = useCallback(
    async (itemId: string) => {
      await updateItem(itemId, 0);
    },
    [updateItem],
  );

  const clearCart = useCallback(async () => {
    if (isAuthenticated) {
      const response = await api.delete<BackendCart>('/cart');
      setCart(mapBackendCart(response.data));
    } else {
      localStorage.removeItem(GUEST_CART_KEY);
      setCart({ items: [], subtotal: 0, itemCount: 0 });
    }
  }, [isAuthenticated]);

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
