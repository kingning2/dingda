import { useNavigate } from "react-router-dom";

import { ErrorTestPage } from "@web/pages/error-test-page";
import { NotFoundPage, NotImplementedPage } from "@web/pages/status-pages";
import { paths } from "@v2/routes/paths";

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
