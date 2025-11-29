/**
 * Authentication Controller
 * 
 * Handles user authentication with comprehensive security measures.
 */

import { Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import { randomUUID } from 'crypto';
import { prisma } from '../utils/prisma';
import { redis, checkRateLimit } from '../utils/redis';
import { generateToken, generateUrlSafeToken, secureCompare } from '../utils/encryption';
import { securityLogger, logAuditEvent } from '../utils/logger';
import { passwordConfig } from '../config/security.config';
import {
  generateAccessToken,
  generateRefreshToken,
  verifyRefreshToken,
  setAuthCookies,
  clearAuthCookies,
  blacklistSession,
} from '../middleware/auth.middleware';
import { AppError, asyncHandler } from '../middleware/error.middleware';

/**
 * Register new user
 * POST /api/v1/auth/register
 */
export const register = asyncHandler(async (req: Request, res: Response) => {
  const { email, password, firstName, lastName } = req.body;

  // Check if user already exists
  const existingUser = await prisma.user.findUnique({
    where: { email },
    select: { id: true },
  });

  if (existingUser) {
    // Use generic message to prevent email enumeration
    throw new AppError(
      'Unable to create account. Please try again or use a different email.',
      400,
      'REGISTRATION_FAILED'
    );
  }

  // Hash password with bcrypt
  const passwordHash = await bcrypt.hash(password, passwordConfig.bcryptRounds);

  // Generate email verification token
  const emailVerificationToken = generateUrlSafeToken(32);
  const emailVerificationExpiry = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours

  // Create user
  const user = await prisma.user.create({
    data: {
      email,
      passwordHash,
      firstName,
      lastName,
      emailVerificationToken,
      emailVerificationExpiry,
      role: 'CUSTOMER',
      isActive: true,
    },
    select: {
      id: true,
      email: true,
      firstName: true,
      lastName: true,
      createdAt: true,
    },
  });

  // Log audit event
  logAuditEvent('user.created', user.id, { email }, req.requestId);

  // TODO: Send verification email
  // await sendVerificationEmail(email, emailVerificationToken);

  res.status(201).json({
    success: true,
    message: 'Account created successfully. Please check your email to verify your account.',
    data: {
      user: {
        id: user.id,
        email: user.email,
        firstName: user.firstName,
        lastName: user.lastName,
      },
    },
  });
});

/**
 * User login
 * POST /api/v1/auth/login
 */
export const login = asyncHandler(async (req: Request, res: Response) => {
  const { email, password, rememberMe } = req.body;
  const clientIp = req.ip || 'unknown';

  // Check rate limit for this IP + email combination
  const rateLimitKey = `login:${clientIp}:${email}`;
  const rateLimit = await checkRateLimit(rateLimitKey, 5, 15 * 60); // 5 attempts per 15 minutes

  if (!rateLimit.allowed) {
    securityLogger.warn('Login rate limit exceeded', {
      email,
      ip: clientIp,
      requestId: req.requestId,
    });
    throw new AppError(
      'Too many login attempts. Please try again later.',
      429,
      'RATE_LIMITED'
    );
  }

  // Find user by email
  const user = await prisma.user.findUnique({
    where: { email },
    select: {
      id: true,
      email: true,
      passwordHash: true,
      role: true,
      firstName: true,
      lastName: true,
      isActive: true,
      lockedUntil: true,
      failedLoginAttempts: true,
      emailVerified: true,
    },
  });

  // Use constant-time comparison and generic error message to prevent enumeration
  const genericError = new AppError(
    'Invalid email or password',
    401,
    'INVALID_CREDENTIALS'
  );

  if (!user) {
    // Perform dummy hash comparison to prevent timing attacks
    await bcrypt.compare(password, '$2a$12$dummy.hash.for.timing.attack.prevention');
    throw genericError;
  }

  // Check if account is locked
  if (user.lockedUntil && user.lockedUntil > new Date()) {
    securityLogger.warn('Login attempt on locked account', {
      userId: user.id,
      ip: clientIp,
      lockedUntil: user.lockedUntil,
    });
    throw new AppError(
      'Account is temporarily locked. Please try again later.',
      403,
      'ACCOUNT_LOCKED'
    );
  }

  // Check if account is active
  if (!user.isActive) {
    throw new AppError('Account is deactivated', 403, 'ACCOUNT_DEACTIVATED');
  }

  // Verify password
  const isValidPassword = await bcrypt.compare(password, user.passwordHash);

  if (!isValidPassword) {
    // Increment failed attempts
    const failedAttempts = user.failedLoginAttempts + 1;
    const shouldLock = failedAttempts >= passwordConfig.maxLoginAttempts;

    await prisma.user.update({
      where: { id: user.id },
      data: {
        failedLoginAttempts: failedAttempts,
        lockedUntil: shouldLock
          ? new Date(Date.now() + passwordConfig.lockoutDuration)
          : null,
      },
    });

    securityLogger.warn('Failed login attempt', {
      userId: user.id,
      email,
      ip: clientIp,
      failedAttempts,
      accountLocked: shouldLock,
      requestId: req.requestId,
    });

    logAuditEvent('auth.failed_login', user.id, { ip: clientIp, failedAttempts }, req.requestId);

    throw genericError;
  }

  // Clear failed attempts on successful login
  if (user.failedLoginAttempts > 0) {
    await prisma.user.update({
      where: { id: user.id },
      data: {
        failedLoginAttempts: 0,
        lockedUntil: null,
      },
    });
  }

  // Generate session ID
  const sessionId = randomUUID();

  // Generate tokens
  const tokenPayload = {
    userId: user.id,
    email: user.email,
    role: user.role,
    sessionId,
  };

  const accessToken = generateAccessToken(tokenPayload);
  const refreshToken = generateRefreshToken(tokenPayload);

  // Store session in Redis
  await redis.setex(
    `session:${sessionId}`,
    rememberMe ? 30 * 24 * 60 * 60 : 24 * 60 * 60, // 30 days or 24 hours
    JSON.stringify({
      userId: user.id,
      createdAt: new Date().toISOString(),
      ip: clientIp,
      userAgent: req.headers['user-agent'],
    })
  );

  // Set cookies
  setAuthCookies(res, accessToken, refreshToken);

  // Update last login
  await prisma.user.update({
    where: { id: user.id },
    data: { lastLoginAt: new Date() },
  });

  // Log successful login
  logAuditEvent('auth.login', user.id, { ip: clientIp, sessionId }, req.requestId);

  res.json({
    success: true,
    message: 'Login successful',
    data: {
      user: {
        id: user.id,
        email: user.email,
        firstName: user.firstName,
        lastName: user.lastName,
        role: user.role,
        emailVerified: user.emailVerified,
      },
    },
  });
});

/**
 * Refresh access token
 * POST /api/v1/auth/refresh
 */
export const refreshToken = asyncHandler(async (req: Request, res: Response) => {
  const token = req.cookies?.refresh_token;

  if (!token) {
    throw new AppError('Refresh token not provided', 401, 'NO_REFRESH_TOKEN');
  }

  // Verify refresh token
  const payload = verifyRefreshToken(token);

  // Check if session still exists
  const session = await redis.get(`session:${payload.sessionId}`);
  if (!session) {
    clearAuthCookies(res);
    throw new AppError('Session expired', 401, 'SESSION_EXPIRED');
  }

  // Verify user still exists and is active
  const user = await prisma.user.findUnique({
    where: { id: payload.userId },
    select: { id: true, email: true, role: true, isActive: true },
  });

  if (!user || !user.isActive) {
    clearAuthCookies(res);
    throw new AppError('User not found or inactive', 401, 'USER_INVALID');
  }

  // Generate new tokens (token rotation)
  const newSessionId = randomUUID();
  const newPayload = {
    userId: user.id,
    email: user.email,
    role: user.role,
    sessionId: newSessionId,
  };

  const newAccessToken = generateAccessToken(newPayload);
  const newRefreshToken = generateRefreshToken(newPayload);

  // Invalidate old session and create new one (rotation)
  await redis.del(`session:${payload.sessionId}`);
  await redis.setex(
    `session:${newSessionId}`,
    7 * 24 * 60 * 60, // 7 days
    JSON.stringify({
      userId: user.id,
      createdAt: new Date().toISOString(),
      ip: req.ip,
      userAgent: req.headers['user-agent'],
    })
  );

  // Set new cookies
  setAuthCookies(res, newAccessToken, newRefreshToken);

  logAuditEvent('auth.token_refresh', user.id, { oldSessionId: payload.sessionId, newSessionId }, req.requestId);

  res.json({
    success: true,
    message: 'Token refreshed successfully',
  });
});

/**
 * Logout user
 * POST /api/v1/auth/logout
 */
export const logout = asyncHandler(async (req: Request, res: Response) => {
  const token = req.cookies?.refresh_token;

  if (token) {
    try {
      const payload = verifyRefreshToken(token);
      
      // Blacklist the session
      await blacklistSession(payload.sessionId);
      
      // Delete session from Redis
      await redis.del(`session:${payload.sessionId}`);

      logAuditEvent('auth.logout', payload.userId, { sessionId: payload.sessionId }, req.requestId);
    } catch {
      // Token invalid, but still clear cookies
    }
  }

  // Clear auth cookies
  clearAuthCookies(res);

  res.json({
    success: true,
    message: 'Logged out successfully',
  });
});

/**
 * Request password reset
 * POST /api/v1/auth/forgot-password
 */
export const forgotPassword = asyncHandler(async (req: Request, res: Response) => {
  const { email } = req.body;
  const clientIp = req.ip || 'unknown';

  // Rate limit password reset requests
  const rateLimitKey = `password-reset:${clientIp}`;
  const rateLimit = await checkRateLimit(rateLimitKey, 3, 60 * 60); // 3 per hour

  if (!rateLimit.allowed) {
    throw new AppError(
      'Too many password reset requests. Please try again later.',
      429,
      'RATE_LIMITED'
    );
  }

  // Always return success to prevent email enumeration
  const successMessage = 'If an account exists with this email, you will receive a password reset link.';

  const user = await prisma.user.findUnique({
    where: { email },
    select: { id: true, email: true },
  });

  if (!user) {
    // Return success even if user doesn't exist
    return res.json({ success: true, message: successMessage });
  }

  // Generate secure reset token
  const resetToken = generateUrlSafeToken(32);
  const resetTokenHash = await bcrypt.hash(resetToken, 10);
  const resetExpiry = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

  // Save hashed token (never store plain token)
  await prisma.user.update({
    where: { id: user.id },
    data: {
      passwordResetToken: resetTokenHash,
      passwordResetExpiry: resetExpiry,
    },
  });

  logAuditEvent('auth.password_reset_requested', user.id, { ip: clientIp }, req.requestId);

  // TODO: Send password reset email
  // await sendPasswordResetEmail(email, resetToken);

  // In development, include token in response (REMOVE IN PRODUCTION)
  const response: Record<string, unknown> = { success: true, message: successMessage };
  if (process.env.NODE_ENV === 'development') {
    response.devToken = resetToken;
  }

  res.json(response);
});

/**
 * Reset password with token
 * POST /api/v1/auth/reset-password
 */
export const resetPassword = asyncHandler(async (req: Request, res: Response) => {
  const { token, password } = req.body;

  // Find users with non-expired reset tokens
  const users = await prisma.user.findMany({
    where: {
      passwordResetExpiry: { gt: new Date() },
      passwordResetToken: { not: null },
    },
    select: {
      id: true,
      email: true,
      passwordResetToken: true,
    },
  });

  // Find matching user using secure comparison
  let matchedUser = null;
  for (const user of users) {
    const isMatch = await bcrypt.compare(token, user.passwordResetToken!);
    if (isMatch) {
      matchedUser = user;
      break;
    }
  }

  if (!matchedUser) {
    throw new AppError(
      'Invalid or expired reset token',
      400,
      'INVALID_RESET_TOKEN'
    );
  }

  // Hash new password
  const passwordHash = await bcrypt.hash(password, passwordConfig.bcryptRounds);

  // Update password and clear reset token
  await prisma.user.update({
    where: { id: matchedUser.id },
    data: {
      passwordHash,
      passwordResetToken: null,
      passwordResetExpiry: null,
      failedLoginAttempts: 0,
      lockedUntil: null,
    },
  });

  // Invalidate all existing sessions
  const sessions = await redis.keys(`session:*`);
  for (const sessionKey of sessions) {
    const session = await redis.get(sessionKey);
    if (session) {
      const sessionData = JSON.parse(session);
      if (sessionData.userId === matchedUser.id) {
        await redis.del(sessionKey);
      }
    }
  }

  logAuditEvent('auth.password_reset', matchedUser.id, {}, req.requestId);

  res.json({
    success: true,
    message: 'Password reset successfully. Please log in with your new password.',
  });
});

/**
 * Get current user profile
 * GET /api/v1/auth/me
 */
export const getCurrentUser = asyncHandler(async (req: Request, res: Response) => {
  const user = await prisma.user.findUnique({
    where: { id: req.user!.id },
    select: {
      id: true,
      email: true,
      firstName: true,
      lastName: true,
      role: true,
      phone: true,
      avatar: true,
      emailVerified: true,
      createdAt: true,
      lastLoginAt: true,
    },
  });

  if (!user) {
    throw new AppError('User not found', 404, 'USER_NOT_FOUND');
  }

  res.json({
    success: true,
    data: { user },
  });
});

export default {
  register,
  login,
  refreshToken,
  logout,
  forgotPassword,
  resetPassword,
  getCurrentUser,
};
