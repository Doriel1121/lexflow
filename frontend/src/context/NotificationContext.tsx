import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { notificationsService } from '../services/notifications';
import { API_BASE_URL } from '../services/api';
import { useAuth } from './AuthContext';

export interface Notification {
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

interface NotificationContextProps {
  notifications: Notification[];
  unreadCount: number;
  loading: boolean;
  fetchNotifications: () => Promise<void>;
  markAsRead: (id: number) => Promise<void>;
  markAllAsRead: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextProps | undefined>(undefined);

export const NotificationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const { isAuthenticated } = useAuth();
  const token = localStorage.getItem('access_token');

  const fetchNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      setLoading(true);
      const [notifs, count] = await Promise.all([
        notificationsService.getNotifications(),
        notificationsService.getUnreadCount()
      ]);
      setNotifications(notifs);
      setUnreadCount(count);
    } catch (error) {
      console.error("Failed to fetch notifications", error);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  // WebSocket Connection
  useEffect(() => {
    if (!isAuthenticated || !token) return;

    // Connect to WebSocket using the appropriate protocol
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use the explicit API_BASE_URL (http://localhost:8000) and convert to ws://
    let wsUrlStr = API_BASE_URL.replace(/^http(s)?:\/\//, `${protocol}//`);
    
    // Ensure there is no trailing slash on the base URL
    if (wsUrlStr.endsWith('/')) {
        wsUrlStr = wsUrlStr.slice(0, -1);
    }
    
    // Build the final WebSocket URL
    const finalWsUrl = `${wsUrlStr}/api/v1/ws/notifications/${token}`;
    console.log("Attempting WebSocket Connection to:", finalWsUrl);

    const wsManager = new WebSocket(finalWsUrl);

    wsManager.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'new_notification') {
          const newNotif = message.data as Notification;
          setNotifications(prev => [newNotif, ...prev]);
          setUnreadCount(prev => prev + 1);
        } else if (message.type === 'DOCUMENT_PROCESSED') {
          // Dispatch a custom window event so DocumentViewer or DocumentList can refresh instantly
          const customEvent = new CustomEvent('document_processed', { detail: { document_id: message.document_id } });
          window.dispatchEvent(customEvent);
        }
      } catch (err) {
        console.error("Error parsing WebSocket message", err);
      }
    };

    wsManager.onerror = (error) => {
      console.warn("WebSocket notification error", error);
    };

    return () => {
      wsManager.close();
    };
  }, [isAuthenticated, token]);

  const markAsRead = async (id: number) => {
    try {
      await notificationsService.markAsRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error(`Failed to mark notification ${id} as read`, error);
    }
  };

  const markAllAsRead = async () => {
    try {
      await notificationsService.markAllAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error("Failed to mark all notifications as read", error);
    }
  };

  return (
    <NotificationContext.Provider value={{
      notifications, unreadCount, loading, fetchNotifications, markAsRead, markAllAsRead
    }}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};
