import { Navigate, useNavigate, useParams } from "react-router-dom";

import { AiWorkPage } from "@web/pages/ai-work-page";
import { paths } from "@v2/routes/paths";

export function WorkRoute() {
  const { workId } = useParams();
  const navigate = useNavigate();

  if (!workId) {
    return <Navigate to={paths.home} replace />;
  }

  return <AiWorkPage workId={workId} onBack={() => navigate(paths.home)} />;
}
