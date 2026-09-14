import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { api, clearAccessToken, setAccessToken } from '../utils/api';

interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: string;
  emailVerified: boolean;
}

interface BackendUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  email_verified: boolean;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  user: BackendUser;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

interface RegisterData {
  email: string;
  password: string;
  confirmPassword: string;
  firstName: string;
  lastName: string;
  acceptTerms: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function mapUser(user: BackendUser): User {
  return {
    id: user.id,
    email: user.email,
    firstName: user.first_name,
    lastName: user.last_name,
    role: user.role,
    emailVerified: user.email_verified,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await api.post<TokenResponse>('/auth/refresh', {});
        setAccessToken(response.data.access_token);
        setUser(mapUser(response.data.user));
      } catch {
        clearAccessToken();
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = useCallback(
    async (email: string, password: string, _rememberMe = false) => {
      const response = await api.post<TokenResponse>('/auth/login', {
        email,
        password,
      });
      setAccessToken(response.data.access_token);
      setUser(mapUser(response.data.user));
    },
    [],
  );

  const register = useCallback(async (data: RegisterData) => {
    const response = await api.post<TokenResponse>('/auth/register', {
      email: data.email,
      password: data.password,
      first_name: data.firstName,
      last_name: data.lastName,
    });
    setAccessToken(response.data.access_token);
    setUser(mapUser(response.data.user));
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // Local logout still proceeds if the server is unavailable.
    } finally {
      clearAccessToken();
      setUser(null);
      navigate('/');
    }
  }, [navigate]);

  const refreshUser = useCallback(async () => {
    try {
      const response = await api.get<BackendUser>('/auth/me');
      setUser(mapUser(response.data));
    } catch {
      clearAccessToken();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    if (!user) return;

    const refreshInterval = setInterval(async () => {
      try {
        const response = await api.post<TokenResponse>('/auth/refresh', {});
        setAccessToken(response.data.access_token);
        setUser(mapUser(response.data.user));
      } catch {
        clearAccessToken();
        setUser(null);
      }
    }, 14 * 60 * 1000);

    return () => clearInterval(refreshInterval);
  }, [user]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}