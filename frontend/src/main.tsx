import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import { I18nProvider } from "./i18n";
import ErrorBoundary from "./components/ErrorBoundary";
import PWAUpdater from "./components/PWAUpdater";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <I18nProvider>
        <BrowserRouter>
          <AuthProvider>
            <App />
            {/* R3-B — يعرض توست "نسخة جديدة متاحة" لما deployment جديد ينزل */}
            <PWAUpdater />
          </AuthProvider>
        </BrowserRouter>
      </I18nProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
