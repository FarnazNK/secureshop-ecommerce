import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ShoppingBag } from 'lucide-react';
import { ProductCard } from '../components/product/ProductCard';
import { api } from '../utils/api';

interface FeaturedProduct {
  id: string;
  name: string;
  slug: string;
  price: number;
  compareAtPrice?: number;
  images: { url: string; alt?: string }[];
  category?: { name: string; slug: string };
}

export function HomePage() {
  const [products, setProducts] = useState<FeaturedProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    api.get('/products?limit=8&page=1')
      .then(({ data }) => {
        if (!active) return;
        setProducts((data.items ?? []).map((item: any) => ({
          id: item.id,
          name: item.name,
          slug: item.slug,
          price: Number(item.price),
          compareAtPrice: item.compare_at_price != null ? Number(item.compare_at_price) : undefined,
          images: item.images ?? [],
          category: item.category ?? undefined,
        })));
      })
      .catch(() => { if (active) setError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <main className="min-h-screen bg-sand-50">
      <section className="relative overflow-hidden border-b border-sand-200 bg-gradient-to-br from-sand-50 via-white to-primary-50">
        <div className="container-page grid gap-10 py-16 md:py-24 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary-700">SecureShop / The collection</p>
            <h1 className="mt-5 max-w-2xl font-display text-display-lg leading-tight text-ink-900 md:text-display-xl">
              Find something worth keeping.
            </h1>
            <p className="mt-6 max-w-xl text-body-xl leading-relaxed text-ink-600">
              Thoughtful essentials for everyday life. Browse the collection, discover your favorites, and make them yours.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Link to="/products" className="btn-primary inline-flex items-center gap-2">
                Shop all products <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
              <Link to="/cart" className="btn-secondary inline-flex items-center gap-2">
                Your bag <ShoppingBag aria-hidden="true" className="h-4 w-4" />
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3" aria-label="Explore the store">
            <Link to="/products?sort=newest" className="group relative flex min-h-64 flex-col justify-end overflow-hidden rounded-3xl bg-ink-900 p-6 text-white transition-transform hover:-translate-y-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
              <span className="mb-auto text-xs font-semibold uppercase tracking-widest text-sand-300">Discover</span>
              <span className="font-display text-2xl">New arrivals</span>
              <ArrowRight aria-hidden="true" className="mt-3 h-5 w-5 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link to="/products?sort=price-low" className="group relative mt-8 flex min-h-64 flex-col justify-end overflow-hidden rounded-3xl bg-primary-100 p-6 text-ink-900 transition-transform hover:-translate-y-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
              <span className="mb-auto text-xs font-semibold uppercase tracking-widest text-primary-700">Explore</span>
              <span className="font-display text-2xl">Everyday finds</span>
              <ArrowRight aria-hidden="true" className="mt-3 h-5 w-5 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </div>
      </section>
      <section className="section bg-white" aria-labelledby="products-heading">
        <div className="container-page">
          <div className="mb-9 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-widest text-primary-600">Browse the edit</p>
              <h2 id="products-heading" className="mt-2 font-display text-display-sm text-ink-900 md:text-display-md">Explore our products</h2>
            </div>
            <Link to="/products" className="inline-flex items-center gap-2 font-semibold text-primary-700 underline underline-offset-4">
              View all products <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
          </div>
          {loading ? (
            <div aria-label="Loading products" aria-busy="true" className="grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6">
              {Array.from({ length: 4 }, (_, i) => (
                <div key={i} className="animate-pulse overflow-hidden rounded-2xl border border-sand-200">
                  <div className="aspect-square bg-sand-100" />
                  <div className="space-y-3 p-4"><div className="h-4 w-3/4 rounded bg-sand-100" /><div className="h-4 w-1/2 rounded bg-sand-100" /></div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div role="status" className="rounded-2xl border border-sand-200 bg-sand-50 p-8 text-center">
              <p className="text-ink-700">We couldn't load the collection right now.</p>
              <Link to="/products" className="mt-4 inline-flex font-semibold text-primary-700 underline">Try browsing the catalog</Link>
            </div>
          ) : products.length === 0 ? (
            <div className="rounded-2xl border border-sand-200 bg-sand-50 p-8 text-center">
              <p className="text-ink-700">New products are on their way.</p>
              <Link to="/products" className="mt-4 inline-flex font-semibold text-primary-700 underline">Browse the catalog</Link>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6">
              {products.map((product, index) => <ProductCard key={product.id} product={product} priority={index < 2} />)}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
