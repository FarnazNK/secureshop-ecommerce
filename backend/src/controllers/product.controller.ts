/**
 * Product Controller
 * 
 * Handles product CRUD operations with caching and security.
 */

import { Request, Response } from 'express';
import { prisma } from '../utils/prisma';
import { withCache, cacheDelete, cacheDeletePattern } from '../utils/redis';
import { logAuditEvent } from '../utils/logger';
import { AppError, asyncHandler, Errors } from '../middleware/error.middleware';

// Cache keys
const CACHE_KEYS = {
  products: 'products:list',
  product: (id: string) => `products:${id}`,
  featured: 'products:featured',
  categories: 'categories:list',
};

/**
 * Get all products (paginated)
 * GET /api/v1/products
 */
export const getProducts = asyncHandler(async (req: Request, res: Response) => {
  const {
    page = 1,
    limit = 20,
    sortBy = 'createdAt',
    sortOrder = 'desc',
    search,
    category,
    brand,
    minPrice,
    maxPrice,
    inStock,
    isFeatured,
    tags,
  } = req.query as Record<string, string | undefined>;

  const pageNum = parseInt(page, 10);
  const limitNum = Math.min(parseInt(limit, 10), 100);
  const skip = (pageNum - 1) * limitNum;

  // Build where clause
  const where: Record<string, unknown> = {
    isActive: true,
  };

  if (search) {
    where.OR = [
      { name: { contains: search, mode: 'insensitive' } },
      { description: { contains: search, mode: 'insensitive' } },
      { sku: { contains: search, mode: 'insensitive' } },
    ];
  }

  if (category) {
    where.categoryId = category;
  }

  if (brand) {
    where.brandId = brand;
  }

  if (minPrice || maxPrice) {
    where.price = {};
    if (minPrice) (where.price as Record<string, number>).gte = parseFloat(minPrice);
    if (maxPrice) (where.price as Record<string, number>).lte = parseFloat(maxPrice);
  }

  if (inStock === 'true') {
    where.quantity = { gt: 0 };
  }

  if (isFeatured === 'true') {
    where.isFeatured = true;
  }

  if (tags) {
    where.tags = { hasSome: tags.split(',') };
  }

  // Validate sort field
  const allowedSortFields = ['createdAt', 'price', 'name', 'quantity'];
  const sortField = allowedSortFields.includes(sortBy) ? sortBy : 'createdAt';

  // Execute query
  const [products, total] = await Promise.all([
    prisma.product.findMany({
      where,
      skip,
      take: limitNum,
      orderBy: { [sortField]: sortOrder === 'asc' ? 'asc' : 'desc' },
      select: {
        id: true,
        name: true,
        slug: true,
        shortDescription: true,
        price: true,
        compareAtPrice: true,
        quantity: true,
        images: true,
        isFeatured: true,
        category: {
          select: { id: true, name: true, slug: true },
        },
        brand: {
          select: { id: true, name: true },
        },
        createdAt: true,
      },
    }),
    prisma.product.count({ where }),
  ]);

  const totalPages = Math.ceil(total / limitNum);

  res.json({
    success: true,
    data: {
      products,
      pagination: {
        page: pageNum,
        limit: limitNum,
        total,
        totalPages,
        hasNext: pageNum < totalPages,
        hasPrev: pageNum > 1,
      },
    },
  });
});

/**
 * Get single product by ID or slug
 * GET /api/v1/products/:idOrSlug
 */
export const getProduct = asyncHandler(async (req: Request, res: Response) => {
  const { idOrSlug } = req.params;

  // Check if it's a UUID or slug
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(idOrSlug);

  const cacheKey = CACHE_KEYS.product(idOrSlug);

  const product = await withCache(
    cacheKey,
    async () => {
      return prisma.product.findFirst({
        where: isUuid
          ? { id: idOrSlug, isActive: true }
          : { slug: idOrSlug, isActive: true },
        include: {
          category: {
            select: { id: true, name: true, slug: true },
          },
          brand: {
            select: { id: true, name: true, logo: true },
          },
          reviews: {
            where: { isApproved: true },
            take: 10,
            orderBy: { createdAt: 'desc' },
            select: {
              id: true,
              rating: true,
              title: true,
              content: true,
              createdAt: true,
              user: {
                select: { firstName: true, lastName: true },
              },
            },
          },
          _count: {
            select: { reviews: { where: { isApproved: true } } },
          },
        },
      });
    },
    3600 // 1 hour cache
  );

  if (!product) {
    throw Errors.NotFound('Product');
  }

  // Calculate average rating
  const avgRating = product.reviews.length > 0
    ? product.reviews.reduce((sum, r) => sum + r.rating, 0) / product.reviews.length
    : 0;

  res.json({
    success: true,
    data: {
      product: {
        ...product,
        averageRating: Math.round(avgRating * 10) / 10,
        reviewCount: product._count.reviews,
      },
    },
  });
});

/**
 * Get featured products
 * GET /api/v1/products/featured
 */
