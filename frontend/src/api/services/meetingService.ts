import axiosInstance from '../axiosInstance';
import type { ICreateMeetingRequest, ICreateMeetingResponse, IMeeting } from '../interfaces/meeting';

class MeetingService {
  static async create(data?: ICreateMeetingRequest): Promise<ICreateMeetingResponse> {
    const response = await axiosInstance.post<ICreateMeetingResponse>('/meetings', data || {});
    return response.data;
  }

  static async getByCode(code: string): Promise<IMeeting> {
    const response = await axiosInstance.get<IMeeting>(`/meetings/${code}`);
    return response.data;
  }

  static async join(code: string): Promise<{ status: string }> {
    const response = await axiosInstance.post<{ status: string }>(`/meetings/${code}/join`);
    return response.data;
  }

  static async approveParticipant(code: string, userId: string): Promise<void> {
    await axiosInstance.post(`/meetings/${code}/participants/${userId}/approve`);
  }

  static async rejectParticipant(code: string, userId: string): Promise<void> {
    await axiosInstance.post(`/meetings/${code}/participants/${userId}/reject`);
  }

  static async leave(code: string): Promise<void> {
    await axiosInstance.delete(`/meetings/${code}/leave`);
  }
}

export default MeetingService;
