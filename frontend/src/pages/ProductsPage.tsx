import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ProductCard } from '../components/product/ProductCard';
import { api } from '../utils/api';

interface Product {
  id: string;
  name: string;
  slug: string;
  shortDescription?: string;
  price: number;
  compareAtPrice?: number;
  images?: { url: string; alt?: string }[];
  category?: { id: string; name: string; slug: string };
  isFeatured: boolean;
}

interface Category {
  id: string;
  name: string;
  slug: string;
  _count?: { products: number };
}

interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export function ProductsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Get current filters from URL
  const currentPage = parseInt(searchParams.get('page') || '1', 10);
  const currentCategory = searchParams.get('category') || '';
  const currentSort = searchParams.get('sort') || 'newest';
  const currentSearch = searchParams.get('search') || '';
  const minPrice = searchParams.get('minPrice') || '';
  const maxPrice = searchParams.get('maxPrice') || '';

  // Fetch categories
  useEffect(() => {
    api.get('/products/categories')
      .then(res => setCategories(res.data.data.categories))
      .catch(console.error);
  }, []);

  // Fetch products
  useEffect(() => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('page', currentPage.toString());
    params.set('limit', '12');
    
    if (currentCategory) params.set('category', currentCategory);
    if (currentSearch) params.set('search', currentSearch);
    if (minPrice) params.set('minPrice', minPrice);
    if (maxPrice) params.set('maxPrice', maxPrice);

    // Handle sorting
    switch (currentSort) {
      case 'price-low':
        params.set('sortBy', 'price');
        params.set('sortOrder', 'asc');
        break;
      case 'price-high':
        params.set('sortBy', 'price');
        params.set('sortOrder', 'desc');
        break;
      case 'name':
        params.set('sortBy', 'name');
        params.set('sortOrder', 'asc');
        break;
      default:
        params.set('sortBy', 'createdAt');
        params.set('sortOrder', 'desc');
    }

    api.get(`/products?${params.toString()}`)
      .then(res => {
        setProducts(res.data.data.products);
        setPagination(res.data.data.pagination);
      })
      .catch(err => {
        setError(err.response?.data?.error?.message || 'Failed to load products');
      })
      .finally(() => setLoading(false));
  }, [currentPage, currentCategory, currentSort, currentSearch, minPrice, maxPrice]);

  const updateFilters = (updates: Record<string, string>) => {
    const newParams = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) {
        newParams.set(key, value);
      } else {
        newParams.delete(key);
      }
    });
    // Reset to page 1 when filters change (except when changing page)
    if (!updates.page) {
      newParams.set('page', '1');
    }
    setSearchParams(newParams);
  };

  return (
    <div className="min-h-screen bg-sand-50">
      {/* Header */}
      <div className="bg-ink-900 text-white py-16">
        <div className="container-page">
          <h1 className="text-display-lg font-display mb-4">Shop All Products</h1>
          <p className="text-ink-300 text-lg max-w-2xl">
            Discover our curated collection of premium products, crafted with care and designed to elevate your everyday.
          </p>
        </div>
      </div>

      <div className="container-page py-12">
        <div className="flex flex-col lg:flex-row gap-8">
          {/* Sidebar Filters */}
          <aside className="lg:w-64 flex-shrink-0">
            <div className="bg-white rounded-xl p-6 shadow-sm border border-ink-100 sticky top-24">
              <h3 className="font-display text-lg text-ink-900 mb-6">Filters</h3>

              {/* Search */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-ink-700 mb-2">
                  Search
                </label>
                <input
                  type="text"
                  value={currentSearch}
                  onChange={(e) => updateFilters({ search: e.target.value })}
                  placeholder="Search products..."
                  className="w-full px-3 py-2 border border-ink-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-transparent"
                />
              </div>

              {/* Categories */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-ink-700 mb-2">
                  Category
                </label>
                <select
                  value={currentCategory}
                  onChange={(e) => updateFilters({ category: e.target.value })}
                  className="w-full px-3 py-2 border border-ink-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                  <option value="">All Categories</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name} {cat._count && `(${cat._count.products})`}
                    </option>
                  ))}
                </select>
              </div>

              {/* Price Range */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-ink-700 mb-2">
                  Price Range
                </label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    value={minPrice}
                    onChange={(e) => updateFilters({ minPrice: e.target.value })}
                    placeholder="Min"
                    className="w-full px-3 py-2 border border-ink-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
                  />
                  <span className="text-ink-400">-</span>
                  <input
                    type="number"
                    value={maxPrice}
                    onChange={(e) => updateFilters({ maxPrice: e.target.value })}
                    placeholder="Max"
                    className="w-full px-3 py-2 border border-ink-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
                  />
                </div>
              </div>

              {/* Clear Filters */}
              <button
                onClick={() => setSearchParams(new URLSearchParams())}
                className="w-full py-2 text-sm text-ink-600 hover:text-ink-900 transition-colors"
              >
                Clear all filters
              </button>
            </div>
          </aside>

          {/* Product Grid */}
          <main className="flex-1">
            {/* Sort & Results Count */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
              <p className="text-ink-600">
                {pagination && (
                  <>
                    Showing {((currentPage - 1) * pagination.limit) + 1}-
                    {Math.min(currentPage * pagination.limit, pagination.total)} of {pagination.total} products
                  </>
                )}
              </p>
              <select
                value={currentSort}
                onChange={(e) => updateFilters({ sort: e.target.value })}
                className="px-4 py-2 border border-ink-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent-500"
              >
                <option value="newest">Newest First</option>
                <option value="price-low">Price: Low to High</option>
                <option value="price-high">Price: High to Low</option>
                <option value="name">Name: A-Z</option>
              </select>
            </div>

            {/* Loading State */}
            {loading && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="bg-white rounded-xl overflow-hidden animate-pulse">
                    <div className="aspect-square bg-ink-100" />
                    <div className="p-4 space-y-3">
                      <div className="h-4 bg-ink-100 rounded w-3/4" />
                      <div className="h-4 bg-ink-100 rounded w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Error State */}
            {error && (
              <div className="text-center py-12">
                <p className="text-red-600 mb-4">{error}</p>
                <button
                  onClick={() => window.location.reload()}
                  className="btn-primary"
                >
                  Try Again
                </button>
              </div>
            )}

            {/* Products Grid */}
            {!loading && !error && (
              <>
                {products.length === 0 ? (
                  <div className="text-center py-12">
                    <p className="text-ink-600 text-lg mb-4">No products found</p>
                    <button
                      onClick={() => setSearchParams(new URLSearchParams())}
                      className="text-accent-600 hover:text-accent-700 font-medium"
                    >
                      Clear filters
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                    {products.map((product) => (
                      <ProductCard key={product.id} product={product} />
                    ))}
                  </div>
                )}

                {/* Pagination */}
                {pagination && pagination.totalPages > 1 && (
                  <div className="flex justify-center items-center gap-2 mt-12">
                    <button
                      onClick={() => updateFilters({ page: (currentPage - 1).toString() })}
                      disabled={!pagination.hasPrev}
                      className="px-4 py-2 rounded-lg border border-ink-200 text-ink-700 hover:bg-ink-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Previous
                    </button>
                    
                    <div className="flex gap-1">
                      {[...Array(pagination.totalPages)].map((_, i) => {
                        const page = i + 1;
                        // Show first, last, and pages around current
                        if (
                          page === 1 ||
                          page === pagination.totalPages ||
                          (page >= currentPage - 1 && page <= currentPage + 1)
                        ) {
                          return (
                            <button
                              key={page}
                              onClick={() => updateFilters({ page: page.toString() })}
                              className={`w-10 h-10 rounded-lg font-medium transition-colors ${
                                page === currentPage
                                  ? 'bg-accent-600 text-white'
                                  : 'text-ink-700 hover:bg-ink-100'
                              }`}
                            >
                              {page}
                            </button>
                          );
                        } else if (page === currentPage - 2 || page === currentPage + 2) {
                          return <span key={page} className="px-2 text-ink-400">...</span>;
                        }
                        return null;
                      })}
                    </div>

                    <button
                      onClick={() => updateFilters({ page: (currentPage + 1).toString() })}
                      disabled={!pagination.hasNext}
                      className="px-4 py-2 rounded-lg border border-ink-200 text-ink-700 hover:bg-ink-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
