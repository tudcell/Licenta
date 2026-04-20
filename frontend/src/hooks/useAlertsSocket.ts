import { useEffect, useRef } from "react";

import { io, type Socket } from "socket.io-client";

import { env } from "../config/env";

interface AlertsSocketHandlers {
  onAnomalyDetected?: () => void;
  onBlockMined?: () => void;
}

export function useAlertsSocket(accessToken: string | null, handlers: AlertsSocketHandlers): void {
  const handlersRef = useRef<AlertsSocketHandlers>({});

  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

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

      socket.on("anomaly_detected", () => {
        handlersRef.current.onAnomalyDetected?.();
      });
      socket.on("block_mined", () => {
        handlersRef.current.onBlockMined?.();
      });
    } catch {
      // Keep page functional even when websocket fails.
    }

    return () => {
      if (socket) {
        socket.disconnect();
      }
    };
  }, [accessToken]);
}

