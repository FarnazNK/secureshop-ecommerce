import { Link } from 'react-router-dom';
import { ArrowUpRight, ShoppingBag, Sparkles } from 'lucide-react';
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
  const [imageFailed, setImageFailed] = useState(false);
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

  const image = product.images?.[0];

  return (
    <article className="product-card product-card-premium group relative flex h-full flex-col overflow-hidden rounded-[22px] border border-stone-200 bg-white focus-within:ring-2 focus-within:ring-accent-500">
      <div className="product-card-image product-card-media relative isolate">
        {image?.url && !imageFailed ? (
          <img src={image.url} alt={image.alt || product.name} loading={priority ? 'eager' : 'lazy'} onError={() => setImageFailed(true)} className="product-card-photo" />
        ) : (
          <div className="product-card-placeholder" role="img" aria-label={`Image unavailable for ${product.name}`}>
            <div className="product-card-placeholder-orbit" aria-hidden="true" />
            <div className="product-card-placeholder-object" aria-hidden="true" />
            <div className="relative z-10 mt-auto flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.22em] text-stone-600"><Sparkles size={13} /> Image coming soon</div>
          </div>
        )}
        <div className="product-card-sheen" aria-hidden="true" />
        {discount ? <span className="product-card-discount absolute left-4 top-4 z-10 rounded-full px-3 py-1.5 text-[11px] font-bold">SAVE {discount}%</span> : null}
        <span className="product-card-explore absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-full bg-white/90 shadow-md" aria-hidden="true"><ArrowUpRight size={17} /></span>
        <div className="absolute bottom-3 left-3 right-3 z-20 opacity-100 transition-all duration-300 sm:translate-y-2 sm:opacity-0 sm:group-hover:translate-y-0 sm:group-hover:opacity-100 sm:group-focus-within:translate-y-0 sm:group-focus-within:opacity-100">
          <button type="button" onClick={handleAddToCart} disabled={isAddingToCart} aria-label={`Add ${product.name} to cart`} className="relative z-20 flex w-full items-center justify-center gap-2 rounded-full bg-[#192924] px-4 py-3 text-sm font-semibold text-white shadow-xl transition hover:bg-[#304d42] focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50">
            <ShoppingBag size={16} aria-hidden="true" /> {isAddingToCart ? 'Adding...' : 'Add to bag'}
          </button>
        </div>
      </div>
      <div className="flex flex-1 flex-col px-4 pb-5 pt-5 sm:px-5">
        <p className="mb-2 text-[10px] font-bold uppercase tracking-[.2em] text-[#98765c]">{product.category?.name || 'THE COLLECTION'}</p>
        <h3 className="mb-3 font-display text-xl font-normal leading-tight text-[#202823] transition-colors group-hover:text-[#aa7551]">
          <Link to={`/products/${product.slug}`} className="after:absolute after:inset-0 focus-visible:outline-none">{product.name}</Link>
        </h3>
        <div className="mt-auto flex flex-wrap items-baseline gap-2">
          <span className={cn('font-semibold tracking-tight text-[#202823]', discount ? 'text-[#ae6844]' : '')}>${product.price.toFixed(2)}</span>
          {product.compareAtPrice && product.compareAtPrice > product.price ? <span className="text-sm text-stone-400 line-through">${product.compareAtPrice.toFixed(2)}</span> : null}
        </div>
      </div>
    </article>
  );
}
