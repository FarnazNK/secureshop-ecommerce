/**
 * Logging Utility
 * 
 * Secure logging with Winston. Sanitizes sensitive data before logging.
 */

import winston from 'winston';
import path from 'path';

// Sensitive fields that should never be logged
const SENSITIVE_FIELDS = [
  'password',
  'confirmPassword',
  'currentPassword',
  'newPassword',
  'token',
  'accessToken',
  'refreshToken',
  'apiKey',
  'secret',
  'creditCard',
  'cardNumber',
  'cvv',
  'ssn',
  'authorization',
];

/**
 * Recursively redact sensitive fields from objects
 */
function redactSensitive(obj: unknown): unknown {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (typeof obj === 'string') {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(redactSensitive);
  }

  if (typeof obj === 'object') {
    const redacted: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      if (SENSITIVE_FIELDS.some((field) => 
        key.toLowerCase().includes(field.toLowerCase())
      )) {
        redacted[key] = '[REDACTED]';
      } else if (typeof value === 'object') {
        redacted[key] = redactSensitive(value);
      } else {
        redacted[key] = value;
      }
    }
    return redacted;
  }

  return obj;
}

// Custom format that redacts sensitive data
const redactFormat = winston.format((info) => {
  if (info.meta) {
    info.meta = redactSensitive(info.meta);
  }
  return info;
});

// Log format
const logFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
  winston.format.errors({ stack: true }),
  redactFormat(),
  winston.format.json()
);

// Console format for development
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: 'HH:mm:ss' }),
  winston.format.colorize(),
  winston.format.printf(({ level, message, timestamp, ...meta }) => {
    const metaStr = Object.keys(meta).length ? JSON.stringify(redactSensitive(meta), null, 2) : '';
    return `${timestamp} ${level}: ${message} ${metaStr}`;
  })
);

// Determine log level
const logLevel = process.env.LOG_LEVEL || (process.env.NODE_ENV === 'production' ? 'info' : 'debug');

// Create transports
const transports: winston.transport[] = [];

// Console transport (always enabled)
transports.push(
  new winston.transports.Console({
    format: process.env.NODE_ENV === 'production' ? logFormat : consoleFormat,
  })
);

// File transports (production only)
if (process.env.NODE_ENV === 'production') {
  const logDir = process.env.LOG_DIR || 'logs';

  // Combined log
  transports.push(
    new winston.transports.File({
      filename: path.join(logDir, 'combined.log'),
      format: logFormat,
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 5,
      tailable: true,
    })
  );

  // Error log
  transports.push(
    new winston.transports.File({
      filename: path.join(logDir, 'error.log'),
      level: 'error',
      format: logFormat,
      maxsize: 10 * 1024 * 1024,
      maxFiles: 5,
      tailable: true,
    })
  );
}

// Main application logger
export const logger = winston.createLogger({
  level: logLevel,
  defaultMeta: { service: 'secureshop-api' },
  transports,
});

// Request logger (HTTP requests)
export const requestLogger = winston.createLogger({
  level: 'info',
  defaultMeta: { service: 'secureshop-api', type: 'request' },
  transports,
});

// Security logger (auth events, suspicious activity)
export const securityLogger = winston.createLogger({
  level: 'info',
  defaultMeta: { service: 'secureshop-api', type: 'security' },
  transports: [
    ...transports,
    // Additional security log file in production
    ...(process.env.NODE_ENV === 'production'
      ? [
          new winston.transports.File({
            filename: path.join(process.env.LOG_DIR || 'logs', 'security.log'),
            format: logFormat,
            maxsize: 10 * 1024 * 1024,
            maxFiles: 10,
            tailable: true,
          }),
        ]
      : []),
  ],
});

// Audit logger (user actions, data changes)
export const auditLogger = winston.createLogger({
  level: 'info',
  defaultMeta: { service: 'secureshop-api', type: 'audit' },
  transports: [
    ...transports,
    // Additional audit log file in production
    ...(process.env.NODE_ENV === 'production'
      ? [
          new winston.transports.File({
            filename: path.join(process.env.LOG_DIR || 'logs', 'audit.log'),
            format: logFormat,
            maxsize: 10 * 1024 * 1024,
            maxFiles: 30,
            tailable: true,
          }),
        ]
      : []),
  ],
});

/**
 * Log audit event
 */
export function logAuditEvent(
  event: string,
  userId: string | null,
  data: Record<string, unknown>,
  requestId?: string
): void {
  auditLogger.info(event, {
    userId,
    requestId,
    timestamp: new Date().toISOString(),
    ...redactSensitive(data),
  });
}

/**
 * Log security event
 */
export function logSecurityEvent(
  event: string,
  level: 'info' | 'warn' | 'error',
  data: Record<string, unknown>
): void {
  securityLogger[level](event, {
    timestamp: new Date().toISOString(),
    ...redactSensitive(data),
  });
}

export default {
  logger,
  requestLogger,
  securityLogger,
  auditLogger,
  logAuditEvent,
  logSecurityEvent,
};
