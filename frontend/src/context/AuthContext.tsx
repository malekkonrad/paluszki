import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { IUser, ILoginRequest, IRegisterRequest, IGoogleLoginRequest } from '../api/interfaces/auth';
import AuthService from '../api/services/authService';

export interface AuthContextType {
  user: IUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: ILoginRequest) => Promise<void>;
  register: (data: IRegisterRequest) => Promise<void>;
  googleLogin: (data: IGoogleLoginRequest) => Promise<void>;
  demoLogin: () => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<IUser | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('token');
      const savedUser = localStorage.getItem('user');

      if (savedToken && savedUser) {
        try {
          setToken(savedToken);
          setUser(JSON.parse(savedUser));

          // Skip API call for demo token
          if (savedToken !== 'demo-token') {
            const freshUser = await AuthService.getMe();
            setUser(freshUser);
            localStorage.setItem('user', JSON.stringify(freshUser));
          }
        } catch {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          setToken(null);
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const handleAuthResponse = useCallback((authUser: IUser, authToken: string) => {
    setUser(authUser);
    setToken(authToken);
    localStorage.setItem('token', authToken);
    localStorage.setItem('user', JSON.stringify(authUser));
  }, []);

  const login = useCallback(async (data: ILoginRequest) => {
    const response = await AuthService.login(data);
    handleAuthResponse(response.user, response.token);
  }, [handleAuthResponse]);

  const register = useCallback(async (data: IRegisterRequest) => {
    const response = await AuthService.register(data);
    handleAuthResponse(response.user, response.token);
  }, [handleAuthResponse]);

  const googleLogin = useCallback(async (data: IGoogleLoginRequest) => {
    const response = await AuthService.googleLogin(data);
    handleAuthResponse(response.user, response.token);
  }, [handleAuthResponse]);

  const demoLogin = useCallback(() => {
    const demoUser: IUser = {
      id: 'demo-user-001',
      email: 'demo@meetflow.app',
      firstName: 'Demo',
      lastName: 'User',
      createdAt: new Date().toISOString(),
    };
    handleAuthResponse(demoUser, 'demo-token');
  }, [handleAuthResponse]);

  const logout = useCallback(() => {
    AuthService.logout().catch(() => {});
    setUser(null);
    setToken(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        register,
        googleLogin,
        demoLogin,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
