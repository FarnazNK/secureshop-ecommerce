import axios, { AxiosError, AxiosRequestConfig } from 'axios';

const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api/v1').replace(/\/+$/, '');
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    config.headers['X-Request-ID'] = crypto.randomUUID();
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
    const isRefreshRequest = originalRequest.url?.includes('/auth/refresh');

    if (error.response?.status === 401 && !originalRequest._retry && !isRefreshRequest) {
      originalRequest._retry = true;
      try {
        const refreshResponse = await api.post('/auth/refresh', {});
        const token = (refreshResponse.data as { access_token?: string }).access_token;
        if (token) {
          setAccessToken(token);
          originalRequest.headers = {
            ...originalRequest.headers,
            Authorization: `Bearer ${token}`,
          };
        }
        return api(originalRequest);
      } catch {
        clearAccessToken();
        window.location.href = '/login';
        return Promise.reject(error);
      }
    }

    const responseData = error.response?.data as
      | { detail?: string; error?: string | { code?: string; message?: string; details?: unknown } }
      | undefined;
    const nestedError =
      responseData?.error && typeof responseData.error === 'object' ? responseData.error : undefined;

    return Promise.reject({
      status: error.response?.status || 500,
      code: nestedError?.code || 'UNKNOWN_ERROR',
      message:
        responseData?.detail ||
        nestedError?.message ||
        (typeof responseData?.error === 'string' ? responseData.error : undefined) ||
        error.message ||
        'An unexpected error occurred',
      details: nestedError?.details,
    });
  },
);

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface ApiError {
  status: number;
  code: string;
  message: string;
  details?: Record<string, string[]>;
}

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    'code' in error &&
    'message' in error
  );
}

export default api;