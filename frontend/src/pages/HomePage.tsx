import { Link } from 'react-router-dom';
import { ArrowRight, ShoppingBag, Search, Heart, ShieldCheck } from 'lucide-react';

/**
 * Customer-first storefront. Technical implementation belongs in the repository,
 * not in the shopping journey.
 */
export function HomePage() {
  return (
    <main className="min-h-screen bg-sand-50">
      <section className="relative overflow-hidden border-b border-sand-200 bg-gradient-to-br from-sand-50 via-white to-primary-50">
        <div className="container-page grid gap-12 py-16 md:py-24 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary-700">Welcome to SecureShop</p>
            <h1 className="mt-5 max-w-2xl font-display text-display-lg leading-tight text-ink-900 md:text-display-xl">
              Good things, thoughtfully chosen.
            </h1>
            <p className="mt-6 max-w-xl text-body-xl leading-relaxed text-ink-600">
              Discover everyday favorites in a clean, easy-to-shop collection. Find what you love, explore the details, and shop with confidence.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Link to="/products" className="btn-primary inline-flex items-center gap-2">
                Shop the collection <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
              <Link to="/cart" className="btn-secondary inline-flex items-center gap-2">
                View your bag <ShoppingBag aria-hidden="true" className="h-4 w-4" />
              </Link>
            </div>
            <p className="mt-6 max-w-xl text-sm text-ink-500">
              Demo storefront with sample products. No real payments are processed.
            </p>
          </div>
          <div className="relative overflow-hidden rounded-3xl bg-ink-900 p-8 text-white shadow-elevated md:p-12">
            <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-primary-500/20 blur-3xl" aria-hidden="true" />
            <div className="relative">
              <p className="text-sm font-semibold uppercase tracking-widest text-primary-300">Made for discovering</p>
              <h2 className="mt-5 max-w-sm font-display text-display-md leading-tight">Find your next favorite.</h2>
              <p className="mt-5 max-w-sm leading-relaxed text-sand-300">A little inspiration goes a long way. Browse the collection and see what catches your eye.</p>
              <div className="mt-10 grid grid-cols-2 gap-3">
                <Link to="/products" className="group flex min-h-32 flex-col justify-between rounded-2xl bg-white/10 p-5 transition-colors hover:bg-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">
                  <Search aria-hidden="true" className="h-7 w-7" />
                  <span className="flex items-center justify-between font-semibold">Explore products <ArrowRight aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-x-1" /></span>
                </Link>
                <Link to="/cart" className="group flex min-h-32 flex-col justify-between rounded-2xl bg-white/10 p-5 transition-colors hover:bg-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">
                  <ShoppingBag aria-hidden="true" className="h-7 w-7" />
                  <span className="flex items-center justify-between font-semibold">Your shopping bag <ArrowRight aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-x-1" /></span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section className="section bg-white" aria-labelledby="discover-heading">
        <div className="container-page">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary-600">The little details</p>
          <h2 id="discover-heading" className="mt-2 max-w-2xl font-display text-display-sm text-ink-900 md:text-display-md">A simpler way to shop.</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            <article className="rounded-2xl border border-sand-200 bg-sand-50 p-7">
              <Search aria-hidden="true" className="h-7 w-7 text-primary-600" />
              <h3 className="mt-5 text-xl font-semibold text-ink-900">Find it faster</h3>
              <p className="mt-3 leading-relaxed text-ink-600">Search, filter, and sort the catalog to narrow down what matters to you.</p>
            </article>
            <article className="rounded-2xl border border-sand-200 bg-sand-50 p-7">
              <Heart aria-hidden="true" className="h-7 w-7 text-primary-600" />
              <h3 className="mt-5 text-xl font-semibold text-ink-900">Explore every detail</h3>
              <p className="mt-3 leading-relaxed text-ink-600">Take a closer look at products before adding them to your bag.</p>
            </article>
            <article className="rounded-2xl border border-sand-200 bg-sand-50 p-7">
              <ShieldCheck aria-hidden="true" className="h-7 w-7 text-primary-600" />
              <h3 className="mt-5 text-xl font-semibold text-ink-900">Shop with confidence</h3>
              <p className="mt-3 leading-relaxed text-ink-600">Clear navigation and a straightforward cart experience from start to finish.</p>
            </article>
          </div>
          <Link to="/products" className="mt-10 inline-flex items-center gap-2 font-semibold text-primary-700 underline underline-offset-4">
            Browse all products <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </main>
  );
}
