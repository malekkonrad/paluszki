import axiosInstance from '../axiosInstance';
import type { IChatMessage } from '../interfaces/chat';

class ChatService {
  static async getHistory(meetingCode: string): Promise<IChatMessage[]> {
    const response = await axiosInstance.get<IChatMessage[]>(`/meetings/${meetingCode}/messages`);
    return response.data;
  }
}

export default ChatService;
