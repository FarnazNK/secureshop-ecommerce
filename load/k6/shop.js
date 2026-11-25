// SecureShop load test (k6). Runs against a LOCAL server only; see load/README.md.
//
//   browse     constant 150 requests/s of product listing and product pages
//   checkout   up to 40 shoppers adding to cart and placing orders with an
//              Idempotency-Key; 1 in 5 immediately retries with the same key
//   flash_sale 200 shoppers race for a product with only 50 units
//
// Pass/fail (thresholds) are the production promises, not just speed:
//   exactly `limitedStock` flash-sale orders succeed and stock ends at 0,
//   every idempotent retry returns the original order, and fewer than 1% of
//   requests fail unexpectedly (409 "sold out" is an expected answer).

import exec from 'k6/execution';
import http from 'k6/http';
import { check } from 'k6';
import { Counter, Gauge, Trend } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:3001';
const API = `${BASE}/api/v1`;
const seed = JSON.parse(open(__ENV.SEED_FILE || '../results/seed.json'));

const BROWSE_RPS = Number(__ENV.BROWSE_RPS || 150);
const CHECKOUT_VUS = Number(__ENV.CHECKOUT_VUS || 40);
const FLASH_VUS = Number(__ENV.FLASH_VUS || 200);
const BROWSE_MAX_VUS = 60;
const TOTAL_USERS = BROWSE_MAX_VUS + CHECKOUT_VUS + FLASH_VUS;

const limitedSold = new Counter('limited_sold');
const limitedSoldOut = new Counter('limited_sold_out');
const limitedStockAfter = new Gauge('limited_stock_after');
const idempotencyMismatch = new Counter('idempotency_mismatch');
const idempotentReplays = new Counter('idempotent_replays');
const orderLatency = new Trend('order_create_ms', true);

http.setResponseCallback(http.expectedStatuses({ min: 200, max: 299 }, 409));

export const options = {
  setupTimeout: '300s',
  scenarios: {
    browse: {
      executor: 'constant-arrival-rate',
      exec: 'browse',
      rate: BROWSE_RPS,
      timeUnit: '1s',
      duration: '150s',
      preAllocatedVUs: 20,
      maxVUs: BROWSE_MAX_VUS,
    },
    checkout: {
      executor: 'ramping-vus',
      exec: 'checkout',
      startVUs: 0,
      stages: [
        { duration: '30s', target: CHECKOUT_VUS },
        { duration: '90s', target: CHECKOUT_VUS },
        { duration: '30s', target: 0 },
      ],
    },
    flash_sale: {
      executor: 'per-vu-iterations',
      exec: 'flashSale',
      vus: FLASH_VUS,
      iterations: 1,
      startTime: '60s',
      maxDuration: '60s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{scenario:browse}': ['p(95)<500'],
    order_create_ms: ['p(95)<1500'],
    limited_sold: [`count==${seed.limitedStock}`],
    limited_stock_after: ['value==0'],
    idempotency_mismatch: ['count==0'],
    checks: ['rate>0.99'],
  },
};

const json = (token) => ({
  headers: {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  },
});

export function setup() {
  const run = Date.now().toString(36);
  const users = [];
  const batchSize = 20;
  for (let start = 0; start < TOTAL_USERS; start += batchSize) {
    const requests = [];
    for (let i = start; i < Math.min(start + batchSize, TOTAL_USERS); i++) {
      requests.push([
        'POST',
        `${API}/auth/register`,
        JSON.stringify({
          email: `load-${run}-${i}@example.com`,
          password: 'LoadTest-Passw0rd!x',
          first_name: 'Load',
          last_name: `User${i}`,
        }),
        json(),
      ]);
    }
    for (const res of http.batch(requests)) {
      if (res.status !== 201) throw new Error(`register failed: ${res.status} ${res.body}`);
      users.push(res.json('access_token'));
    }
  }
  return { users };
}

function tokenFor(data) {
  return data.users[(exec.vu.idInTest - 1) % data.users.length];
}

export function browse() {
  const page = 1 + Math.floor(Math.random() * 3);
  const list = http.get(`${API}/products?page=${page}&limit=20`, { tags: { name: 'GET /products' } });
  check(list, { 'list 200': (r) => r.status === 200 });
  const id = seed.everyday[Math.floor(Math.random() * seed.everyday.length)];
  const item = http.get(`${API}/products/${id}`, { tags: { name: 'GET /products/:id' } });
  check(item, { 'product 200': (r) => r.status === 200 });
}

function placeOrder(token, key) {
  const params = json(token);
  params.headers['Idempotency-Key'] = key;
  params.tags = { name: 'POST /orders' };
  const res = http.post(`${API}/orders`, '{}', params);
  orderLatency.add(res.timings.duration);
  return res;
}

export function checkout(data) {
  const token = tokenFor(data);
  const product = seed.everyday[Math.floor(Math.random() * seed.everyday.length)];
  const added = http.post(
    `${API}/cart/items`,
    JSON.stringify({ product_id: product, quantity: 1 }),
    Object.assign(json(token), { tags: { name: 'POST /cart/items' } }),
  );
  check(added, { 'cart 201': (r) => r.status === 201 });

  const key = `k6-${exec.vu.idInTest}-${exec.vu.iterationInScenario}-${Date.now()}`;
  const order = placeOrder(token, key);
  check(order, { 'order 201': (r) => r.status === 201 });

  if (order.status === 201 && Math.random() < 0.2) {
    // Same key again, as a client would after a timeout: must be the same order.
    const retry = placeOrder(token, key);
    idempotentReplays.add(1);
    const same = retry.status === 201 && retry.json('order.id') === order.json('order.id');
    if (!same) idempotencyMismatch.add(1);
    check(retry, { 'retry returns the same order': () => same });
  }
}

export function flashSale(data) {
  const token = tokenFor(data);
  const added = http.post(
    `${API}/cart/items`,
    JSON.stringify({ product_id: seed.limited, quantity: 1 }),
    Object.assign(json(token), { tags: { name: 'POST /cart/items (flash)' } }),
  );
  if (added.status === 409) {
    limitedSoldOut.add(1);
    return;
  }
  check(added, { 'flash cart 201': (r) => r.status === 201 });
  const order = placeOrder(token, `flash-${exec.vu.idInTest}`);
  if (order.status === 201) limitedSold.add(1);
  else if (order.status === 409) limitedSoldOut.add(1);
  check(order, { 'flash order 201 or sold out 409': (r) => r.status === 201 || r.status === 409 });
}

export function teardown() {
  const res = http.get(`${API}/products/${seed.limited}`);
  limitedStockAfter.add(res.json('stock_quantity'));
}
