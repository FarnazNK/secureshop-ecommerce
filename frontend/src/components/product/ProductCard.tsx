import { Link } from 'react-router-dom';
import { Heart, ShoppingBag } from 'lucide-react';
import { motion } from 'framer-motion';
import { useState } from 'react';
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
  const [isHovered, setIsHovered] = useState(false);
  const [isWishlisted, setIsWishlisted] = useState(false);
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  const { addItem } = useCart();

  const discount = product.compareAtPrice
    ? Math.round((1 - product.price / product.compareAtPrice) * 100)
    : null;

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsAddingToCart(true);
    try {
      await addItem(product.id, 1);
    } finally {
      setIsAddingToCart(false);
    }
  };

  const handleWishlist = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsWishlisted(!isWishlisted);
  };

  return (
    <Link
      to={`/products/${product.slug}`}
      className="group block"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <article className="product-card">
        {/* Image container */}
        <div className="product-card-image relative">
          {/* Placeholder for actual image */}
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

          {/* Quick actions */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: isHovered ? 1 : 0 }}
            className="absolute top-3 right-3 flex flex-col gap-2"
          >
            <button
              onClick={handleWishlist}
              className={cn(
                'w-9 h-9 flex items-center justify-center rounded-full bg-white shadow-soft transition-colors',
                isWishlisted ? 'text-primary-500' : 'text-ink-400 hover:text-primary-500'
              )}
              aria-label={isWishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
            >
              <Heart className={cn('w-4 h-4', isWishlisted && 'fill-current')} />
            </button>
          </motion.div>

          {/* Add to cart button */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: isHovered ? 1 : 0, y: isHovered ? 0 : 10 }}
            className="absolute bottom-3 left-3 right-3"
          >
            <button
              onClick={handleAddToCart}
              disabled={isAddingToCart}
              className="w-full btn bg-white text-ink-900 shadow-soft hover:bg-sand-50"
            >
              <ShoppingBag className="w-4 h-4" />
              {isAddingToCart ? 'Adding...' : 'Add to Cart'}
            </button>
          </motion.div>
        </div>

        {/* Product info */}
        <div className="p-4">
          {product.category && (
            <p className="text-body-xs text-ink-400 uppercase tracking-wide mb-1">
              {product.category.name}
            </p>
          )}
          
          <h3 className="text-body-md font-medium text-ink-900 mb-2 line-clamp-1 group-hover:text-primary-600 transition-colors">
            {product.name}
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
    </Link>
  );
}
