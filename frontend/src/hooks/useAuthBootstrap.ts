import { useEffect } from "react";

import { SESSION_EXPIRED_EVENT } from "../services/http";
import { useAuthStore } from "../stores/authStore";

export function useAuthBootstrap(): void {
  const bootstrap = useAuthStore((state) => state.bootstrap);
  const consumeSessionExpired = useAuthStore((state) => state.consumeSessionExpired);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    const onSessionExpired = () => consumeSessionExpired();
    window.addEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
  }, [consumeSessionExpired]);
}

