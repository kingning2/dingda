import { RouterProvider } from "react-router-dom";

import { TooltipProvider } from "@/components/ui/tooltip";
import { ServerProvider } from "@/providers/server-provider";
import { router } from "@/routes/router";

function App() {
  return (
    <ServerProvider>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </ServerProvider>
  );
}

export default App;
