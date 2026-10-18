import { Link } from 'react-router-dom';
import { ArrowRight, LockKeyhole, Database, ShieldCheck, Code2, PackageSearch } from 'lucide-react';

/**
 * Portfolio storefront: showcase the actual application and its security model.
 * All CTAs link to implemented routes. No fabricated customer or sales claims.
 */
const capabilities = [
  { icon: LockKeyhole, title: 'Account security', description: 'JWT authentication, role-aware API access and refresh-token rotation.' },
  { icon: Database, title: 'Reliable transactions', description: 'PostgreSQL-backed catalog and order workflows with validation.' },
  { icon: ShieldCheck, title: 'Defence in depth', description: 'Rate limiting, security headers, explicit CORS and integration tests.' },
];

export function HomePage() {
  return (
    <main className="min-h-screen bg-sand-50">
      <section className="relative overflow-hidden border-b border-sand-200 bg-gradient-to-br from-sand-50 via-white to-primary-50">
        <div className="container-page grid gap-12 py-20 md:py-28 lg:grid-cols-2 lg:items-center">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-primary-200 bg-white px-4 py-2 text-sm font-semibold text-primary-700">
              <ShieldCheck aria-hidden="true" className="h-4 w-4" />
              Full-stack security engineering demo
            </span>
            <h1 className="mt-7 max-w-2xl font-display text-display-lg leading-tight text-ink-900 md:text-display-xl">
              A modern storefront, built with security in mind.
            </h1>
            <p className="mt-6 max-w-xl text-body-xl leading-relaxed text-ink-600">
              Explore a React and TypeScript storefront backed by a FastAPI and PostgreSQL service.
              Browse the demo catalog, inspect account flows, and discover the architecture behind them.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Link to="/products" className="btn-primary inline-flex items-center gap-2">
                Browse demo products <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
              <Link to="/skills" className="btn-secondary inline-flex items-center gap-2">
                Explore engineering details <Code2 aria-hidden="true" className="h-4 w-4" />
              </Link>
            </div>
            <p className="mt-6 max-w-xl text-sm text-ink-500">
              Portfolio demonstration using synthetic catalog data. Live payment processing and email delivery are not enabled.
            </p>
          </div>
          <div aria-label="SecureShop feature preview" className="rounded-2xl border border-sand-200 bg-white p-5 shadow-elevated md:p-7">
            <div className="flex items-center justify-between border-b border-sand-200 pb-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-primary-600">SecureShop / architecture</p>
                <h2 className="mt-2 text-2xl font-semibold text-ink-900">Engineered end to end</h2>
              </div>
              <ShieldCheck aria-hidden="true" className="h-10 w-10 text-primary-600" />
            </div>
            <ol className="mt-6 space-y-5">
              <li className="flex gap-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-100 font-bold text-primary-700">01</span>
                <div><h3 className="font-semibold text-ink-900">React + TypeScript</h3><p className="mt-1 text-sm text-ink-600">Responsive catalog, account and shopping flows.</p></div>
              </li>
              <li className="flex gap-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-100 font-bold text-primary-700">02</span>
                <div><h3 className="font-semibold text-ink-900">FastAPI services</h3><p className="mt-1 text-sm text-ink-600">Validated API requests and authentication boundaries.</p></div>
              </li>
              <li className="flex gap-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-100 font-bold text-primary-700">03</span>
                <div><h3 className="font-semibold text-ink-900">PostgreSQL persistence</h3><p className="mt-1 text-sm text-ink-600">Relational data models and transactional order logic.</p></div>
              </li>
            </ol>
            <Link to="/products" className="mt-7 flex items-center justify-between rounded-xl bg-ink-900 p-4 font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
              Explore the live catalog <PackageSearch aria-hidden="true" className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      <section className="section bg-white" aria-labelledby="security-heading">
        <div className="container-page">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary-600">Under the hood</p>
          <h2 id="security-heading" className="mt-2 max-w-2xl font-display text-display-sm text-ink-900 md:text-display-md">
            Built to demonstrate the engineering behind the interface.
          </h2>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {capabilities.map(({ icon: Icon, title, description }) => (
              <article key={title} className="rounded-2xl border border-sand-200 bg-sand-50 p-7">
                <div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100 text-primary-700">
                  <Icon aria-hidden="true" className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-semibold text-ink-900">{title}</h3>
                <p className="mt-3 leading-relaxed text-ink-600">{description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section bg-ink-900 text-sand-50" aria-labelledby="try-heading">
        <div className="container-page flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-primary-400">Try the workflow</p>
            <h2 id="try-heading" className="mt-2 font-display text-display-sm">Inspect the interface yourself.</h2>
            <p className="mt-3 max-w-xl text-sand-300">Browse synthetic products without an account, or visit the engineering page to see the stack.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/products" className="btn-primary">Open catalog</Link>
            <Link to="/skills" className="btn-secondary">View technical skills</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
