import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { initializeAuthentication } from "./auth";
import "./styles.css";

const root = ReactDOM.createRoot(document.getElementById("root")!);

function AuthenticationError() {
  return (
    <main className="auth-startup" role="alert">
      <h1>No se pudo iniciar la sesión</h1>
      <p>Verifica que Keycloak esté disponible y que el cliente web esté configurado.</p>
      <button className="button button-primary" onClick={() => window.location.reload()}>Reintentar</button>
    </main>
  );
}

root.render(<main className="auth-startup" role="status">Conectando con el inicio de sesión…</main>);

void initializeAuthentication()
  .then(() => root.render(<React.StrictMode><App /></React.StrictMode>))
  .catch(() => root.render(<AuthenticationError />));
