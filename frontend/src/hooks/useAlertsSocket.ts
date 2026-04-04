import { useEffect } from "react";

import { io, type Socket } from "socket.io-client";

import { env } from "../config/env";

interface AlertsSocketHandlers {
  onAnomalyDetected?: () => void;
  onBlockMined?: () => void;
}

export function useAlertsSocket(accessToken: string | null, handlers: AlertsSocketHandlers): void {
  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let socket: Socket | null = null;
    try {
      socket = io(`${env.socketUrl}/alerts`, {
        transports: ["websocket"],
        auth: { token: accessToken },
      });

      if (handlers.onAnomalyDetected) {
        socket.on("anomaly_detected", handlers.onAnomalyDetected);
      }
      if (handlers.onBlockMined) {
        socket.on("block_mined", handlers.onBlockMined);
      }
    } catch {
      // Keep page functional even when websocket fails.
    }

    return () => {
      if (socket) {
        socket.disconnect();
      }
    };
  }, [accessToken, handlers.onAnomalyDetected, handlers.onBlockMined]);
}

