import { RouterProvider } from "react-router-dom";

import { AppAlertHost } from "@/components/feedback/app-alert-host";
import { TooltipProvider } from "@v2/ui-primitives/tooltip";
import { ServerProvider } from "@/providers/server-provider";
import { router } from "@/routes/router";

function App() {
  return (
    <ServerProvider>
      <TooltipProvider>
        <RouterProvider router={router} />
        <AppAlertHost />
      </TooltipProvider>
    </ServerProvider>
  );
}

export default App;
