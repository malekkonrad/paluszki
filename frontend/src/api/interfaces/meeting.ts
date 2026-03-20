export type ParticipantStatus = 'waiting' | 'approved' | 'rejected';

export interface IParticipant {
  userId: string;
  firstName: string;
  lastName: string;
  avatarUrl?: string;
  status: ParticipantStatus;
  joinedAt: string;
  isHost: boolean;
}

export interface IMeeting {
  id: string;
  code: string;
  title: string;
  hostId: string;
  participants: IParticipant[];
  createdAt: string;
  isActive: boolean;
}

export interface ICreateMeetingRequest {
  title?: string;
}

export interface ICreateMeetingResponse {
  meeting: IMeeting;
  code: string;
}

export interface IJoinMeetingRequest {
  code: string;
}