export const getFeaturedProducts = asyncHandler(async (_req: Request, res: Response) => {
  const products = await withCache(
    CACHE_KEYS.featured,
    async () => {
      return prisma.product.findMany({
        where: { isActive: true, isFeatured: true },
        take: 12,
        orderBy: { createdAt: 'desc' },
        select: {
          id: true,
          name: true,
          slug: true,
          shortDescription: true,
          price: true,
          compareAtPrice: true,
          images: true,
          category: {
            select: { name: true, slug: true },
          },
        },
      });
    },
    1800 // 30 minutes cache
  );

  res.json({
    success: true,
    data: { products },
  });
});

/**
 * Create new product (Admin only)
 * POST /api/v1/products
 */
export const createProduct = asyncHandler(async (req: Request, res: Response) => {
  const productData = req.body;

  // Check for duplicate SKU
  const existingSku = await prisma.product.findUnique({
    where: { sku: productData.sku },
    select: { id: true },
  });

  if (existingSku) {
    throw Errors.Conflict('A product with this SKU already exists');
  }

  // Check for duplicate slug
  const existingSlug = await prisma.product.findUnique({
    where: { slug: productData.slug },
    select: { id: true },
  });

  if (existingSlug) {
    throw Errors.Conflict('A product with this slug already exists');
  }

  const product = await prisma.product.create({
    data: productData,
    include: {
      category: { select: { id: true, name: true } },
      brand: { select: { id: true, name: true } },
    },
  });

  // Invalidate caches
  await cacheDeletePattern('products:*');

  logAuditEvent('product.created', req.user!.id, { productId: product.id, sku: product.sku }, req.requestId);

  res.status(201).json({
    success: true,
    message: 'Product created successfully',
    data: { product },
  });
});

/**
 * Update product (Admin only)
 * PUT /api/v1/products/:id
 */
export const updateProduct = asyncHandler(async (req: Request, res: Response) => {
  const { id } = req.params;
  const updateData = req.body;

  // Verify product exists
  const existingProduct = await prisma.product.findUnique({
    where: { id },
    select: { id: true, sku: true, slug: true },
  });

  if (!existingProduct) {
    throw Errors.NotFound('Product');
  }

  // Check for SKU conflict
  if (updateData.sku && updateData.sku !== existingProduct.sku) {
    const skuConflict = await prisma.product.findUnique({
      where: { sku: updateData.sku },
      select: { id: true },
    });
    if (skuConflict) {
      throw Errors.Conflict('A product with this SKU already exists');
    }
  }

  // Check for slug conflict
  if (updateData.slug && updateData.slug !== existingProduct.slug) {
    const slugConflict = await prisma.product.findUnique({
      where: { slug: updateData.slug },
      select: { id: true },
    });
    if (slugConflict) {
      throw Errors.Conflict('A product with this slug already exists');
    }
  }

  const product = await prisma.product.update({
    where: { id },
    data: {
      ...updateData,
      updatedAt: new Date(),
    },
    include: {
      category: { select: { id: true, name: true } },
      brand: { select: { id: true, name: true } },
    },
  });

  // Invalidate caches
  await cacheDelete(CACHE_KEYS.product(id));
  await cacheDelete(CACHE_KEYS.product(existingProduct.slug));
  await cacheDeletePattern('products:list*');

  logAuditEvent('product.updated', req.user!.id, { productId: id, changes: Object.keys(updateData) }, req.requestId);

  res.json({
    success: true,
    message: 'Product updated successfully',
    data: { product },
  });
});

/**
 * Delete product (Admin only - soft delete)
 * DELETE /api/v1/products/:id
 */
export const deleteProduct = asyncHandler(async (req: Request, res: Response) => {
  const { id } = req.params;

  const product = await prisma.product.findUnique({
    where: { id },
    select: { id: true, slug: true },
  });

  if (!product) {
    throw Errors.NotFound('Product');
  }

  // Soft delete
  await prisma.product.update({
    where: { id },
    data: {
      isActive: false,
      deletedAt: new Date(),
    },
  });

  // Invalidate caches
  await cacheDelete(CACHE_KEYS.product(id));
  await cacheDelete(CACHE_KEYS.product(product.slug));
  await cacheDeletePattern('products:*');

  logAuditEvent('product.deleted', req.user!.id, { productId: id }, req.requestId);

  res.json({
    success: true,
    message: 'Product deleted successfully',
  });
});

/**
 * Get product categories
 * GET /api/v1/products/categories
 */
export const getCategories = asyncHandler(async (_req: Request, res: Response) => {
  const categories = await withCache(
    CACHE_KEYS.categories,
    async () => {
      return prisma.category.findMany({
        where: { isActive: true },
        orderBy: { name: 'asc' },
        select: {
          id: true,
          name: true,
          slug: true,
          description: true,
          image: true,
          parentId: true,
          _count: {
            select: { products: { where: { isActive: true } } },
          },
        },
      });
    },
    3600 // 1 hour cache
  );

  res.json({
    success: true,
    data: { categories },
  });
});

export default {
  getProducts,
  getProduct,
  getFeaturedProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  getCategories,
};
