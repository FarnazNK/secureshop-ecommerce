/**
 * Input Validation Schemas
 * 
 * Comprehensive validation using Zod for type-safe input validation.
 * All user input MUST be validated before processing.
 */

import { z } from 'zod';
import sanitizeHtml from 'sanitize-html';
import { passwordConfig } from '../config/security.config';

// =============================================================================
// SANITIZATION HELPERS
// =============================================================================

/**
 * Sanitize string input to prevent XSS
 */
const sanitizedString = (minLength: number = 1, maxLength: number = 255) =>
  z
    .string()
    .min(minLength)
    .max(maxLength)
    .transform((val) =>
      sanitizeHtml(val.trim(), {
        allowedTags: [],
        allowedAttributes: {},
      })
    );

/**
 * Sanitize HTML content (for rich text fields)
 */
const sanitizedHtml = (maxLength: number = 10000) =>
  z
    .string()
    .max(maxLength)
    .transform((val) =>
      sanitizeHtml(val, {
        allowedTags: ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3'],
        allowedAttributes: {},
      })
    );

// =============================================================================
// COMMON SCHEMAS
// =============================================================================

export const idSchema = z.string().uuid('Invalid ID format');

export const emailSchema = z
  .string()
  .email('Invalid email format')
  .max(255)
  .transform((val) => val.toLowerCase().trim());

export const passwordSchema = z
  .string()
  .min(passwordConfig.minLength, `Password must be at least ${passwordConfig.minLength} characters`)
  .max(128, 'Password too long')
  .refine(
    (val) => !passwordConfig.requireUppercase || /[A-Z]/.test(val),
    'Password must contain at least one uppercase letter'
  )
  .refine(
    (val) => !passwordConfig.requireLowercase || /[a-z]/.test(val),
    'Password must contain at least one lowercase letter'
  )
  .refine(
    (val) => !passwordConfig.requireNumbers || /\d/.test(val),
    'Password must contain at least one number'
  )
  .refine(
    (val) => !passwordConfig.requireSpecialChars || /[!@#$%^&*(),.?":{}|<>]/.test(val),
    'Password must contain at least one special character'
  );

export const paginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  sortBy: z.string().max(50).optional(),
  sortOrder: z.enum(['asc', 'desc']).default('desc'),
});

// =============================================================================
// AUTH SCHEMAS
// =============================================================================

export const registerSchema = z.object({
  body: z.object({
    email: emailSchema,
    password: passwordSchema,
    confirmPassword: z.string(),
    firstName: sanitizedString(1, 50),
    lastName: sanitizedString(1, 50),
    acceptTerms: z.literal(true, {
      errorMap: () => ({ message: 'You must accept the terms and conditions' }),
    }),
  }).refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  }),
});

export const loginSchema = z.object({
  body: z.object({
    email: emailSchema,
    password: z.string().min(1, 'Password is required'),
    rememberMe: z.boolean().optional().default(false),
  }),
});

export const forgotPasswordSchema = z.object({
  body: z.object({
    email: emailSchema,
  }),
});

export const resetPasswordSchema = z.object({
  body: z.object({
    token: z.string().min(1, 'Reset token is required'),
    password: passwordSchema,
    confirmPassword: z.string(),
  }).refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  }),
});

export const changePasswordSchema = z.object({
  body: z.object({
    currentPassword: z.string().min(1, 'Current password is required'),
    newPassword: passwordSchema,
    confirmPassword: z.string(),
  }).refine((data) => data.newPassword === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  }).refine((data) => data.currentPassword !== data.newPassword, {
    message: 'New password must be different from current password',
    path: ['newPassword'],
  }),
});

// =============================================================================
// USER SCHEMAS
// =============================================================================

export const updateProfileSchema = z.object({
  body: z.object({
    firstName: sanitizedString(1, 50).optional(),
    lastName: sanitizedString(1, 50).optional(),
    phone: z
      .string()
      .regex(/^\+?[\d\s-()]{10,20}$/, 'Invalid phone number format')
      .optional()
      .nullable(),
    avatar: z.string().url('Invalid avatar URL').optional().nullable(),
  }),
});

export const addressSchema = z.object({
  body: z.object({
    label: sanitizedString(1, 50).optional(),
    firstName: sanitizedString(1, 50),
    lastName: sanitizedString(1, 50),
    company: sanitizedString(1, 100).optional().nullable(),
    addressLine1: sanitizedString(1, 255),
    addressLine2: sanitizedString(1, 255).optional().nullable(),
    city: sanitizedString(1, 100),
    state: sanitizedString(1, 100),
    postalCode: sanitizedString(1, 20),
    country: z.string().length(2, 'Country must be ISO 3166-1 alpha-2 code'),
    phone: z.string().regex(/^\+?[\d\s-()]{10,20}$/).optional().nullable(),
    isDefault: z.boolean().optional().default(false),
  }),
});

// =============================================================================
// PRODUCT SCHEMAS
// =============================================================================

