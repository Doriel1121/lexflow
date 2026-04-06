/**
 * Global WebSocket Manager - Singleton pattern
 * One persistent connection for the entire app, not per-page
 */

type MessageListener = (data: any) => void;

class WebSocketManager {
  private static instance: WebSocketManager;
  private ws: WebSocket | null = null;
  private reconnectTimeoutRef: NodeJS.Timeout | null = null;
  private isConnectingRef = false;
  private messageListeners: Set<MessageListener> = new Set();
  private connectionStateListeners: Set<(connected: boolean) => void> =
    new Set();

  private constructor() {}

  static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  /**
   * Establish WebSocket connection (only if not already connected)
   */
  connect(): void {
    console.log("[WebSocket Manager] connect() called");
    console.log("[WebSocket Manager] Current state:", {
      isConnecting: this.isConnectingRef,
      wsState: this.ws?.readyState,
      wsStates: { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 },
    });

    if (this.isConnectingRef || this.ws?.readyState === WebSocket.OPEN) {
      console.log("[WebSocket] Already connected or connecting");
      return;
    }

    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        console.warn("[WebSocket] No auth token found in localStorage");
        return;
      }

      console.log("[WebSocket Manager] Token found, attempting connection...");
      this.isConnectingRef = true;

      // Determine WebSocket URL
      const apiBaseUrl =
        import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
      console.log("[WebSocket Manager] API Base URL:", apiBaseUrl);

      const wsUrl = apiBaseUrl
        .replace("http://", "ws://")
        .replace("https://", "wss://");

      const fullUrl = `${wsUrl}/api/v1/ws/notifications/${token}`;
      console.log(
        "[WebSocket Manager] Connecting to:",
        fullUrl.replace(token, "***"),
      );

      this.ws = new WebSocket(fullUrl);

      this.ws.onopen = () => {
        console.log("[WebSocket Manager] Connected ✅");
        this.isConnectingRef = false;

        // Clear any pending reconnect timeout
        if (this.reconnectTimeoutRef) {
          clearTimeout(this.reconnectTimeoutRef);
          this.reconnectTimeoutRef = null;
        }

        // Notify all listeners
        window.dispatchEvent(new CustomEvent("websocket_connected"));
        this.notifyConnectionStateListeners(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Silently handle server heartbeat / pong frames
          if (data.type === "heartbeat" || data.type === "pong") {
            return;
          }

          console.log("[WebSocket Manager] Message received:", data);

          // Trigger custom events for backward compatibility
          if (data.type === "DOCUMENT_PROCESSED") {
            window.dispatchEvent(
              new CustomEvent("document_processed", {
                detail: { document_id: data.document_id },
              }),
            );
          }

          if (data.type === "DOCUMENT_STATUS_UPDATE") {
            window.dispatchEvent(
              new CustomEvent("document_status_update", {
                detail: data,
              }),
            );
          }

          // Notify all registered message listeners
          this.messageListeners.forEach((listener) => {
            try {
              listener(data);
            } catch (err) {
              console.error("[WebSocket Manager] Error in listener:", err);
            }
          });
        } catch (err) {
          console.error("[WebSocket Manager] Failed to parse message:", err);
        }
      };

      this.ws.onerror = (error) => {
        console.error("[WebSocket Manager] Error:", error);
        this.isConnectingRef = false;
      };

      this.ws.onclose = () => {
        console.log(
          "[WebSocket Manager] Disconnected, will reconnect in 5s...",
        );
        this.isConnectingRef = false;
        this.ws = null;
        this.notifyConnectionStateListeners(false);

        // Auto-reconnect after 5 seconds
        this.reconnectTimeoutRef = setTimeout(() => {
          console.log("[WebSocket Manager] Attempting auto-reconnect...");
          this.connect();
        }, 5000);
      };
    } catch (err) {
      console.error("[WebSocket Manager] Connection failed:", err);
      this.isConnectingRef = false;

      // Retry connection after 5 seconds
      this.reconnectTimeoutRef = setTimeout(() => {
        console.log("[WebSocket Manager] Retrying connection after error...");
        this.connect();
      }, 5000);
    }
  }

  /**
   * Gracefully disconnect
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    if (this.reconnectTimeoutRef) {
      clearTimeout(this.reconnectTimeoutRef);
      this.reconnectTimeoutRef = null;
    }
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Register a listener for incoming messages
   * Returns unsubscribe function
   */
  onMessage(listener: MessageListener): () => void {
    this.messageListeners.add(listener);
    return () => {
      this.messageListeners.delete(listener);
    };
  }

  /**
   * Register a listener for connection state changes
   * Returns unsubscribe function
   */
  onConnectionStateChange(listener: (connected: boolean) => void): () => void {
    this.connectionStateListeners.add(listener);
    // Immediately notify of current state
    listener(this.isConnected());
    return () => {
      this.connectionStateListeners.delete(listener);
    };
  }

  /**
   * Notify all connection state listeners
   */
  private notifyConnectionStateListeners(connected: boolean): void {
    this.connectionStateListeners.forEach((listener) => {
      try {
        listener(connected);
      } catch (err) {
        console.error(
          "[WebSocket Manager] Error in connection state listener:",
          err,
        );
      }
    });
  }
}

export default WebSocketManager.getInstance();
