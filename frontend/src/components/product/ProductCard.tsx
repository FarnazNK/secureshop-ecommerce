import { Link } from 'react-router-dom';
import { ShoppingBag } from 'lucide-react';
import { useState } from 'react';
import type { MouseEvent } from 'react';
import { cn } from '../../utils/cn';
import { useCart } from '../../context/CartContext';

interface Product {
  id: string;
  name: string;
  slug: string;
  price: number;
  compareAtPrice?: number;
  images: { url: string; alt?: string }[];
  category?: { name: string; slug: string };
}

interface ProductCardProps {
  product: Product;
  priority?: boolean;
}

export function ProductCard({ product, priority = false }: ProductCardProps) {
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  const { addItem } = useCart();

  const discount = product.compareAtPrice && product.compareAtPrice > product.price
    ? Math.round((1 - product.price / product.compareAtPrice) * 100)
    : null;

  const handleAddToCart = async (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsAddingToCart(true);
    try {
      await addItem(product.id, 1);
    } finally {
      setIsAddingToCart(false);
    }
  };

  return (
    <article className="product-card group relative h-full flex flex-col overflow-hidden rounded-2xl border border-ink-100 bg-white transition-shadow duration-200 hover:shadow-lg focus-within:ring-2 focus-within:ring-accent-500">
        {/* Image container */}
        <div className="product-card-image relative">
          {/* Product photography with graceful fallback */}
          <div className="w-full h-full bg-gradient-to-br from-sand-100 to-sand-200 flex items-center justify-center">
            {product.images?.[0]?.url ? (
              <img
                src={product.images[0].url}
                alt={product.images[0].alt || product.name}
                className="w-full h-full object-cover"
                loading={priority ? 'eager' : 'lazy'}
              />
            ) : (
              <span className="text-sand-400 text-body-sm">No image</span>
            )}
          </div>

          {/* Badges */}
          <div className="absolute top-3 left-3 flex flex-col gap-2">
            {discount && (
              <span className="badge-primary">
                -{discount}%
              </span>
            )}
          </div>

          {/* Primary product link is a stretched, accessible link. Actions are siblings, not nested buttons. */}
          {/* Add to cart button */}
          <div className="absolute bottom-3 left-3 right-3 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 transition-opacity">
            <button
              type="button"
              onClick={handleAddToCart}
              disabled={isAddingToCart}
              aria-label={`Add ${product.name} to cart`}
              className="relative z-10 w-full btn bg-white text-ink-900 shadow-soft hover:bg-sand-50 focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50"
            >
              <ShoppingBag className="w-4 h-4" aria-hidden="true" />
              {isAddingToCart ? 'Adding...' : 'Add to Cart'}
            </button>
          </div>
        </div>

        {/* Product info */}
        <div className="p-4 flex-1">
          {product.category && (
            <p className="text-body-xs text-ink-400 uppercase tracking-wide mb-1">
              {product.category.name}
            </p>
          )}
          
          <h3 className="text-body-md font-medium text-ink-900 mb-2 line-clamp-2 group-hover:text-primary-600 transition-colors">
            <Link to={`/products/${product.slug}`} className="after:absolute after:inset-0 focus-visible:outline-none">
              {product.name}
            </Link>
          </h3>

          <div className="flex items-center gap-2">
            <span className={cn(
              'price',
              discount ? 'price-sale' : ''
            )}>
              ${product.price.toFixed(2)}
            </span>
            {product.compareAtPrice && (
              <span className="price-original text-body-sm">
                ${product.compareAtPrice.toFixed(2)}
              </span>
            )}
          </div>
        </div>
    </article>
  );
}
