/**
 * SecureShop API Server
 * 
 * Production-ready Express server with comprehensive security measures.
 */

import express, { Application, Request, Response, NextFunction } from 'express';
import helmet from 'helmet';
import cors from 'cors';
import compression from 'compression';
import cookieParser from 'cookie-parser';
import morgan from 'morgan';
import rateLimit from 'express-rate-limit';
import hpp from 'hpp';
import { randomUUID } from 'crypto';

import {
  validateEnvironment,
  corsConfig,
  helmetConfig,
  rateLimitConfig,
} from './config/security.config';
import { errorHandler, notFoundHandler } from './middleware/error.middleware';
import { requestLogger, securityLogger } from './utils/logger';

// Routes
import authRoutes from './routes/auth.routes';
import productRoutes from './routes/product.routes';
import cartRoutes from './routes/cart.routes';
import orderRoutes from './routes/order.routes';
import userRoutes from './routes/user.routes';

// Load environment variables
import dotenv from 'dotenv';
dotenv.config();

// Validate environment on startup
validateEnvironment();

const app: Application = express();

// =============================================================================
// SECURITY MIDDLEWARE
// =============================================================================

// Trust proxy (required for rate limiting behind reverse proxy)
app.set('trust proxy', 1);

// Security headers with Helmet
app.use(helmet(helmetConfig));

// CORS configuration
app.use(cors(corsConfig));

// Parse cookies (before CSRF protection)
app.use(cookieParser());

// Body parsing with size limits
app.use(express.json({ limit: '10kb' })); // Limit JSON body size
app.use(express.urlencoded({ extended: true, limit: '10kb' }));

// Prevent HTTP Parameter Pollution
app.use(hpp({
  whitelist: ['price', 'category', 'sort', 'page', 'limit'], // Allow these params
}));

// Compression (after body parsing)
app.use(compression());

// Request ID for tracing
app.use((req: Request, res: Response, next: NextFunction) => {
  const requestId = req.headers['x-request-id'] as string || randomUUID();
  req.requestId = requestId;
  res.setHeader('X-Request-ID', requestId);
  next();
});

// Request logging
if (process.env.NODE_ENV === 'development') {
  app.use(morgan('dev'));
} else {
  app.use(morgan('combined', {
    stream: { write: (message) => requestLogger.info(message.trim()) },
  }));
}

// General rate limiting
app.use('/api', rateLimit(rateLimitConfig.general));

// =============================================================================
// HEALTH CHECK (before auth)
// =============================================================================

app.get('/health', (_req: Request, res: Response) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

// =============================================================================
// API ROUTES
// =============================================================================

const API_VERSION = process.env.API_VERSION || 'v1';
const API_PREFIX = `/api/${API_VERSION}`;

// Authentication routes (with stricter rate limiting)
app.use(`${API_PREFIX}/auth`, rateLimit(rateLimitConfig.auth), authRoutes);

// Protected routes
app.use(`${API_PREFIX}/products`, productRoutes);
app.use(`${API_PREFIX}/cart`, cartRoutes);
app.use(`${API_PREFIX}/orders`, orderRoutes);
app.use(`${API_PREFIX}/users`, userRoutes);

// =============================================================================
// ERROR HANDLING
// =============================================================================

// 404 handler
app.use(notFoundHandler);

// Global error handler
app.use(errorHandler);

// =============================================================================
// GRACEFUL SHUTDOWN
// =============================================================================

const server = app.listen(process.env.PORT || 3001, () => {
  console.log(`
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🛒 SecureShop API Server                                   ║
║                                                              ║
║   Environment: ${(process.env.NODE_ENV || 'development').padEnd(41)}║
║   Port: ${(process.env.PORT || '3001').toString().padEnd(48)}║
║   API Version: ${API_VERSION.padEnd(42)}║
║                                                              ║
║   Security Features:                                         ║
║   ✓ Helmet security headers                                  ║
║   ✓ CORS protection                                          ║
║   ✓ Rate limiting                                            ║
║   ✓ HTTP Parameter Pollution prevention                      ║
║   ✓ Request size limits                                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
  `);
});

// Graceful shutdown handlers
const shutdown = async (signal: string) => {
  console.log(`\n${signal} received. Starting graceful shutdown...`);
  
  server.close(async () => {
    console.log('HTTP server closed.');
    
    // Close database connections
    try {
      const { prisma } = await import('./utils/prisma');
      await prisma.$disconnect();
      console.log('Database connections closed.');
    } catch (error) {
      console.error('Error closing database:', error);
    }
    
    // Close Redis connections
    try {
      const { redis } = await import('./utils/redis');
      await redis.quit();
      console.log('Redis connections closed.');
    } catch (error) {
      console.error('Error closing Redis:', error);
    }
    
    console.log('Graceful shutdown complete.');
    process.exit(0);
  });

  // Force shutdown after 30 seconds
  setTimeout(() => {
    console.error('Forced shutdown after timeout.');
    process.exit(1);
  }, 30000);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// Unhandled rejection handler
process.on('unhandledRejection', (reason: Error) => {
  securityLogger.error('Unhandled Rejection', { error: reason.message, stack: reason.stack });
  throw reason;
});

// Uncaught exception handler
process.on('uncaughtException', (error: Error) => {
  securityLogger.error('Uncaught Exception', { error: error.message, stack: error.stack });
  shutdown('UNCAUGHT_EXCEPTION');
});

// Type augmentation for request ID
declare global {
  namespace Express {
    interface Request {
      requestId?: string;
      user?: {
        id: string;
        email: string;
        role: string;
      };
    }
  }
}

export default app;
