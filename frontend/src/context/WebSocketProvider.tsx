import React, { useEffect } from 'react';
import { useAuth } from './AuthContext';
import websocketManager from '../services/websocketManager';

/**
 * WebSocket Provider - Initializes and manages the global WebSocket connection
 * Wraps the app so the connection persists across page navigation
 */
export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    console.log('[WebSocketProvider] Auth state changed:', { isAuthenticated });
    
    if (isAuthenticated) {
      console.log('[WebSocketProvider] User authenticated, initializing WebSocket...');
      const token = localStorage.getItem('access_token');
      console.log('[WebSocketProvider] Token exists:', !!token);
      websocketManager.connect();
    } else {
      console.log('[WebSocketProvider] User not authenticated, disconnecting WebSocket...');
      websocketManager.disconnect();
    }

    // No cleanup - we want the connection to persist across component unmounts
    return () => {
      // Don't disconnect on unmount since this provider only unmounts when app exits
    };
  }, [isAuthenticated]);

  return <>{children}</>;
};
