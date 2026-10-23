import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownRight, ArrowRight, ShieldCheck, ShoppingBag, Sparkles, Truck } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
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

const collections = [
  {
    name: 'The new edit',
    description: 'Fresh finds, timeless appeal.',
    to: '/products?sort=newest',
    image: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=1100&q=85',
    className: 'editorial-tile--first',
  },
  {
    name: 'Everyday essentials',
    description: 'Considered pieces for daily living.',
    to: '/products?sort=price-low',
    image: 'https://images.unsplash.com/photo-1546868871-7041f2a55e12?auto=format&fit=crop&w=1100&q=85',
    className: 'editorial-tile--second',
  },
];

export function HomePage() {
  const [products, setProducts] = useState<FeaturedProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const reduceMotion = useReducedMotion();

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
    <main className="immersive-shop min-h-screen">
      <section className="shop-hero relative isolate overflow-hidden" aria-labelledby="hero-title">
        <div className="shop-hero-glow" aria-hidden="true" />
        <div className="container-page relative z-10 grid min-h-[660px] gap-12 pb-20 pt-20 lg:min-h-[760px] lg:grid-cols-[1fr_1.02fr] lg:items-center lg:gap-10 lg:py-24">
          <motion.div initial={reduceMotion ? false : { opacity: 0, y: 35 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .8, ease: 'easeOut' }} className="relative z-10 max-w-2xl">
            <div className="shop-eyebrow"><span className="shop-eyebrow-line" /> THE ART OF FINDING BETTER</div>
            <h1 id="hero-title" className="shop-hero-title mt-7">A little more <em>extraordinary.</em></h1>
            <p className="shop-hero-copy mt-7 max-w-lg">A curated world of everyday objects, thoughtful details, and things you'll love to live with.</p>
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <Link to="/products" className="shop-pill-button">Explore collection <ArrowUpRightIcon /></Link>
              <Link to="/products?sort=newest" className="shop-text-link">See what's new <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
            </div>
            <div className="shop-hero-bottom mt-14 flex items-center gap-5">
              <span className="shop-index">01 <span className="text-white/30">/ 03</span></span>
              <span className="shop-index-line" />
              <span className="text-xs uppercase tracking-[.22em] text-white/60">Your next favorite awaits</span>
            </div>
          </motion.div>
          <motion.div initial={reduceMotion ? false : { opacity: 0, y: 48, rotate: -3 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ duration: 1, delay: .15 }} className="shop-stage relative mx-auto w-full max-w-[650px]">
            <div className="shop-stage-ring shop-stage-ring--one" aria-hidden="true" />
            <div className="shop-stage-ring shop-stage-ring--two" aria-hidden="true" />
            <div className="shop-visual-card">
              <img src="https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=1400&q=90" alt="Sculptural contemporary chair in a warm minimalist interior" className="shop-hero-photo" fetchPriority="high" />
              <div className="shop-visual-shade" />
              <div className="shop-visual-caption"><span>THE CURATED EDIT</span><span>EST. FOR EVERYDAY</span></div>
            </div>
            <div className="shop-floating-label" aria-hidden="true"><Sparkles size={17} /> Thoughtfully selected</div>
            <div className="shop-stage-orb" aria-hidden="true" />
          </motion.div>
        </div>
        <div className="shop-bottom-fade" aria-hidden="true" />
      </section>

      <section className="shop-benefits border-b border-[#eae6df]" aria-label="Shopping benefits">
        <div className="container-page grid gap-5 py-6 md:grid-cols-3 md:gap-10">
          <div><Sparkles size={18} aria-hidden="true" /><span>Curated with intention</span></div>
          <div><ShieldCheck size={18} aria-hidden="true" /><span>Shop with confidence</span></div>
          <div><Truck size={18} aria-hidden="true" /><span>Discover something different</span></div>
        </div>
      </section>

      <section className="section shop-collections" aria-labelledby="collections-heading">
        <div className="container-page">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-5">
            <div><p className="shop-section-kicker">01 / THE COLLECTIONS</p><h2 id="collections-heading" className="shop-section-title mt-3">Curiosity looks <em>good on you.</em></h2></div>
            <Link to="/products" className="shop-dark-link">Shop everything <ArrowRight size={17} aria-hidden="true" /></Link>
          </div>
          <div className="grid gap-5 md:grid-cols-2 md:gap-7">
            {collections.map((collection, index) => (
              <motion.div key={collection.name} initial={reduceMotion ? false : { opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .2 }} transition={{ delay: index * .12, duration: .6 }}>
                <Link to={collection.to} className={`editorial-tile group ${collection.className}`}>
                  <img src={collection.image} alt="" loading="lazy" />
                  <div className="editorial-tile-shade" />
                  <div className="editorial-tile-content"><span className="editorial-overline">EXPLORE / 0{index + 1}</span><div className="flex items-end justify-between gap-4"><div><h3>{collection.name}</h3><p>{collection.description}</p></div><span className="editorial-arrow"><ArrowDownRight size={24} aria-hidden="true" /></span></div></div>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="section shop-products-section" aria-labelledby="products-heading">
        <div className="container-page">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
            <div><p className="shop-section-kicker">02 / SELECTED FOR YOU</p><h2 id="products-heading" className="shop-section-title mt-3">The good <em>stuff.</em></h2><p className="mt-3 max-w-xl text-[#6f6a64]">Made for the moments that matter, big and small.</p></div>
            <Link to="/products" className="shop-dark-link">View all products <ArrowRight size={17} aria-hidden="true" /></Link>
          </div>
          {loading ? (
            <div aria-label="Loading products" aria-busy="true" className="grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6">
              {Array.from({ length: 4 }, (_, i) => <div key={i} className="animate-pulse overflow-hidden rounded-2xl bg-white"><div className="aspect-[4/5] bg-[#e9e4dd]" /><div className="space-y-3 p-4"><div className="h-4 w-3/4 rounded bg-[#eee9e2]" /><div className="h-4 w-1/2 rounded bg-[#eee9e2]" /></div></div>)}
            </div>
          ) : error ? (
            <div role="status" className="rounded-3xl border border-[#e8e3da] bg-white p-10 text-center"><p>We couldn't load the collection right now.</p><Link to="/products" className="mt-4 inline-flex font-semibold underline">Try browsing the catalog</Link></div>
          ) : products.length === 0 ? (
            <div className="rounded-3xl border border-[#e8e3da] bg-white p-10 text-center"><p>New products are on their way.</p><Link to="/products" className="mt-4 inline-flex font-semibold underline">Browse the catalog</Link></div>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6">
              {products.map((product, index) => <ProductCard key={product.id} product={product} priority={index < 2} />)}
            </div>
          )}
        </div>
      </section>
      <section className="shop-final-cta"><div className="container-page relative z-10 py-24 text-center md:py-32"><p className="shop-section-kicker !text-[#d9b79a]">THE DISCOVERY CONTINUES</p><h2 className="mx-auto mt-5 max-w-3xl font-display text-4xl text-white md:text-6xl">Good things are <em>out there.</em></h2><p className="mx-auto mt-6 max-w-md text-white/65">Explore a collection made to make the everyday feel anything but ordinary.</p><Link to="/products" className="shop-pill-button mx-auto mt-9">Find your next favorite <ArrowRight size={18} aria-hidden="true" /></Link></div></section>
    </main>
  );
}

function ArrowUpRightIcon() { return <ArrowRight className="-rotate-45 h-[18px] w-[18px]" aria-hidden="true" />; }
