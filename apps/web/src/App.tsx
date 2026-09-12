import { RouterProvider } from "react-router-dom";

import { AppAlertHost } from "@v2/ui-feedback/app-alert-host";
import { TooltipProvider } from "@v2/ui-primitives/tooltip";
import { ServerProvider } from "@v2/runtime/server-provider";
import { router } from "@web/routes/router";

import { BootGate } from "./boot/boot-gate";

function App() {
  return (
    <ServerProvider>
      <BootGate>
        <TooltipProvider>
          <RouterProvider router={router} />
          <AppAlertHost />
        </TooltipProvider>
      </BootGate>
    </ServerProvider>
  );
}

export default App;
