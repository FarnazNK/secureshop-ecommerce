/**
 * Product Routes
 * 
 * Product management endpoints.
 */

import { Router } from 'express';
import {
  getProducts,
  getProduct,
  getFeaturedProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  getCategories,
} from '../controllers/product.controller';
import { authenticate, authorize, optionalAuth } from '../middleware/auth.middleware';
import { validate } from '../validators/schemas';
import {
  createProductSchema,
  updateProductSchema,
  productQuerySchema,
} from '../validators/schemas';

const router = Router();

// Public routes
router.get('/', validate(productQuerySchema), getProducts);
router.get('/featured', getFeaturedProducts);
router.get('/categories', getCategories);
router.get('/:idOrSlug', getProduct);

// Admin routes
router.post(
  '/',
  authenticate,
  authorize('ADMIN', 'MANAGER'),
  validate(createProductSchema),
  createProduct
);

router.put(
  '/:id',
  authenticate,
  authorize('ADMIN', 'MANAGER'),
  validate(updateProductSchema),
  updateProduct
);

router.delete(
  '/:id',
  authenticate,
  authorize('ADMIN'),
  deleteProduct
);

export default router;
