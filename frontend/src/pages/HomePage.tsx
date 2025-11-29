import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Shield, Truck, RefreshCw, Star } from 'lucide-react';
import { ProductCard } from '../components/product/ProductCard';

// Animation variants
const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

const stagger = {
  visible: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

// Mock featured products (would come from API)
const featuredProducts = [
  {
    id: '1',
    name: 'Minimal Leather Tote',
    slug: 'minimal-leather-tote',
    price: 189,
    compareAtPrice: 249,
    images: [{ url: '/images/products/tote.jpg', alt: 'Leather tote bag' }],
    category: { name: 'Bags', slug: 'bags' },
  },
  {
    id: '2',
    name: 'Ceramic Pour Over Set',
    slug: 'ceramic-pour-over-set',
    price: 78,
    images: [{ url: '/images/products/pourover.jpg', alt: 'Pour over coffee set' }],
    category: { name: 'Kitchen', slug: 'kitchen' },
  },
  {
    id: '3',
    name: 'Merino Wool Throw',
    slug: 'merino-wool-throw',
    price: 145,
    images: [{ url: '/images/products/throw.jpg', alt: 'Wool throw blanket' }],
    category: { name: 'Home', slug: 'home' },
  },
  {
    id: '4',
    name: 'Brass Desk Lamp',
    slug: 'brass-desk-lamp',
    price: 225,
    images: [{ url: '/images/products/lamp.jpg', alt: 'Brass desk lamp' }],
    category: { name: 'Lighting', slug: 'lighting' },
  },
];

const features = [
  {
    icon: Shield,
    title: 'Secure Shopping',
    description: 'Industry-leading security with encrypted transactions.',
  },
  {
    icon: Truck,
    title: 'Free Shipping',
    description: 'Complimentary shipping on all orders over $100.',
  },
  {
    icon: RefreshCw,
    title: 'Easy Returns',
    description: '30-day hassle-free returns on all items.',
  },
];

const testimonials = [
  {
    content: 'The quality exceeded my expectations. Every detail is thoughtfully designed.',
    author: 'Sarah M.',
    role: 'Interior Designer',
    rating: 5,
  },
  {
    content: 'Finally, a shop that prioritizes both aesthetics and security. Highly recommend.',
    author: 'James L.',
    role: 'Architect',
    rating: 5,
  },
];

export function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative min-h-[85vh] flex items-center overflow-hidden">
        {/* Background with subtle gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-sand-100 via-sand-50 to-primary-50/30" />
        
        {/* Decorative elements */}
        <div className="absolute top-20 right-20 w-96 h-96 bg-primary-200/20 rounded-full blur-3xl" />
        <div className="absolute bottom-20 left-20 w-72 h-72 bg-ocean-400/10 rounded-full blur-3xl" />

        <div className="container-page relative">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-center">
            {/* Hero content */}
            <motion.div
              initial="hidden"
              animate="visible"
              variants={stagger}
              className="text-center lg:text-left"
            >
              <motion.span
                variants={fadeInUp}
                className="inline-block px-4 py-1.5 bg-primary-100 text-primary-700 text-body-sm font-medium rounded-full mb-6"
              >
                New Collection 2025
              </motion.span>

              <motion.h1
                variants={fadeInUp}
                className="text-display-lg md:text-display-xl font-display text-ink-900 mb-6"
              >
                Curated for
                <br />
                <span className="text-primary-600">Modern Living</span>
              </motion.h1>

              <motion.p
                variants={fadeInUp}
                className="text-body-xl text-ink-600 mb-8 max-w-lg mx-auto lg:mx-0"
              >
                Discover thoughtfully designed essentials that bring warmth, 
                function, and beauty to your everyday life.
              </motion.p>

              <motion.div
                variants={fadeInUp}
                className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start"
              >
                <Link to="/products" className="btn-primary">
                  Shop Collection
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <Link to="/about" className="btn-secondary">
                  Our Story
                </Link>
              </motion.div>

              {/* Trust indicators */}
              <motion.div
                variants={fadeInUp}
                className="mt-12 flex items-center gap-6 justify-center lg:justify-start"
              >
                <div className="flex -space-x-2">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="w-10 h-10 rounded-full bg-sand-300 border-2 border-sand-50"
                    />
                  ))}
                </div>
                <div className="text-left">
                  <div className="flex items-center gap-1 text-primary-500">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Star key={i} className="w-4 h-4 fill-current" />
                    ))}
                  </div>
                  <p className="text-body-sm text-ink-500">
                    Trusted by 10,000+ customers
                  </p>
                </div>
              </motion.div>
            </motion.div>

            {/* Hero image composition */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="relative hidden lg:block"
            >
              <div className="relative aspect-[4/5] max-w-md mx-auto">
                {/* Main image placeholder */}
                <div className="absolute inset-0 bg-sand-200 rounded-2xl overflow-hidden shadow-elevated">
                  <div className="w-full h-full bg-gradient-to-br from-sand-100 to-sand-200 flex items-center justify-center">
                    <span className="text-sand-400 text-body-lg">Featured Image</span>
                  </div>
                </div>

                {/* Floating accent card */}
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 }}
                  className="absolute -right-8 top-1/4 bg-white rounded-card shadow-card p-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center">
                      <Shield className="w-6 h-6 text-primary-600" />
                    </div>
                    <div>
                      <p className="text-body-sm font-medium text-ink-900">Secure</p>
                      <p className="text-body-xs text-ink-500">256-bit encryption</p>
                    </div>
                  </div>
                </motion.div>

                {/* Stats card */}
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.7 }}
                  className="absolute -left-8 bottom-1/4 bg-ink-900 text-sand-50 rounded-card shadow-elevated p-4"
                >
                  <p className="text-display-sm font-display">10K+</p>
                  <p className="text-body-sm text-sand-400">Happy Customers</p>
                </motion.div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="section bg-white">
        <div className="container-page">
          <div className="grid md:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="text-center p-6"
              >
                <div className="w-14 h-14 mx-auto mb-4 bg-sand-100 rounded-xl flex items-center justify-center">
                  <feature.icon className="w-7 h-7 text-ink-700" />
                </div>
                <h3 className="text-lg font-medium text-ink-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-body-md text-ink-500">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Products Section */}
      <section className="section">
        <div className="container-page">
          <div className="flex items-end justify-between mb-10">
            <div>
              <span className="text-body-sm text-primary-600 font-medium">
                Curated Selection
              </span>
              <h2 className="text-display-sm md:text-display-md font-display text-ink-900 mt-1">
                Featured Products
              </h2>
            </div>
            <Link
              to="/products"
              className="hidden sm:flex items-center gap-2 text-body-md text-ink-700 hover:text-primary-600 transition-colors"
            >
              View all
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="product-grid">
            {featuredProducts.map((product, index) => (
              <motion.div
                key={product.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
              >
                <ProductCard product={product} />
              </motion.div>
            ))}
          </div>

          <div className="mt-8 text-center sm:hidden">
            <Link to="/products" className="btn-secondary">
              View All Products
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="section bg-ink-900 text-sand-50">
        <div className="container-page">
          <div className="text-center mb-12">
            <span className="text-body-sm text-primary-400 font-medium">
              What People Say
            </span>
            <h2 className="text-display-sm md:text-display-md font-display text-sand-50 mt-1">
              Customer Stories
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {testimonials.map((testimonial, index) => (
              <motion.div
                key={testimonial.author}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="bg-ink-800 rounded-card p-8"
              >
                <div className="flex gap-1 mb-4">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <Star key={i} className="w-4 h-4 text-primary-400 fill-current" />
                  ))}
                </div>
                <blockquote className="text-body-lg text-sand-200 mb-6">
                  "{testimonial.content}"
                </blockquote>
                <div>
                  <p className="font-medium text-sand-50">{testimonial.author}</p>
                  <p className="text-body-sm text-sand-400">{testimonial.role}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="section">
        <div className="container-page">
          <div className="relative bg-sand-100 rounded-2xl overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-primary-500/10 to-transparent" />
            <div className="relative px-8 py-16 md:px-16 md:py-20 text-center">
              <h2 className="text-display-sm md:text-display-md font-display text-ink-900 mb-4">
                Join Our Community
              </h2>
              <p className="text-body-xl text-ink-600 mb-8 max-w-xl mx-auto">
                Get early access to new collections, exclusive offers, and design inspiration.
              </p>
              <form className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
                <input
                  type="email"
                  placeholder="Enter your email"
                  className="input flex-1"
                />
                <button type="submit" className="btn-primary whitespace-nowrap">
                  Subscribe
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
