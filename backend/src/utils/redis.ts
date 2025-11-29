/**
 * Redis Client
 * 
 * Redis connection for caching, sessions, and rate limiting.
 */

import Redis from 'ioredis';
import { logger } from './logger';

// Create Redis client
const createRedisClient = () => {
  const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';

  const client = new Redis(redisUrl, {
    maxRetriesPerRequest: 3,
    retryStrategy(times) {
      const delay = Math.min(times * 50, 2000);
      logger.warn(`Redis connection retry attempt ${times}`, { delay });
      return delay;
    },
    reconnectOnError(err) {
      const targetErrors = ['READONLY', 'ECONNRESET', 'ETIMEDOUT'];
      if (targetErrors.some((e) => err.message.includes(e))) {
        return true;
      }
      return false;
    },
  });

  client.on('connect', () => {
    logger.info('Redis connected');
  });

  client.on('ready', () => {
    logger.info('Redis ready');
  });

  client.on('error', (err) => {
    logger.error('Redis error', { error: err.message });
  });

  client.on('close', () => {
    logger.warn('Redis connection closed');
  });

  client.on('reconnecting', () => {
    logger.info('Redis reconnecting');
  });

  return client;
};

// Singleton pattern for Redis client
declare global {
  // eslint-disable-next-line no-var
  var redis: Redis | undefined;
}

export const redis = globalThis.redis ?? createRedisClient();

if (process.env.NODE_ENV !== 'production') {
  globalThis.redis = redis;
}

// =============================================================================
// CACHE UTILITIES
// =============================================================================

const DEFAULT_CACHE_TTL = 3600; // 1 hour

/**
 * Get cached value with automatic JSON parsing
 */
export async function cacheGet<T>(key: string): Promise<T | null> {
  const value = await redis.get(key);
  if (!value) return null;

  try {
    return JSON.parse(value) as T;
  } catch {
    return value as unknown as T;
  }
}

/**
 * Set cache value with automatic JSON serialization
 */
export async function cacheSet(
  key: string,
  value: unknown,
  ttl: number = DEFAULT_CACHE_TTL
): Promise<void> {
  const serialized = typeof value === 'string' ? value : JSON.stringify(value);
  await redis.setex(key, ttl, serialized);
}

/**
 * Delete cache key
 */
export async function cacheDelete(key: string): Promise<void> {
  await redis.del(key);
}

/**
 * Delete multiple cache keys by pattern
 */
export async function cacheDeletePattern(pattern: string): Promise<void> {
  const keys = await redis.keys(pattern);
  if (keys.length > 0) {
    await redis.del(...keys);
  }
}

/**
 * Cache wrapper for expensive operations
 */
export async function withCache<T>(
  key: string,
  fn: () => Promise<T>,
  ttl: number = DEFAULT_CACHE_TTL
): Promise<T> {
  // Try to get from cache
  const cached = await cacheGet<T>(key);
  if (cached !== null) {
    return cached;
  }

  // Execute function and cache result
  const result = await fn();
  await cacheSet(key, result, ttl);
  return result;
}

// =============================================================================
// RATE LIMITING UTILITIES
// =============================================================================

/**
 * Check and increment rate limit counter
 * Returns remaining attempts
 */
export async function checkRateLimit(
  key: string,
  maxAttempts: number,
  windowSeconds: number
): Promise<{ allowed: boolean; remaining: number; resetAt: Date }> {
  const multi = redis.multi();
  const fullKey = `ratelimit:${key}`;

  multi.incr(fullKey);
  multi.ttl(fullKey);

  const results = await multi.exec();
  const count = results?.[0]?.[1] as number;
  const ttl = results?.[1]?.[1] as number;

  // Set expiry on first request
  if (ttl === -1) {
    await redis.expire(fullKey, windowSeconds);
  }

  const remaining = Math.max(0, maxAttempts - count);
  const resetAt = new Date(Date.now() + (ttl > 0 ? ttl : windowSeconds) * 1000);

  return {
    allowed: count <= maxAttempts,
    remaining,
    resetAt,
  };
}

// =============================================================================
// SESSION UTILITIES
// =============================================================================

/**
 * Store session data
 */
export async function setSession(
  sessionId: string,
  data: Record<string, unknown>,
  ttl: number = 24 * 60 * 60 // 24 hours
): Promise<void> {
  await redis.setex(`session:${sessionId}`, ttl, JSON.stringify(data));
}

/**
 * Get session data
 */
export async function getSession<T>(sessionId: string): Promise<T | null> {
  const data = await redis.get(`session:${sessionId}`);
  if (!data) return null;
  return JSON.parse(data) as T;
}

/**
 * Delete session
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await redis.del(`session:${sessionId}`);
}

/**
 * Extend session TTL
 */
export async function extendSession(
  sessionId: string,
  ttl: number = 24 * 60 * 60
): Promise<void> {
  await redis.expire(`session:${sessionId}`, ttl);
}

export default {
  redis,
  cacheGet,
  cacheSet,
  cacheDelete,
  cacheDeletePattern,
  withCache,
  checkRateLimit,
  setSession,
  getSession,
  deleteSession,
  extendSession,
};
