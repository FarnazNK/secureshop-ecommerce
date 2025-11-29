/**
 * Authentication Middleware
 * 
 * Handles JWT verification, token refresh, and session management.
 * Implements secure cookie-based authentication with HTTP-only tokens.
 */

import { Request, Response, NextFunction } from 'express';
import jwt, { JsonWebTokenError, TokenExpiredError } from 'jsonwebtoken';
import { jwtConfig, cookieConfig } from '../config/security.config';
import { prisma } from '../utils/prisma';
import { redis } from '../utils/redis';
import { securityLogger } from '../utils/logger';
import { AppError } from './error.middleware';

// Token payload interface
interface TokenPayload {
  userId: string;
  email: string;
  role: string;
  sessionId: string;
  iat: number;
  exp: number;
}

/**
 * Generate access token
 */
export function generateAccessToken(payload: Omit<TokenPayload, 'iat' | 'exp'>): string {
  return jwt.sign(payload, jwtConfig.accessToken.secret, {
    expiresIn: jwtConfig.accessToken.expiresIn,
    issuer: jwtConfig.issuer,
    audience: jwtConfig.audience,
  });
}

/**
 * Generate refresh token
 */
export function generateRefreshToken(payload: Omit<TokenPayload, 'iat' | 'exp'>): string {
  return jwt.sign(payload, jwtConfig.refreshToken.secret, {
    expiresIn: jwtConfig.refreshToken.expiresIn,
    issuer: jwtConfig.issuer,
    audience: jwtConfig.audience,
  });
}

/**
 * Verify access token
 */
export function verifyAccessToken(token: string): TokenPayload {
  return jwt.verify(token, jwtConfig.accessToken.secret, {
    issuer: jwtConfig.issuer,
    audience: jwtConfig.audience,
  }) as TokenPayload;
}

/**
 * Verify refresh token
 */
export function verifyRefreshToken(token: string): TokenPayload {
  return jwt.verify(token, jwtConfig.refreshToken.secret, {
    issuer: jwtConfig.issuer,
    audience: jwtConfig.audience,
  }) as TokenPayload;
}

/**
 * Set authentication cookies
 */
export function setAuthCookies(
  res: Response,
  accessToken: string,
  refreshToken: string
): void {
  res.cookie('access_token', accessToken, cookieConfig.accessToken);
  res.cookie('refresh_token', refreshToken, cookieConfig.refreshToken);
}

/**
 * Clear authentication cookies
 */
export function clearAuthCookies(res: Response): void {
  res.clearCookie('access_token', { path: '/' });
  res.clearCookie('refresh_token', { path: '/api/v1/auth/refresh' });
}

/**
 * Check if session is blacklisted (logged out)
 */
async function isSessionBlacklisted(sessionId: string): Promise<boolean> {
  const blacklisted = await redis.get(`blacklist:session:${sessionId}`);
  return blacklisted !== null;
}

/**
 * Blacklist a session (logout)
 */
export async function blacklistSession(
  sessionId: string,
  expiresIn: number = 7 * 24 * 60 * 60 // 7 days
): Promise<void> {
  await redis.setex(`blacklist:session:${sessionId}`, expiresIn, 'true');
}

/**
 * Authentication middleware
 * 
 * Verifies JWT from HTTP-only cookie and attaches user to request.
 */
