import { useNavigate } from "react-router-dom";

import { ErrorTestPage } from "@/pages/error-test-page";
import { NotFoundPage, NotImplementedPage } from "@/pages/status-pages";
import { paths } from "@/routes/paths";

export function ErrorTestRoute() {
  const navigate = useNavigate();
  return <ErrorTestPage onBack={() => navigate(paths.home)} />;
}

export function NotFoundRoute() {
  const navigate = useNavigate();
  return <NotFoundPage onBack={() => navigate(paths.home)} />;
}

export function NotImplementedRoute() {
  const navigate = useNavigate();
  return <NotImplementedPage onBack={() => navigate(paths.home)} />;
}
