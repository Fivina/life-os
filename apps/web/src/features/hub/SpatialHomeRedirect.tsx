import { Navigate, useLocation } from "react-router-dom";
import { spatialView, spatialViewParams } from "./spatialJourney";

/** Keep saved spatial links working after moving the scene to the normal home route. */
export function SpatialHomeRedirect() {
  const { search } = useLocation();
  const params = spatialViewParams(spatialView(new URLSearchParams(search)));
  return <Navigate to={params.size ? `/?${params}` : "/"} replace />;
}