export async function authenticate(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    // Get token from cookie (preferred) or Authorization header (fallback for APIs)
    let token = req.cookies?.access_token;
    
    if (!token && req.headers.authorization?.startsWith('Bearer ')) {
      token = req.headers.authorization.substring(7);
    }

    if (!token) {
      throw new AppError('Authentication required', 401, 'UNAUTHORIZED');
    }

    // Verify token
    const payload = verifyAccessToken(token);

    // Check if session is blacklisted
    if (await isSessionBlacklisted(payload.sessionId)) {
      clearAuthCookies(res);
      throw new AppError('Session expired. Please log in again.', 401, 'SESSION_EXPIRED');
    }

    // Verify user still exists and is active
    const user = await prisma.user.findUnique({
      where: { id: payload.userId },
      select: {
        id: true,
        email: true,
        role: true,
        isActive: true,
        lockedUntil: true,
      },
    });

    if (!user) {
      throw new AppError('User not found', 401, 'USER_NOT_FOUND');
    }

    if (!user.isActive) {
      throw new AppError('Account is deactivated', 403, 'ACCOUNT_DEACTIVATED');
    }

    if (user.lockedUntil && user.lockedUntil > new Date()) {
      throw new AppError('Account is temporarily locked', 403, 'ACCOUNT_LOCKED');
    }

    // Attach user to request
    req.user = {
      id: user.id,
      email: user.email,
      role: user.role,
    };

    // Log successful authentication (for audit)
    securityLogger.debug('Authentication successful', {
      userId: user.id,
      requestId: req.requestId,
      path: req.path,
    });

    next();
  } catch (error) {
    if (error instanceof TokenExpiredError) {
      clearAuthCookies(res);
      return next(new AppError('Token expired. Please log in again.', 401, 'TOKEN_EXPIRED'));
    }

    if (error instanceof JsonWebTokenError) {
      clearAuthCookies(res);
      securityLogger.warn('Invalid token attempt', {
        requestId: req.requestId,
        ip: req.ip,
        error: error.message,
      });
      return next(new AppError('Invalid token', 401, 'INVALID_TOKEN'));
    }

    next(error);
  }
}

/**
 * Optional authentication middleware
 * 
 * Attaches user if token is present, but doesn't require authentication.
 */
export async function optionalAuth(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const token = req.cookies?.access_token;
    
    if (!token) {
      return next();
    }

    const payload = verifyAccessToken(token);

    if (await isSessionBlacklisted(payload.sessionId)) {
      clearAuthCookies(res);
      return next();
    }

    const user = await prisma.user.findUnique({
      where: { id: payload.userId },
      select: { id: true, email: true, role: true, isActive: true },
    });

    if (user?.isActive) {
      req.user = {
        id: user.id,
        email: user.email,
        role: user.role,
      };
    }

    next();
  } catch {
    // Silently fail for optional auth
    next();
  }
}

/**
 * Role-based authorization middleware
 */
export function authorize(...allowedRoles: string[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      return next(new AppError('Authentication required', 401, 'UNAUTHORIZED'));
    }

    if (!allowedRoles.includes(req.user.role)) {
      securityLogger.warn('Authorization failed', {
        userId: req.user.id,
        requiredRoles: allowedRoles,
        userRole: req.user.role,
        path: req.path,
        requestId: req.requestId,
      });
      return next(new AppError('Insufficient permissions', 403, 'FORBIDDEN'));
    }

    next();
  };
}

/**
 * CSRF protection middleware
 * 
 * Validates CSRF token for state-changing requests.
 */
export async function csrfProtection(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  // Skip for safe methods
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
    return next();
  }

  const csrfToken = req.headers['x-csrf-token'] as string;
  const sessionId = req.cookies?.session_id;

  if (!csrfToken || !sessionId) {
    return next(new AppError('CSRF token missing', 403, 'CSRF_ERROR'));
  }

  // Verify CSRF token matches session
  const storedToken = await redis.get(`csrf:${sessionId}`);
  
  if (!storedToken || storedToken !== csrfToken) {
    securityLogger.warn('CSRF validation failed', {
      requestId: req.requestId,
      ip: req.ip,
      path: req.path,
    });
    return next(new AppError('Invalid CSRF token', 403, 'CSRF_ERROR'));
  }

  next();
}

export default {
  authenticate,
  optionalAuth,
  authorize,
  csrfProtection,
  generateAccessToken,
  generateRefreshToken,
  verifyAccessToken,
  verifyRefreshToken,
  setAuthCookies,
  clearAuthCookies,
  blacklistSession,
};
