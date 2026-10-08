import { Navigate, useLocation } from "react-router-dom";

/** Keep bookmarked conversations and draft/context links addressable. */
export function LegacyChatRedirect() {
  const location = useLocation();
  return <Navigate to={{ pathname: "/chat", search: location.search, hash: location.hash }} state={location.state} replace />;
}
