/**
 * Order Routes
 * 
 * Order management endpoints.
 */

import { Router } from 'express';
import { authenticate, authorize } from '../middleware/auth.middleware';
import { validate } from '../validators/schemas';
import { createOrderSchema, orderQuerySchema } from '../validators/schemas';
import { asyncHandler, Errors, AppError } from '../middleware/error.middleware';
import { prisma } from '../utils/prisma';
import { logAuditEvent } from '../utils/logger';
import { Request, Response } from 'express';
import { randomUUID } from 'crypto';

const router = Router();

/**
 * Create order from cart
 * POST /api/v1/orders
 */
router.post(
  '/',
  authenticate,
  validate(createOrderSchema),
  asyncHandler(async (req: Request, res: Response) => {
    const userId = req.user!.id;
    const { shippingAddressId, billingAddressId, paymentMethodId, shippingMethodId, notes } = req.body;

    // Get user's cart
    const cart = await prisma.cart.findUnique({
      where: { userId },
      include: {
        items: {
          include: {
            product: {
              select: { id: true, name: true, price: true, quantity: true },
            },
          },
        },
      },
    });

    if (!cart || cart.items.length === 0) {
      throw Errors.BadRequest('Cart is empty');
    }

    // Verify all items are in stock
    for (const item of cart.items) {
      if (item.product.quantity < item.quantity) {
        throw Errors.BadRequest(
          `Insufficient stock for ${item.product.name}. Only ${item.product.quantity} available.`
        );
      }
    }

    // Verify shipping address belongs to user
    const shippingAddress = await prisma.address.findFirst({
      where: { id: shippingAddressId, userId },
    });

    if (!shippingAddress) {
      throw Errors.NotFound('Shipping address');
    }

    // Calculate totals
    const subtotal = cart.items.reduce(
      (sum, item) => sum + item.quantity * item.product.price,
      0
    );
    const shippingCost = 0; // TODO: Calculate based on shipping method
    const tax = subtotal * 0.1; // TODO: Calculate based on location
    const total = subtotal + shippingCost + tax;

    // Generate order number
    const orderNumber = `ORD-${Date.now()}-${randomUUID().split('-')[0].toUpperCase()}`;

    // Create order in transaction
    const order = await prisma.$transaction(async (tx) => {
      // Create order
      const newOrder = await tx.order.create({
        data: {
          orderNumber,
          userId,
          status: 'PENDING',
          subtotal,
          shippingCost,
          tax,
          total,
          notes,
          shippingAddress: JSON.parse(JSON.stringify(shippingAddress)),
          billingAddress: billingAddressId
            ? JSON.parse(JSON.stringify(await tx.address.findUnique({ where: { id: billingAddressId } })))
            : JSON.parse(JSON.stringify(shippingAddress)),
          items: {
            create: cart.items.map((item) => ({
              productId: item.productId,
              productName: item.product.name,
              quantity: item.quantity,
              price: item.product.price,
              total: item.quantity * item.product.price,
            })),
          },
        },
        include: {
          items: true,
        },
      });

      // Update product quantities
      for (const item of cart.items) {
        await tx.product.update({
          where: { id: item.productId },
          data: {
            quantity: { decrement: item.quantity },
          },
        });
      }

      // Clear cart
      await tx.cartItem.deleteMany({ where: { cartId: cart.id } });

      return newOrder;
    });

    logAuditEvent('order.created', userId, { orderId: order.id, orderNumber, total }, req.requestId);

    res.status(201).json({
      success: true,
      message: 'Order created successfully',
      data: {
        order: {
          id: order.id,
          orderNumber: order.orderNumber,
          status: order.status,
          total: order.total,
          items: order.items,
        },
      },
    });
  })
);

/**
 * Get user's orders
 * GET /api/v1/orders
 */
