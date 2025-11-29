/**
 * Prisma Client Singleton
 * 
 * Ensures a single Prisma client instance across the application.
 * Includes query logging and error handling.
 */

import { PrismaClient } from '@prisma/client';
import { logger } from './logger';

// Extend PrismaClient with custom methods if needed
const prismaClientSingleton = () => {
  const client = new PrismaClient({
    log: [
      {
        emit: 'event',
        level: 'query',
      },
      {
        emit: 'event',
        level: 'error',
      },
      {
        emit: 'event',
        level: 'warn',
      },
    ],
  });

  // Log queries in development
  if (process.env.NODE_ENV === 'development') {
    client.$on('query', (e) => {
      logger.debug('Prisma Query', {
        query: e.query,
        params: e.params,
        duration: `${e.duration}ms`,
      });
    });
  }

  // Log errors
  client.$on('error', (e) => {
    logger.error('Prisma Error', {
      message: e.message,
      target: e.target,
    });
  });

  // Log warnings
  client.$on('warn', (e) => {
    logger.warn('Prisma Warning', {
      message: e.message,
    });
  });

  return client;
};

// Prevent multiple instances during hot reload in development
declare global {
  // eslint-disable-next-line no-var
  var prisma: PrismaClient | undefined;
}

export const prisma = globalThis.prisma ?? prismaClientSingleton();

if (process.env.NODE_ENV !== 'production') {
  globalThis.prisma = prisma;
}

/**
 * Connect to database with retry logic
 */
export async function connectDatabase(
  maxRetries: number = 5,
  retryDelay: number = 5000
): Promise<void> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await prisma.$connect();
      logger.info('Database connected successfully');
      return;
    } catch (error) {
      logger.error(`Database connection attempt ${attempt}/${maxRetries} failed`, {
        error: error instanceof Error ? error.message : 'Unknown error',
      });

      if (attempt === maxRetries) {
        throw new Error('Failed to connect to database after maximum retries');
      }

      await new Promise((resolve) => setTimeout(resolve, retryDelay));
    }
  }
}

/**
 * Disconnect from database gracefully
 */
export async function disconnectDatabase(): Promise<void> {
  await prisma.$disconnect();
  logger.info('Database disconnected');
}

export default prisma;
