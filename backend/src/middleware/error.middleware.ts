/**
 * Error Handling Middleware
 * 
 * Centralized error handling with security-conscious error messages.
 * Prevents information leakage in production.
 */

import { Request, Response, NextFunction } from 'express';
import { securityLogger, requestLogger } from '../utils/logger';
import { ZodError } from 'zod';
import { Prisma } from '@prisma/client';

// Custom application error class
export class AppError extends Error {
  public readonly statusCode: number;
  public readonly code: string;
  public readonly isOperational: boolean;
  public readonly details?: Record<string, unknown>;

  constructor(
    message: string,
    statusCode: number = 500,
    code: string = 'INTERNAL_ERROR',
    isOperational: boolean = true,
    details?: Record<string, unknown>
  ) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.isOperational = isOperational;
    this.details = details;

    Error.captureStackTrace(this, this.constructor);
  }
}

// Common error types
export const Errors = {
  BadRequest: (message: string, details?: Record<string, unknown>) =>
    new AppError(message, 400, 'BAD_REQUEST', true, details),
  
  Unauthorized: (message: string = 'Unauthorized') =>
    new AppError(message, 401, 'UNAUTHORIZED', true),
  
  Forbidden: (message: string = 'Access denied') =>
    new AppError(message, 403, 'FORBIDDEN', true),
  
  NotFound: (resource: string = 'Resource') =>
    new AppError(`${resource} not found`, 404, 'NOT_FOUND', true),
  
  Conflict: (message: string) =>
    new AppError(message, 409, 'CONFLICT', true),
  
  ValidationError: (details: Record<string, unknown>) =>
    new AppError('Validation failed', 422, 'VALIDATION_ERROR', true, details),
  
  RateLimited: () =>
    new AppError('Too many requests', 429, 'RATE_LIMITED', true),
  
  Internal: (message: string = 'Internal server error') =>
    new AppError(message, 500, 'INTERNAL_ERROR', false),
};

/**
 * Format Zod validation errors
 */
function formatZodError(error: ZodError): Record<string, string[]> {
  const formatted: Record<string, string[]> = {};
  
  for (const issue of error.issues) {
    const path = issue.path.join('.');
    if (!formatted[path]) {
      formatted[path] = [];
    }
    formatted[path].push(issue.message);
  }
  
  return formatted;
}

/**
 * Handle Prisma errors
 */
function handlePrismaError(error: Prisma.PrismaClientKnownRequestError): AppError {
  switch (error.code) {
    case 'P2002':
      // Unique constraint violation
      const field = (error.meta?.target as string[])?.join(', ') || 'field';
      return new AppError(
        `A record with this ${field} already exists`,
        409,
        'DUPLICATE_ENTRY',
        true
      );
    
    case 'P2025':
      // Record not found
      return new AppError('Record not found', 404, 'NOT_FOUND', true);
    
    case 'P2003':
      // Foreign key constraint
      return new AppError('Related record not found', 400, 'INVALID_REFERENCE', true);
    
    case 'P2014':
      // Invalid ID
      return new AppError('Invalid identifier', 400, 'INVALID_ID', true);
    
    default:
      securityLogger.error('Unhandled Prisma error', {
        code: error.code,
        meta: error.meta,
      });
      return new AppError('Database error', 500, 'DATABASE_ERROR', false);
  }
}

/**
 * 404 Not Found handler
 */
export function notFoundHandler(
  req: Request,
  _res: Response,
  next: NextFunction
): void {
  const error = new AppError(
    `Route ${req.method} ${req.path} not found`,
    404,
    'ROUTE_NOT_FOUND',
    true
  );
  next(error);
}

/**
 * Global error handler
 * 
 * SECURITY: Sanitizes error responses to prevent information leakage.
 */
export function errorHandler(
  error: Error,
  req: Request,
  res: Response,
  _next: NextFunction
): void {
  // Default error values
  let statusCode = 500;
  let code = 'INTERNAL_ERROR';
  let message = 'An unexpected error occurred';
  let details: Record<string, unknown> | undefined;
  let isOperational = false;

  // Handle known error types
  if (error instanceof AppError) {
    statusCode = error.statusCode;
    code = error.code;
    message = error.message;
    details = error.details;
    isOperational = error.isOperational;
  } else if (error instanceof ZodError) {
    statusCode = 422;
    code = 'VALIDATION_ERROR';
    message = 'Validation failed';
    details = { errors: formatZodError(error) };
    isOperational = true;
  } else if (error instanceof Prisma.PrismaClientKnownRequestError) {
    const prismaError = handlePrismaError(error);
    statusCode = prismaError.statusCode;
    code = prismaError.code;
    message = prismaError.message;
    isOperational = prismaError.isOperational;
  } else if (error instanceof Prisma.PrismaClientValidationError) {
    statusCode = 400;
    code = 'VALIDATION_ERROR';
    message = 'Invalid data provided';
    isOperational = true;
  } else if (error.name === 'SyntaxError' && 'body' in error) {
    statusCode = 400;
    code = 'INVALID_JSON';
    message = 'Invalid JSON in request body';
    isOperational = true;
  }

  // Log error
  const logData = {
    requestId: req.requestId,
    method: req.method,
    path: req.path,
    statusCode,
    code,
    message: error.message,
    userId: req.user?.id,
    ip: req.ip,
    userAgent: req.headers['user-agent'],
  };

  if (isOperational) {
    requestLogger.warn('Operational error', logData);
  } else {
    // Log full stack for non-operational errors
    securityLogger.error('Non-operational error', {
      ...logData,
      stack: error.stack,
    });
  }

  // SECURITY: In production, hide internal error details
  if (process.env.NODE_ENV === 'production' && !isOperational) {
    message = 'An unexpected error occurred';
    details = undefined;
  }

  // Send error response
  const response: Record<string, unknown> = {
    success: false,
    error: {
      code,
      message,
      ...(details && { details }),
      ...(process.env.NODE_ENV === 'development' && {
        stack: error.stack,
      }),
    },
    requestId: req.requestId,
    timestamp: new Date().toISOString(),
  };

  res.status(statusCode).json(response);
}

/**
 * Async handler wrapper
 * 
 * Wraps async route handlers to catch errors automatically.
 */
export function asyncHandler(
  fn: (req: Request, res: Response, next: NextFunction) => Promise<unknown>
) {
  return (req: Request, res: Response, next: NextFunction): void => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}

export default {
  AppError,
  Errors,
  notFoundHandler,
  errorHandler,
  asyncHandler,
};