export const createProductSchema = z.object({
  body: z.object({
    name: sanitizedString(1, 255),
    slug: z
      .string()
      .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'Invalid slug format')
      .max(255),
    description: sanitizedHtml(10000),
    shortDescription: sanitizedString(1, 500).optional(),
    sku: sanitizedString(1, 50),
    price: z.number().positive('Price must be positive').multipleOf(0.01),
    compareAtPrice: z.number().positive().multipleOf(0.01).optional().nullable(),
    costPrice: z.number().positive().multipleOf(0.01).optional().nullable(),
    quantity: z.number().int().min(0).default(0),
    lowStockThreshold: z.number().int().min(0).default(5),
    weight: z.number().positive().optional().nullable(),
    dimensions: z
      .object({
        length: z.number().positive(),
        width: z.number().positive(),
        height: z.number().positive(),
      })
      .optional()
      .nullable(),
    categoryId: idSchema,
    brandId: idSchema.optional().nullable(),
    tags: z.array(sanitizedString(1, 50)).max(20).optional(),
    images: z
      .array(
        z.object({
          url: z.string().url(),
          alt: sanitizedString(1, 255).optional(),
          position: z.number().int().min(0),
        })
      )
      .max(20)
      .optional(),
    isActive: z.boolean().default(true),
    isFeatured: z.boolean().default(false),
    metaTitle: sanitizedString(1, 60).optional(),
    metaDescription: sanitizedString(1, 160).optional(),
  }),
});

export const updateProductSchema = z.object({
  params: z.object({
    id: idSchema,
  }),
  body: createProductSchema.shape.body.partial(),
});

export const productQuerySchema = z.object({
  query: paginationSchema.extend({
    search: sanitizedString(1, 100).optional(),
    category: idSchema.optional(),
    brand: idSchema.optional(),
    minPrice: z.coerce.number().min(0).optional(),
    maxPrice: z.coerce.number().min(0).optional(),
    inStock: z.coerce.boolean().optional(),
    isFeatured: z.coerce.boolean().optional(),
    tags: z.string().optional().transform((val) => val?.split(',')),
  }),
});

// =============================================================================
// CART SCHEMAS
// =============================================================================

export const addToCartSchema = z.object({
  body: z.object({
    productId: idSchema,
    variantId: idSchema.optional(),
    quantity: z.number().int().min(1).max(100),
  }),
});

export const updateCartItemSchema = z.object({
  params: z.object({
    itemId: idSchema,
  }),
  body: z.object({
    quantity: z.number().int().min(0).max(100),
  }),
});

// =============================================================================
// ORDER SCHEMAS
// =============================================================================

export const createOrderSchema = z.object({
  body: z.object({
    shippingAddressId: idSchema,
    billingAddressId: idSchema.optional(),
    paymentMethodId: z.string().min(1),
    shippingMethodId: idSchema,
    notes: sanitizedString(1, 500).optional(),
    couponCode: sanitizedString(1, 50).optional(),
  }),
});

export const orderQuerySchema = z.object({
  query: paginationSchema.extend({
    status: z
      .enum(['pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded'])
      .optional(),
    startDate: z.coerce.date().optional(),
    endDate: z.coerce.date().optional(),
  }),
});

// =============================================================================
// REVIEW SCHEMAS
// =============================================================================

export const createReviewSchema = z.object({
  body: z.object({
    productId: idSchema,
    rating: z.number().int().min(1).max(5),
    title: sanitizedString(1, 100).optional(),
    content: sanitizedString(10, 2000),
  }),
});

// =============================================================================
// VALIDATION MIDDLEWARE
// =============================================================================

import { Request, Response, NextFunction } from 'express';
import { AppError } from '../middleware/error.middleware';

/**
 * Validation middleware factory
 */
export function validate(schema: z.ZodSchema) {
  return async (req: Request, _res: Response, next: NextFunction): Promise<void> => {
    try {
      const validated = await schema.parseAsync({
        body: req.body,
        query: req.query,
        params: req.params,
      });

      // Replace request data with validated/sanitized data
      req.body = validated.body ?? req.body;
      req.query = validated.query ?? req.query;
      req.params = validated.params ?? req.params;

      next();
    } catch (error) {
      if (error instanceof z.ZodError) {
        const formattedErrors = error.issues.reduce(
          (acc, issue) => {
            const path = issue.path.join('.');
            if (!acc[path]) acc[path] = [];
            acc[path].push(issue.message);
            return acc;
          },
          {} as Record<string, string[]>
        );

        return next(
          new AppError('Validation failed', 422, 'VALIDATION_ERROR', true, {
            errors: formattedErrors,
          })
        );
      }
      next(error);
    }
  };
}

export default {
  validate,
  registerSchema,
  loginSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
  changePasswordSchema,
  updateProfileSchema,
  addressSchema,
  createProductSchema,
  updateProductSchema,
  productQuerySchema,
  addToCartSchema,
  updateCartItemSchema,
  createOrderSchema,
  orderQuerySchema,
  createReviewSchema,
};
