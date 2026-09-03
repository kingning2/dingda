import { RouterProvider } from "react-router-dom";

import { TooltipProvider } from "@/components/ui/tooltip";
import { BackendProvider } from "@/providers/backend-provider";
import { router } from "@/routes/router";

function App() {
  return (
    <BackendProvider>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </BackendProvider>
  );
}

export default App;