router.get(
  '/',
  authenticate,
  validate(orderQuerySchema),
  asyncHandler(async (req: Request, res: Response) => {
    const userId = req.user!.id;
    const { page = 1, limit = 10, status, startDate, endDate } = req.query as Record<string, string>;

    const pageNum = parseInt(page, 10);
    const limitNum = Math.min(parseInt(limit, 10), 50);
    const skip = (pageNum - 1) * limitNum;

    const where: Record<string, unknown> = { userId };

    if (status) {
      where.status = status.toUpperCase();
    }

    if (startDate || endDate) {
      where.createdAt = {};
      if (startDate) (where.createdAt as Record<string, Date>).gte = new Date(startDate);
      if (endDate) (where.createdAt as Record<string, Date>).lte = new Date(endDate);
    }

    const [orders, total] = await Promise.all([
      prisma.order.findMany({
        where,
        skip,
        take: limitNum,
        orderBy: { createdAt: 'desc' },
        select: {
          id: true,
          orderNumber: true,
          status: true,
          total: true,
          createdAt: true,
          _count: { select: { items: true } },
        },
      }),
      prisma.order.count({ where }),
    ]);

    res.json({
      success: true,
      data: {
        orders,
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

/**
 * Get order by ID
 * GET /api/v1/orders/:id
 */
router.get(
  '/:id',
  authenticate,
  asyncHandler(async (req: Request, res: Response) => {
    const { id } = req.params;
    const userId = req.user!.id;
    const isAdmin = ['ADMIN', 'MANAGER'].includes(req.user!.role);

    const where: Record<string, unknown> = { id };
    if (!isAdmin) {
      where.userId = userId;
    }

    const order = await prisma.order.findFirst({
      where,
      include: {
        items: {
          include: {
            product: {
              select: { id: true, slug: true, images: true },
            },
          },
        },
        user: isAdmin
          ? { select: { id: true, email: true, firstName: true, lastName: true } }
          : false,
      },
    });

    if (!order) {
      throw Errors.NotFound('Order');
    }

    res.json({
      success: true,
      data: { order },
    });
  })
);

/**
 * Cancel order
 * POST /api/v1/orders/:id/cancel
 */
router.post(
  '/:id/cancel',
  authenticate,
  asyncHandler(async (req: Request, res: Response) => {
    const { id } = req.params;
    const userId = req.user!.id;

    const order = await prisma.order.findFirst({
      where: { id, userId },
      include: { items: true },
    });

    if (!order) {
      throw Errors.NotFound('Order');
    }

    if (!['PENDING', 'PROCESSING'].includes(order.status)) {
      throw Errors.BadRequest('Order cannot be cancelled');
    }

    // Cancel order and restore inventory
    await prisma.$transaction(async (tx) => {
      await tx.order.update({
        where: { id },
        data: { status: 'CANCELLED', cancelledAt: new Date() },
      });

      // Restore product quantities
      for (const item of order.items) {
        await tx.product.update({
          where: { id: item.productId },
          data: { quantity: { increment: item.quantity } },
        });
      }
    });

    logAuditEvent('order.cancelled', userId, { orderId: id }, req.requestId);

    res.json({
      success: true,
      message: 'Order cancelled successfully',
    });
  })
);

/**
 * Update order status (Admin only)
 * PUT /api/v1/orders/:id/status
 */
router.put(
  '/:id/status',
  authenticate,
  authorize('ADMIN', 'MANAGER'),
  asyncHandler(async (req: Request, res: Response) => {
    const { id } = req.params;
    const { status } = req.body;

    const validStatuses = ['PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED'];
    if (!validStatuses.includes(status)) {
      throw Errors.BadRequest('Invalid status');
    }

    const order = await prisma.order.findUnique({ where: { id } });
    if (!order) {
      throw Errors.NotFound('Order');
    }

    await prisma.order.update({
      where: { id },
      data: {
        status,
        ...(status === 'SHIPPED' && { shippedAt: new Date() }),
        ...(status === 'DELIVERED' && { deliveredAt: new Date() }),
      },
    });

    logAuditEvent('order.status_updated', req.user!.id, { orderId: id, newStatus: status }, req.requestId);

    res.json({
      success: true,
      message: 'Order status updated',
    });
  })
);

export default router;
