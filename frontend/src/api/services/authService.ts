import axiosInstance from '../axiosInstance';
import type { IAuthResponse, IGoogleLoginRequest, ILoginRequest, IRegisterRequest, IUser } from '../interfaces/auth';

class AuthService {
  static async login(data: ILoginRequest): Promise<IAuthResponse> {
    const response = await axiosInstance.post<IAuthResponse>('/auth/login', data);
    return response.data;
  }

  static async register(data: IRegisterRequest): Promise<IAuthResponse> {
    const response = await axiosInstance.post<IAuthResponse>('/auth/register', data);
    return response.data;
  }

  static async googleLogin(data: IGoogleLoginRequest): Promise<IAuthResponse> {
    const response = await axiosInstance.post<IAuthResponse>('/auth/google', data);
    return response.data;
  }

  static async getMe(): Promise<IUser> {
    const response = await axiosInstance.get<IUser>('/auth/me');
    return response.data;
  }

  static async logout(): Promise<void> {
    await axiosInstance.post('/auth/logout');
  }
}

export default AuthService;
