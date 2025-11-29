/**
 * Encryption Utilities
 * 
 * Secure encryption/decryption for sensitive data.
 * Uses AES-256-GCM for authenticated encryption.
 */

import crypto from 'crypto';
import { encryptionConfig } from '../config/security.config';

const ALGORITHM = encryptionConfig.algorithm;
const IV_LENGTH = encryptionConfig.ivLength;
const TAG_LENGTH = encryptionConfig.tagLength;

/**
 * Get encryption key from environment
 */
function getKey(): Buffer {
  const key = process.env.ENCRYPTION_KEY;
  if (!key || key.length !== 32) {
    throw new Error('ENCRYPTION_KEY must be exactly 32 characters');
  }
  return Buffer.from(key);
}

/**
 * Encrypt sensitive data
 * Returns: base64(iv + authTag + ciphertext)
 */
export function encrypt(plaintext: string): string {
  const key = getKey();
  const iv = crypto.randomBytes(IV_LENGTH);
  
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv, {
    authTagLength: TAG_LENGTH,
  });
  
  let encrypted = cipher.update(plaintext, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  
  const authTag = cipher.getAuthTag();
  
  // Combine iv + authTag + ciphertext
  const combined = Buffer.concat([
    iv,
    authTag,
    Buffer.from(encrypted, 'hex'),
  ]);
  
  return combined.toString('base64');
}

/**
 * Decrypt sensitive data
 */
export function decrypt(encryptedData: string): string {
  const key = getKey();
  const combined = Buffer.from(encryptedData, 'base64');
  
  // Extract iv, authTag, and ciphertext
  const iv = combined.subarray(0, IV_LENGTH);
  const authTag = combined.subarray(IV_LENGTH, IV_LENGTH + TAG_LENGTH);
  const ciphertext = combined.subarray(IV_LENGTH + TAG_LENGTH);
  
  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv, {
    authTagLength: TAG_LENGTH,
  });
  
  decipher.setAuthTag(authTag);
  
  let decrypted = decipher.update(ciphertext);
  decrypted = Buffer.concat([decrypted, decipher.final()]);
  
  return decrypted.toString('utf8');
}

/**
 * Hash data using SHA-256 (one-way, for comparisons)
 */
export function hash(data: string): string {
  return crypto.createHash('sha256').update(data).digest('hex');
}

/**
 * Hash data with a salt using HMAC-SHA256
 */
export function hmacHash(data: string, salt?: string): string {
  const key = salt || process.env.ENCRYPTION_KEY!;
  return crypto.createHmac('sha256', key).update(data).digest('hex');
}

/**
 * Generate a secure random token
 */
export function generateToken(length: number = 32): string {
  return crypto.randomBytes(length).toString('hex');
}

/**
 * Generate a URL-safe random token
 */
export function generateUrlSafeToken(length: number = 32): string {
  return crypto.randomBytes(length).toString('base64url');
}

/**
 * Timing-safe string comparison
 * Prevents timing attacks when comparing secrets
 */
export function secureCompare(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

/**
 * Mask sensitive data for display (e.g., credit card: **** **** **** 1234)
 */
export function maskSensitive(
  data: string,
  visibleStart: number = 0,
  visibleEnd: number = 4,
  maskChar: string = '*'
): string {
  if (data.length <= visibleStart + visibleEnd) {
    return maskChar.repeat(data.length);
  }
  
  const start = data.slice(0, visibleStart);
  const end = data.slice(-visibleEnd);
  const masked = maskChar.repeat(data.length - visibleStart - visibleEnd);
  
  return start + masked + end;
}

/**
 * Generate a cryptographically secure random password
 */
export function generateSecurePassword(length: number = 16): string {
  const lowercase = 'abcdefghijklmnopqrstuvwxyz';
  const uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const numbers = '0123456789';
  const special = '!@#$%^&*()_+-=[]{}|;:,.<>?';
  const allChars = lowercase + uppercase + numbers + special;
  
  let password = '';
  
  // Ensure at least one of each type
  password += lowercase[crypto.randomInt(lowercase.length)];
  password += uppercase[crypto.randomInt(uppercase.length)];
  password += numbers[crypto.randomInt(numbers.length)];
  password += special[crypto.randomInt(special.length)];
  
  // Fill the rest randomly
  for (let i = password.length; i < length; i++) {
    password += allChars[crypto.randomInt(allChars.length)];
  }
  
  // Shuffle the password
  return password
    .split('')
    .sort(() => crypto.randomInt(3) - 1)
    .join('');
}

/**
 * Derive a key from a password using PBKDF2
 */
export async function deriveKey(
  password: string,
  salt: string,
  iterations: number = 100000
): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    crypto.pbkdf2(password, salt, iterations, 32, 'sha256', (err, key) => {
      if (err) reject(err);
      else resolve(key);
    });
  });
}

export default {
  encrypt,
  decrypt,
  hash,
  hmacHash,
  generateToken,
  generateUrlSafeToken,
  secureCompare,
  maskSensitive,
  generateSecurePassword,
  deriveKey,
};
