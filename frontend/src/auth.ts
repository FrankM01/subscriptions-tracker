import Keycloak, { type KeycloakInstance } from "keycloak-js";

type PublicAuthConfig = {
  enabled: boolean;
  url?: string;
  realm?: string;
  clientId?: string;
};

let keycloak: KeycloakInstance | null = null;

export async function initializeAuthentication(): Promise<void> {
  const response = await fetch("/auth/config");
  if (!response.ok) {
    throw new Error("No se pudo cargar la configuración de inicio de sesión.");
  }

  const config = (await response.json()) as PublicAuthConfig;
  if (!config.enabled) return;
  if (!config.url || !config.realm || !config.clientId) {
    throw new Error("La configuración de inicio de sesión está incompleta.");
  }

  keycloak = new Keycloak({ url: config.url, realm: config.realm, clientId: config.clientId });
  const authenticated = await keycloak.init({
    onLoad: "login-required",
    pkceMethod: "S256",
  });
  if (!authenticated) {
    throw new Error("No se pudo establecer una sesión autenticada.");
  }
}

export async function getAccessToken(): Promise<string | undefined> {
  if (!keycloak) return undefined;
  try {
    await keycloak.updateToken(30);
  } catch {
    keycloak.clearToken();
    await keycloak.login({ redirectUri: window.location.href });
    throw new Error("La sesión expiró. Inicia sesión nuevamente.");
  }
  return keycloak.token;
}

export function getAuthenticatedUserLabel(): string | undefined {
  const token = keycloak?.tokenParsed;
  if (!token) return undefined;
  return token.preferred_username ?? token.email ?? "Cuenta";
}

export async function logout(): Promise<void> {
  if (!keycloak) return;
  await keycloak.logout({ redirectUri: window.location.origin });
}
