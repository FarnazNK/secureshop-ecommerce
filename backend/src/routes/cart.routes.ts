/**
 * Cart Routes
 * 
 * Shopping cart management endpoints.
 */

import { Router } from 'express';
import { authenticate, optionalAuth } from '../middleware/auth.middleware';
import { validate } from '../validators/schemas';
import { addToCartSchema, updateCartItemSchema } from '../validators/schemas';
import { asyncHandler, Errors } from '../middleware/error.middleware';
import { prisma } from '../utils/prisma';
import { Request, Response } from 'express';

const router = Router();

/**
 * Get cart
 * GET /api/v1/cart
 */
router.get('/', authenticate, asyncHandler(async (req: Request, res: Response) => {
  const cart = await prisma.cart.findUnique({
    where: { userId: req.user!.id },
    include: {
      items: {
        include: {
          product: {
            select: {
              id: true,
              name: true,
              slug: true,
              price: true,
              images: true,
              quantity: true,
            },
          },
        },
      },
    },
  });

  if (!cart) {
    return res.json({
      success: true,
      data: {
        cart: { items: [], subtotal: 0, itemCount: 0 },
      },
    });
  }

  // Calculate totals
  const subtotal = cart.items.reduce(
    (sum, item) => sum + item.quantity * item.price,
    0
  );

  res.json({
    success: true,
    data: {
      cart: {
        ...cart,
        subtotal,
        itemCount: cart.items.reduce((sum, item) => sum + item.quantity, 0),
      },
    },
  });
}));

/**
 * Add item to cart
 * POST /api/v1/cart/items
 */
router.post(
  '/items',
  authenticate,
  validate(addToCartSchema),
  asyncHandler(async (req: Request, res: Response) => {
    const { productId, quantity } = req.body;
    const userId = req.user!.id;

    // Verify product exists and has stock
    const product = await prisma.product.findUnique({
      where: { id: productId, isActive: true },
      select: { id: true, price: true, quantity: true, name: true },
    });

    if (!product) {
      throw Errors.NotFound('Product');
    }

    if (product.quantity < quantity) {
      throw Errors.BadRequest(`Only ${product.quantity} items available`);
    }

    // Get or create cart
    let cart = await prisma.cart.findUnique({
      where: { userId },
    });

    if (!cart) {
      cart = await prisma.cart.create({
        data: { userId },
      });
    }

    // Check if item already in cart
    const existingItem = await prisma.cartItem.findFirst({
      where: { cartId: cart.id, productId },
    });

    if (existingItem) {
      // Update quantity
      const newQuantity = existingItem.quantity + quantity;
      if (newQuantity > product.quantity) {
        throw Errors.BadRequest(`Cannot add more than ${product.quantity} items`);
      }

      await prisma.cartItem.update({
        where: { id: existingItem.id },
        data: { quantity: newQuantity },
      });
    } else {
      // Add new item
      await prisma.cartItem.create({
        data: {
          cartId: cart.id,
          productId,
          quantity,
          price: product.price,
        },
      });
    }

    res.json({
      success: true,
      message: 'Item added to cart',
    });
  })
);

/**
 * Update cart item quantity
 * PUT /api/v1/cart/items/:itemId
 */
router.put(
  '/items/:itemId',
  authenticate,
  validate(updateCartItemSchema),
  asyncHandler(async (req: Request, res: Response) => {
    const { itemId } = req.params;
    const { quantity } = req.body;
    const userId = req.user!.id;

    // Verify item belongs to user's cart
    const cartItem = await prisma.cartItem.findFirst({
      where: {
        id: itemId,
        cart: { userId },
      },
      include: {
        product: { select: { quantity: true } },
      },
    });

    if (!cartItem) {
      throw Errors.NotFound('Cart item');
    }

    if (quantity === 0) {
      // Remove item
      await prisma.cartItem.delete({ where: { id: itemId } });
      return res.json({ success: true, message: 'Item removed from cart' });
    }

    if (quantity > cartItem.product.quantity) {
      throw Errors.BadRequest(`Only ${cartItem.product.quantity} items available`);
    }

    await prisma.cartItem.update({
      where: { id: itemId },
      data: { quantity },
    });

    res.json({
      success: true,
      message: 'Cart updated',
    });
  })
);

/**
 * Remove item from cart
 * DELETE /api/v1/cart/items/:itemId
 */
router.delete(
  '/items/:itemId',
  authenticate,
  asyncHandler(async (req: Request, res: Response) => {
    const { itemId } = req.params;
    const userId = req.user!.id;

    // Verify item belongs to user's cart
    const cartItem = await prisma.cartItem.findFirst({
      where: {
        id: itemId,
        cart: { userId },
      },
    });

    if (!cartItem) {
      throw Errors.NotFound('Cart item');
    }

    await prisma.cartItem.delete({ where: { id: itemId } });

    res.json({
      success: true,
      message: 'Item removed from cart',
    });
  })
);

/**
 * Clear cart
 * DELETE /api/v1/cart
 */
router.delete(
  '/',
  authenticate,
  asyncHandler(async (req: Request, res: Response) => {
    const userId = req.user!.id;

    const cart = await prisma.cart.findUnique({
      where: { userId },
    });

    if (cart) {
      await prisma.cartItem.deleteMany({
        where: { cartId: cart.id },
      });
    }

    res.json({
      success: true,
      message: 'Cart cleared',
    });
  })
);

export default router;
