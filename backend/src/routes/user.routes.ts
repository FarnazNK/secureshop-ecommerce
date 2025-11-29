/**
 * User Routes
 * 
 * User profile and address management endpoints.
 */

import { Router } from 'express';
import { authenticate, authorize } from '../middleware/auth.middleware';
import { validate } from '../validators/schemas';
import { updateProfileSchema, addressSchema, changePasswordSchema } from '../validators/schemas';
import { asyncHandler, Errors } from '../middleware/error.middleware';
import { prisma } from '../utils/prisma';
import { logAuditEvent } from '../utils/logger';
import { passwordConfig } from '../config/security.config';
import bcrypt from 'bcryptjs';
import { Request, Response } from 'express';

const router = Router();

// All routes require authentication
router.use(authenticate);

/**
 * Get user profile
 * GET /api/v1/users/profile
 */
router.get(
  '/profile',
  asyncHandler(async (req: Request, res: Response) => {
    const user = await prisma.user.findUnique({
      where: { id: req.user!.id },
      select: {
        id: true,
        email: true,
        firstName: true,
        lastName: true,
        phone: true,
        avatar: true,
        emailVerified: true,
        createdAt: true,
        lastLoginAt: true,
      },
    });

    if (!user) {
      throw Errors.NotFound('User');
    }

    res.json({
      success: true,
      data: { user },
    });
  })
);

/**
 * Update user profile
 * PUT /api/v1/users/profile
 */
router.put(
  '/profile',
  validate(updateProfileSchema),
  asyncHandler(async (req: Request, res: Response) => {
    const userId = req.user!.id;
    const updateData = req.body;

    const user = await prisma.user.update({
      where: { id: userId },
      data: updateData,
      select: {
        id: true,
        email: true,
        firstName: true,
        lastName: true,
        phone: true,
        avatar: true,
      },
    });

    logAuditEvent('user.profile_updated', userId, { fields: Object.keys(updateData) }, req.requestId);

    res.json({
      success: true,
      message: 'Profile updated successfully',
      data: { user },
    });
  })
);

/**
 * Change password
 * PUT /api/v1/users/password
 */
router.put(
  '/password',
  validate(changePasswordSchema),
  asyncHandler(async (req: Request, res: Response) => {
    const userId = req.user!.id;
    const { currentPassword, newPassword } = req.body;

    // Get current password hash
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { passwordHash: true },
    });

    if (!user) {
      throw Errors.NotFound('User');
    }

    // Verify current password
    const isValid = await bcrypt.compare(currentPassword, user.passwordHash);
    if (!isValid) {
      throw Errors.BadRequest('Current password is incorrect');
    }

    // Hash new password
    const passwordHash = await bcrypt.hash(newPassword, passwordConfig.bcryptRounds);

    await prisma.user.update({
      where: { id: userId },
      data: { passwordHash },
    });

    logAuditEvent('user.password_changed', userId, {}, req.requestId);

    res.json({
      success: true,
      message: 'Password changed successfully',
    });
  })
);

/**
 * Get user addresses
 * GET /api/v1/users/addresses
 */
router.get(
  '/addresses',
  asyncHandler(async (req: Request, res: Response) => {
    const addresses = await prisma.address.findMany({
      where: { userId: req.user!.id },
      orderBy: [{ isDefault: 'desc' }, { createdAt: 'desc' }],
    });

    res.json({
      success: true,
      data: { addresses },
    });
  })
);

/**
 * Add new address
 * POST /api/v1/users/addresses
 */
router.post(
  '/addresses',
  validate(addressSchema),
  asyncHandler(async (req: Request, res: Response) => {
    const userId = req.user!.id;
    const addressData = req.body;

    // If this is set as default, unset other defaults
    if (addressData.isDefault) {
      await prisma.address.updateMany({
        where: { userId, isDefault: true },
        data: { isDefault: false },
      });
    }

    const address = await prisma.address.create({
      data: {
        ...addressData,
        userId,
      },
    });

    res.status(201).json({
      success: true,
      message: 'Address added successfully',
      data: { address },
    });
  })
);

/**
 * Update address
 * PUT /api/v1/users/addresses/:id
 */
router.put(
  '/addresses/:id',
  validate(addressSchema),
  asyncHandler(async (req: Request, res: Response) => {
    const { id } = req.params;
    const userId = req.user!.id;
    const addressData = req.body;

    // Verify address belongs to user
    const existing = await prisma.address.findFirst({
      where: { id, userId },
    });

    if (!existing) {
      throw Errors.NotFound('Address');
    }

    // If setting as default, unset others
    if (addressData.isDefault) {
      await prisma.address.updateMany({
        where: { userId, isDefault: true, id: { not: id } },
        data: { isDefault: false },
      });
    }

    const address = await prisma.address.update({
      where: { id },
      data: addressData,
    });

    res.json({
      success: true,
      message: 'Address updated successfully',
      data: { address },
    });
  })
);

/**
 * Delete address
 * DELETE /api/v1/users/addresses/:id
 */
router.delete(
  '/addresses/:id',
  asyncHandler(async (req: Request, res: Response) => {
    const { id } = req.params;
    const userId = req.user!.id;

    // Verify address belongs to user
    const existing = await prisma.address.findFirst({
      where: { id, userId },
    });

    if (!existing) {
      throw Errors.NotFound('Address');
    }

    await prisma.address.delete({ where: { id } });

    res.json({
      success: true,
      message: 'Address deleted successfully',
    });
  })
);

/**
 * Get all users (Admin only)
 * GET /api/v1/users
 */
router.get(
  '/',
  authorize('ADMIN'),
  asyncHandler(async (req: Request, res: Response) => {
    const { page = '1', limit = '20', search } = req.query as Record<string, string>;

    const pageNum = parseInt(page, 10);
    const limitNum = Math.min(parseInt(limit, 10), 100);
    const skip = (pageNum - 1) * limitNum;

    const where: Record<string, unknown> = {};
    if (search) {
      where.OR = [
        { email: { contains: search, mode: 'insensitive' } },
        { firstName: { contains: search, mode: 'insensitive' } },
        { lastName: { contains: search, mode: 'insensitive' } },
      ];
    }

    const [users, total] = await Promise.all([
      prisma.user.findMany({
        where,
        skip,
        take: limitNum,
        orderBy: { createdAt: 'desc' },
        select: {
          id: true,
          email: true,
          firstName: true,
          lastName: true,
          role: true,
          isActive: true,
          emailVerified: true,
          createdAt: true,
          lastLoginAt: true,
        },
      }),
      prisma.user.count({ where }),
    ]);

    res.json({
      success: true,
      data: {
        users,
        pagination: {
          page: pageNum,
          limit: limitNum,
          total,
          totalPages: Math.ceil(total / limitNum),
        },
      },
    });
  })
);

export default router;
