import { Navigate, useNavigate, useParams } from "react-router-dom";

import { AiWorkPage } from "@/pages/ai-work-page";
import { paths } from "@/routes/paths";

export function WorkRoute() {
  const { workId } = useParams();
  const navigate = useNavigate();

  if (!workId) {
    return <Navigate to={paths.home} replace />;
  }

  console.log(workId);
  

  return <AiWorkPage workId={workId} onBack={() => navigate(paths.home)} />;
}
