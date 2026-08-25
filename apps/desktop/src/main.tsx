import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app/app";
import { flushHtmlStartupMarks, logStartupPhase } from "./lifecycle/startup-log";

flushHtmlStartupMarks();
logStartupPhase("frontend.js.entry");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

logStartupPhase("frontend.react.mounted");
