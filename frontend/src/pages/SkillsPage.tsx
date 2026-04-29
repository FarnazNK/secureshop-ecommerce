import { motion } from 'framer-motion';
import {
  Code2,
  Layers,
  Boxes,
  Palette,
  TestTube2,
  Smartphone,
  Accessibility,
  Radio,
  Plug,
  BookOpen,
  LayoutDashboard,
  LineChart,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

const stagger = {
  visible: {
    transition: {
      staggerChildren: 0.08,
    },
  },
};

type Skill = {
  icon: typeof Code2;
  title: string;
  description: string;
  meta?: string;
};

const coreSkills: Skill[] = [
  {
    icon: Code2,
    title: 'React',
    description:
      'Five plus years architecting sophisticated, dynamic applications — from rich product flows to complex stateful interfaces.',
    meta: '5+ years',
  },
  {
    icon: Layers,
    title: 'TypeScript',
    description:
      'Strongly typed codebases end to end: discriminated unions, generics, and inference-first APIs that catch bugs at compile time.',
  },
  {
    icon: Boxes,
    title: 'Redux',
    description:
      'Predictable state management at scale, with middleware patterns, normalized stores, and clean separation of UI and domain logic.',
  },
  {
    icon: Palette,
    title: 'styled-components',
    description:
      'Theme-driven CSS-in-JS with composable variants, dynamic props, and runtime theming for cohesive component libraries.',
  },
  {
    icon: TestTube2,
    title: 'Jest',
    description:
      'Unit and integration coverage with React Testing Library — testing behavior, not implementation, and keeping suites fast.',
  },
  {
    icon: Smartphone,
    title: 'Responsive Web Design',
    description:
      'Mobile-first layouts that scale gracefully from 320px to ultrawide, using fluid type, container queries, and intrinsic sizing.',
  },
  {
    icon: Accessibility,
    title: 'Accessibility',
    description:
      'WCAG 2.1 AA built in: semantic HTML, ARIA where it counts, keyboard flows, focus management, and screen-reader testing.',
  },
];

const specializations: Skill[] = [
  {
    icon: Radio,
    title: 'Reactive Programming',
    description:
      'Event-driven, responsive UIs powered by streams and observables — UIs that stay in sync with the data, not the other way around.',
  },
  {
    icon: Plug,
    title: 'Third-Party API Integration',
    description:
      'REST, GraphQL, webhooks, and OAuth flows — wiring external services with retry logic, caching, and graceful degradation.',
  },
  {
    icon: BookOpen,
    title: 'Design Systems & Documentation',
    description:
      'Component libraries documented in Storybook and Styleguidist, with tokens, usage guidelines, and visual regression tests.',
  },
  {
    icon: LayoutDashboard,
    title: 'Data-Driven Dashboards',
    description:
      'Analytics interfaces with filterable views, drill-downs, and exportable reports for users who need answers fast.',
  },
  {
    icon: LineChart,
    title: 'Real-Time Data Visualization',
    description:
      'Live charts and streaming dashboards built on D3 and WebSockets — handling high-frequency updates without dropping frames.',
  },
];

export function SkillsPage() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-sand-100 via-sand-50 to-primary-50/30" />
        <div className="absolute top-20 right-20 w-96 h-96 bg-primary-200/20 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-20 w-72 h-72 bg-ocean-400/10 rounded-full blur-3xl" />

        <div className="container-page relative py-24 md:py-32">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger}
            className="max-w-3xl"
          >
            <motion.span
              variants={fadeInUp}
              className="inline-flex items-center gap-2 px-4 py-1.5 bg-primary-100 text-primary-700 text-body-sm font-medium rounded-full mb-6"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Senior Software Developer
            </motion.span>

            <motion.h1
              variants={fadeInUp}
              className="text-display-lg md:text-display-xl font-display text-ink-900 mb-6"
            >
              Building <span className="text-primary-600">sophisticated</span>,
              <br />
              dynamic web applications.
            </motion.h1>

            <motion.p
              variants={fadeInUp}
              className="text-body-xl text-ink-600 max-w-2xl"
            >
              A snapshot of the tools, frameworks, and disciplines I bring to
              modern frontend engineering — from reactive UIs and design systems
              to real-time dashboards.
            </motion.p>
          </motion.div>
        </div>
      </section>

      {/* Core Skills */}
      <section className="section bg-white">
        <div className="container-page">
          <div className="mb-12 max-w-2xl">
            <span className="text-body-sm text-primary-600 font-medium">
              Core Stack
            </span>
            <h2 className="text-display-sm md:text-display-md font-display text-ink-900 mt-1">
              The day-to-day toolkit
            </h2>
            <p className="text-body-lg text-ink-500 mt-4">
              The technologies I reach for first when shipping production
              frontends.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {coreSkills.map((skill, index) => (
              <motion.article
                key={skill.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: index * 0.06, duration: 0.4 }}
                className="group relative bg-sand-50 hover:bg-white border border-sand-200 hover:border-primary-200 rounded-card p-6 transition-all duration-300 hover:shadow-card-hover"
              >
                <div className="flex items-start justify-between mb-5">
                  <div className="w-12 h-12 bg-white group-hover:bg-primary-50 border border-sand-200 group-hover:border-primary-200 rounded-xl flex items-center justify-center transition-colors">
                    <skill.icon
                      className="w-6 h-6 text-ink-700 group-hover:text-primary-600 transition-colors"
                      aria-hidden="true"
                    />
                  </div>
                  {skill.meta && (
                    <span className="font-mono text-body-xs text-primary-600 bg-primary-50 px-2.5 py-1 rounded-full">
                      {skill.meta}
                    </span>
                  )}
                </div>
                <h3 className="text-lg font-medium text-ink-900 mb-2">
                  {skill.title}
                </h3>
                <p className="text-body-sm text-ink-600">{skill.description}</p>
              </motion.article>
            ))}
          </div>
        </div>
      </section>

      {/* Specializations */}
      <section className="section bg-sand-100/60">
        <div className="container-page">
          <div className="mb-12 max-w-2xl">
            <span className="text-body-sm text-primary-600 font-medium">
              Specializations
            </span>
            <h2 className="text-display-sm md:text-display-md font-display text-ink-900 mt-1">
              Where I add the most leverage
            </h2>
            <p className="text-body-lg text-ink-500 mt-4">
              The deeper expertise I bring to teams building complex,
              data-rich interfaces.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {specializations.map((skill, index) => (
              <motion.article
                key={skill.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: index * 0.07, duration: 0.4 }}
                className="group flex gap-5 bg-white border border-sand-200 rounded-card p-6 hover:border-primary-200 hover:shadow-card transition-all duration-300"
              >
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-primary-50 group-hover:bg-primary-100 rounded-xl flex items-center justify-center transition-colors">
                    <skill.icon
                      className="w-6 h-6 text-primary-600"
                      aria-hidden="true"
                    />
                  </div>
                </div>
                <div className="min-w-0">
                  <h3 className="text-lg font-medium text-ink-900 mb-2">
                    {skill.title}
                  </h3>
                  <p className="text-body-sm text-ink-600">
                    {skill.description}
                  </p>
                </div>
              </motion.article>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="section">
        <div className="container-page">
          <div className="relative bg-ink-900 rounded-2xl overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-primary-500/20 via-transparent to-ocean-500/10" />
            <div className="relative px-8 py-16 md:px-16 md:py-20 text-center max-w-2xl mx-auto">
              <h2 className="text-display-sm md:text-display-md font-display text-sand-50 mb-4">
                Have a project in mind?
              </h2>
              <p className="text-body-xl text-sand-300 mb-8">
                I'm always happy to talk shop, review architecture, or jump into
                interesting product work.
              </p>
              <Link
                to="/contact"
                className="btn bg-primary-500 text-white hover:bg-primary-600 inline-flex"
              >
                Get in touch
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
