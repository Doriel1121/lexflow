import { useEffect, useState } from 'react';
import websocketManager from '../services/websocketManager';

/**
 * Hook for using the global WebSocket connection.
 * Does NOT create/destroy the connection - that's handled globally.
 * Simply registers listeners for events.
 */
export const useDocumentWebSocket = (onStatusUpdate?: (data: any) => void) => {
  const [isConnected, setIsConnected] = useState(websocketManager.isConnected());

  useEffect(() => {
    // Subscribe to connection state changes
    const unsubscribeConnectionState = websocketManager.onConnectionStateChange((connected) => {
      setIsConnected(connected);
    });

    return () => {
      unsubscribeConnectionState();
    };
  }, []);

  useEffect(() => {
    if (!onStatusUpdate) return;

    // Subscribe to messages
    const unsubscribeMessages = websocketManager.onMessage((data) => {
      onStatusUpdate(data);
    });

    return () => {
      unsubscribeMessages();
    };
  }, [onStatusUpdate]);

  return {
    isConnected,
    disconnect: () => websocketManager.disconnect(),
    reconnect: () => websocketManager.connect(),
  };
};
