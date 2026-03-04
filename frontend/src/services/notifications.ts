import api from './api';

export interface NotificationOut {
  id: number;
  user_id: number;
  organization_id: number;
  type: string;
  title: string;
  message: string;
  link?: string;
  source_type?: string;
  source_id?: number;
  read: boolean;
  created_at: string;
}

export interface NotificationUpdateResult {
  updated: number;
}

export const notificationsService = {
  async getNotifications(skip: number = 0, limit: number = 100): Promise<NotificationOut[]> {
    const response = await api.get('/v1/notifications', { params: { skip, limit } });
    return response.data;
  },

  async getUnreadCount(): Promise<number> {
    const response = await api.get('/v1/notifications/unread-count');
    return response.data;
  },

  async markAsRead(id: number): Promise<NotificationOut> {
    const response = await api.patch(`/v1/notifications/${id}/read`);
    return response.data;
  },

  async markAllAsRead(): Promise<NotificationUpdateResult> {
    const response = await api.patch('/v1/notifications/read-all');
    return response.data;
  }
};
