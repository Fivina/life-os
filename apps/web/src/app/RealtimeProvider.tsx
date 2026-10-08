import { useQueryClient } from "@tanstack/react-query";
import { createContext, type PropsWithChildren, useContext, useEffect, useState } from "react";

import {
  getRealtimeStateClient,
  type RealtimeConnectionState
} from "../services/realtime";

const RealtimeContext = createContext<RealtimeConnectionState>("OFFLINE");

export function RealtimeProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<RealtimeConnectionState>("CONNECTING");

  useEffect(() => {
    const client = getRealtimeStateClient(queryClient, setState);
    client.start();
    const authChanged = () => client.restart();
    window.addEventListener("life-os:auth-changed", authChanged);
    return () => {
      window.removeEventListener("life-os:auth-changed", authChanged);
      client.stop();
    };
  }, [queryClient]);

  return <RealtimeContext.Provider value={state}>{children}</RealtimeContext.Provider>;
}

export function useRealtimeConnectionState() {
  return useContext(RealtimeContext);
}
