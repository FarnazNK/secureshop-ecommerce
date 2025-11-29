import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { api } from '../utils/api';

interface Product {
  id: string;
  name: string;
  slug: string;
  description?: string;
  shortDescription?: string;
  price: number;
  compareAtPrice?: number;
  quantity: number;
  images?: { url: string; alt?: string; position: number }[];
  category?: { id: string; name: string; slug: string };
  brand?: { id: string; name: string; logo?: string };
  averageRating?: number;
  reviewCount?: number;
  reviews?: {
    id: string;
    rating: number;
    title?: string;
    content: string;
    createdAt: string;
    user: { firstName: string; lastName: string };
  }[];
}

export function ProductDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { addItem } = useCart();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [addingToCart, setAddingToCart] = useState(false);
  const [addedToCart, setAddedToCart] = useState(false);

  useEffect(() => {
    if (!slug) return;
    
    setLoading(true);
    setError(null);
    
    api.get(`/products/${slug}`)
      .then(res => {
        setProduct(res.data.data.product);
      })
      .catch(err => {
        setError(err.response?.data?.error?.message || 'Product not found');
      })
      .finally(() => setLoading(false));
  }, [slug]);

  const handleAddToCart = async () => {
    if (!product) return;
    
    setAddingToCart(true);
    try {
      await addItem(product.id, quantity);
      setAddedToCart(true);
      setTimeout(() => setAddedToCart(false), 3000);
    } catch (err) {
      console.error('Failed to add to cart:', err);
    } finally {
      setAddingToCart(false);
    }
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price);
  };

  const renderStars = (rating: number) => {
    return [...Array(5)].map((_, i) => (
      <svg
        key={i}
        className={`w-5 h-5 ${i < Math.floor(rating) ? 'text-amber-400' : 'text-ink-200'}`}
        fill="currentColor"
        viewBox="0 0 20 20"
      >
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
    ));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-sand-50 py-12">
        <div className="container-page">
          <div className="grid lg:grid-cols-2 gap-12 animate-pulse">
            <div className="aspect-square bg-ink-100 rounded-2xl" />
            <div className="space-y-6">
              <div className="h-8 bg-ink-100 rounded w-3/4" />
              <div className="h-6 bg-ink-100 rounded w-1/4" />
              <div className="space-y-2">
                <div className="h-4 bg-ink-100 rounded" />
                <div className="h-4 bg-ink-100 rounded" />
                <div className="h-4 bg-ink-100 rounded w-2/3" />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-display-md font-display text-ink-900 mb-4">Product Not Found</h1>
          <p className="text-ink-600 mb-8">{error || 'The product you are looking for does not exist.'}</p>
          <Link to="/products" className="btn-primary">
            Browse Products
          </Link>
        </div>
      </div>
    );
  }

  const images = product.images?.sort((a, b) => a.position - b.position) || [];
  const inStock = product.quantity > 0;
  const discount = product.compareAtPrice
    ? Math.round((1 - product.price / product.compareAtPrice) * 100)
    : 0;

  return (
    <div className="min-h-screen bg-sand-50">
      {/* Breadcrumb */}
      <div className="bg-white border-b border-ink-100">
        <div className="container-page py-4">
          <nav className="flex items-center text-sm text-ink-500">
            <Link to="/" className="hover:text-ink-900 transition-colors">Home</Link>
            <span className="mx-2">/</span>
            <Link to="/products" className="hover:text-ink-900 transition-colors">Products</Link>
            {product.category && (
              <>
                <span className="mx-2">/</span>
                <Link 
                  to={`/products?category=${product.category.id}`}
                  className="hover:text-ink-900 transition-colors"
                >
                  {product.category.name}
                </Link>
              </>
            )}
            <span className="mx-2">/</span>
            <span className="text-ink-900">{product.name}</span>
          </nav>
        </div>
      </div>

      <div className="container-page py-12">
        <div className="grid lg:grid-cols-2 gap-12">
          {/* Image Gallery */}
          <div className="space-y-4">
            <div className="aspect-square bg-white rounded-2xl overflow-hidden shadow-sm border border-ink-100">
              {images.length > 0 ? (
                <img
                  src={images[selectedImage]?.url}
                  alt={images[selectedImage]?.alt || product.name}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-ink-300">
                  <svg className="w-24 h-24" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
              )}
            </div>
            
            {images.length > 1 && (
              <div className="flex gap-3 overflow-x-auto pb-2">
                {images.map((img, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSelectedImage(idx)}
                    className={`w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden border-2 transition-colors ${
                      selectedImage === idx ? 'border-accent-600' : 'border-transparent'
                    }`}
                  >
                    <img
                      src={img.url}
                      alt={img.alt || `${product.name} ${idx + 1}`}
                      className="w-full h-full object-cover"
                    />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Product Info */}
          <div className="space-y-6">
            {/* Brand */}
            {product.brand && (
              <p className="text-sm font-medium text-accent-600 uppercase tracking-wide">
                {product.brand.name}
              </p>
            )}

            {/* Title */}
            <h1 className="text-display-md font-display text-ink-900">
              {product.name}
            </h1>

            {/* Rating */}
            {product.reviewCount !== undefined && product.reviewCount > 0 && (
              <div className="flex items-center gap-2">
                <div className="flex">{renderStars(product.averageRating || 0)}</div>
                <span className="text-ink-600">
                  {product.averageRating?.toFixed(1)} ({product.reviewCount} reviews)
                </span>
              </div>
            )}

            {/* Price */}
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-display font-bold text-ink-900">
                {formatPrice(product.price)}
              </span>
              {product.compareAtPrice && (
                <>
                  <span className="text-xl text-ink-400 line-through">
                    {formatPrice(product.compareAtPrice)}
                  </span>
                  <span className="px-2 py-1 bg-red-100 text-red-700 text-sm font-medium rounded">
                    {discount}% OFF
                  </span>
                </>
              )}
            </div>

            {/* Short Description */}
            {product.shortDescription && (
              <p className="text-ink-600 text-lg leading-relaxed">
                {product.shortDescription}
              </p>
            )}

            {/* Stock Status */}
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${inStock ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className={inStock ? 'text-green-700' : 'text-red-700'}>
                {inStock ? `In Stock (${product.quantity} available)` : 'Out of Stock'}
              </span>
            </div>

            {/* Quantity & Add to Cart */}
            <div className="flex flex-col sm:flex-row gap-4 pt-4">
              <div className="flex items-center border border-ink-200 rounded-lg">
                <button
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  className="px-4 py-3 text-ink-600 hover:text-ink-900 transition-colors"
                  disabled={!inStock}
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                  </svg>
                </button>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, Math.min(product.quantity, parseInt(e.target.value) || 1)))}
                  className="w-16 text-center py-3 border-x border-ink-200 focus:outline-none"
                  min="1"
                  max={product.quantity}
                  disabled={!inStock}
                />
                <button
                  onClick={() => setQuantity(Math.min(product.quantity, quantity + 1))}
                  className="px-4 py-3 text-ink-600 hover:text-ink-900 transition-colors"
                  disabled={!inStock || quantity >= product.quantity}
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </button>
              </div>

              <button
                onClick={handleAddToCart}
                disabled={!inStock || addingToCart}
                className={`flex-1 py-3 px-8 rounded-lg font-medium transition-all ${
                  addedToCart
                    ? 'bg-green-600 text-white'
                    : inStock
                    ? 'bg-ink-900 text-white hover:bg-ink-800'
                    : 'bg-ink-200 text-ink-400 cursor-not-allowed'
                }`}
              >
                {addingToCart ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Adding...
                  </span>
                ) : addedToCart ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Added to Cart
                  </span>
                ) : (
                  'Add to Cart'
                )}
              </button>
            </div>

            {/* Category */}
            {product.category && (
              <div className="pt-6 border-t border-ink-100">
                <span className="text-sm text-ink-500">Category: </span>
                <Link 
                  to={`/products?category=${product.category.id}`}
                  className="text-sm text-accent-600 hover:text-accent-700"
                >
                  {product.category.name}
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Description */}
        {product.description && (
          <div className="mt-16">
            <h2 className="text-display-sm font-display text-ink-900 mb-6">Description</h2>
            <div 
              className="prose prose-lg max-w-none text-ink-600"
              dangerouslySetInnerHTML={{ __html: product.description }}
            />
          </div>
        )}

        {/* Reviews */}
        {product.reviews && product.reviews.length > 0 && (
          <div className="mt-16">
            <h2 className="text-display-sm font-display text-ink-900 mb-6">
              Customer Reviews ({product.reviewCount})
            </h2>
            <div className="space-y-6">
              {product.reviews.map((review) => (
                <div key={review.id} className="bg-white rounded-xl p-6 shadow-sm border border-ink-100">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <div className="flex">{renderStars(review.rating)}</div>
                        {review.title && (
                          <span className="font-medium text-ink-900">{review.title}</span>
                        )}
                      </div>
                      <p className="text-sm text-ink-500">
                        By {review.user.firstName} {review.user.lastName} on{' '}
                        {new Date(review.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <p className="text-ink-600">{review.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
