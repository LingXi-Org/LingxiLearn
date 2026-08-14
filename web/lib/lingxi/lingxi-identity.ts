"use client";

import {
  setAccessTokenProvider,
  setAccessTokenRefreshHandler,
  type AccessTokenProvider,
} from '@/lib/lingxi/api'

const PKCE_TRANSACTION_KEY = "lingxilearn.oidc.pkce";
const DEFAULT_SCOPE = "openid profile email offline_access roles urn:logto:scope:organizations urn:logto:scope:organization_roles learn.read learn.write";
const TOKEN_STORAGE_KEY = "lingxilearn.oidc.tokens";

export interface LingxiIdentityConfig {
  issuer: string;
  clientId: string;
  resource: string;
  redirectUri: string;
  scope?: string;
}

interface DiscoveryDocument {
  authorization_endpoint: string;
  token_endpoint: string;
  userinfo_endpoint?: string;
  end_session_endpoint?: string;
}

interface TokenResponse {
  access_token: string;
  token_type?: string;
  expires_in?: number;
  refresh_token?: string;
  id_token?: string;
}

interface StoredTransaction {
  state: string;
  codeVerifier: string;
  nonce: string;
  redirectUri: string;
  createdAt: number;
}

interface TokenSet {
  accessToken: string;
  refreshToken?: string;
  idToken?: string;
  expiresAt: number;
}

export interface LingxiIdentityUser {
  id: string;
  email?: string;
  name?: string;
  picture?: string;
  emailVerified?: boolean;
}

function base64Url(bytes: Uint8Array): string {
  let value = "";
  for (const byte of bytes) value += String.fromCharCode(byte);
  return btoa(value).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(size = 32): string {
  const bytes = new Uint8Array(size);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return base64Url(new Uint8Array(digest));
}

function requiredEnv(name: string, value: string | undefined): string {
  if (!value) throw new Error(`缺少 LingxiIdentity 配置：${name}`);
  return value;
}

export function lingxiIdentityConfig(): LingxiIdentityConfig {
  return {
    issuer: requiredEnv("NEXT_PUBLIC_LINGXI_IDENTITY_ISSUER", process.env.NEXT_PUBLIC_LINGXI_IDENTITY_ISSUER).replace(/\/$/, ""),
    clientId: requiredEnv("NEXT_PUBLIC_LINGXI_IDENTITY_CLIENT_ID", process.env.NEXT_PUBLIC_LINGXI_IDENTITY_CLIENT_ID),
    resource: requiredEnv("NEXT_PUBLIC_LINGXI_IDENTITY_RESOURCE", process.env.NEXT_PUBLIC_LINGXI_IDENTITY_RESOURCE),
    redirectUri: process.env.NEXT_PUBLIC_LINGXI_IDENTITY_REDIRECT_URI || `${window.location.origin}/auth/callback/`,
    scope: process.env.NEXT_PUBLIC_LINGXI_IDENTITY_SCOPE || DEFAULT_SCOPE,
  };
}

export class LingxiIdentityClient {
  private discovery?: Promise<DiscoveryDocument>;
  private tokens: TokenSet | null = null;
  private releaseProvider: (() => void) | null = null;
  private refreshPromise: Promise<string | null> | null = null;
  private releaseRefreshProvider: (() => void) | null = null;
  private readonly storage: Storage | null =
    typeof window === "undefined" ? null : window.sessionStorage;

  constructor(private readonly config: LingxiIdentityConfig) {
    this.tokens = this.readTokens();
  }

  private readTokens(): TokenSet | null {
    try {
      const raw = this.storage?.getItem(TOKEN_STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as TokenSet;
      if (!parsed.accessToken || !parsed.expiresAt) return null;
      return parsed;
    } catch {
      return null;
    }
  }

  private persistTokens(): void {
    if (!this.storage) return;
    if (!this.tokens) {
      this.storage.removeItem(TOKEN_STORAGE_KEY);
      return;
    }
    this.storage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(this.tokens));
  }

  private clearTokens(): void {
    this.tokens = null;
    this.persistTokens();
  }

  private async metadata(): Promise<DiscoveryDocument> {
    this.discovery ??= fetch(`${this.config.issuer}/.well-known/openid-configuration`).then(async (response) => {
      if (!response.ok) throw new Error(`LingxiIdentity discovery failed (${response.status})`);
      return response.json() as Promise<DiscoveryDocument>;
    });
    return this.discovery;
  }

  async login(): Promise<void> {
    const state = randomString();
    const codeVerifier = randomString(48);
    const nonce = randomString();
    const transaction: StoredTransaction = { state, codeVerifier, nonce, redirectUri: this.config.redirectUri, createdAt: Date.now() };
    sessionStorage.setItem(PKCE_TRANSACTION_KEY, JSON.stringify(transaction));
    const metadata = await this.metadata();
    const params = new URLSearchParams({
      response_type: "code",
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      scope: this.config.scope || DEFAULT_SCOPE,
      state,
      nonce,
      code_challenge: await sha256(codeVerifier),
      code_challenge_method: "S256",
      resource: this.config.resource,
    });
    window.location.assign(`${metadata.authorization_endpoint}?${params}`);
  }

  async handleCallback(): Promise<boolean> {
    const query = new URLSearchParams(window.location.search);
    const error = query.get("error");
    if (error) throw new Error(query.get("error_description") || error);
    const code = query.get("code");
    if (!code) return false;
    const raw = sessionStorage.getItem(PKCE_TRANSACTION_KEY);
    sessionStorage.removeItem(PKCE_TRANSACTION_KEY);
    if (!raw) throw new Error("登录状态已过期，请重新登录。");
    const transaction = JSON.parse(raw) as StoredTransaction;
    if (!transaction.state || transaction.state !== query.get("state") || Date.now() - transaction.createdAt > 10 * 60 * 1000) {
      throw new Error("登录状态校验失败，请重新登录。");
    }
    const metadata = await this.metadata();
    await this.exchange(metadata.token_endpoint, { grant_type: "authorization_code", code, redirect_uri: transaction.redirectUri, client_id: this.config.clientId, code_verifier: transaction.codeVerifier, nonce: transaction.nonce });
    return true;
  }

  private async exchange(endpoint: string, params: Record<string, string>): Promise<void> {
    const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" }, body: new URLSearchParams({ ...params, resource: this.config.resource }) });
    if (!response.ok) throw new Error(`LingxiIdentity token request failed (${response.status})`);
    const body = await response.json() as TokenResponse;
    if (!body.access_token) throw new Error("LingxiIdentity 未返回 access token。");
    this.tokens = { accessToken: body.access_token, refreshToken: body.refresh_token || this.tokens?.refreshToken, idToken: body.id_token || this.tokens?.idToken, expiresAt: Date.now() + Math.max((body.expires_in ?? 300) - 30, 1) * 1000 };
    this.persistTokens();
  }

  async accessToken(): Promise<string | null> {
    if (!this.tokens) return null;
    if (Date.now() < this.tokens.expiresAt) return this.tokens.accessToken;
    if (!this.tokens.refreshToken) return null;
    if (!this.refreshPromise) {
      this.refreshPromise = this.refresh().finally(() => { this.refreshPromise = null; });
    }
    return this.refreshPromise;
  }

  private async refresh(): Promise<string | null> {
    const refreshToken = this.tokens?.refreshToken;
    if (!refreshToken) return null;
    try {
      const metadata = await this.metadata();
      await this.exchange(metadata.token_endpoint, { grant_type: "refresh_token", refresh_token: refreshToken, client_id: this.config.clientId });
      return this.tokens?.accessToken ?? null;
    } catch {
      this.clearTokens();
      return null;
    }
  }

  mountTokenProvider(): void {
    this.releaseProvider?.();
    const provider: AccessTokenProvider = () => this.accessToken();
    this.releaseProvider = setAccessTokenProvider(provider);
    this.releaseRefreshProvider?.();
    this.releaseRefreshProvider = setAccessTokenRefreshHandler(async () => {
      await this.refresh();
    });
  }

  hasSession(): boolean {
    return Boolean(this.tokens);
  }

  async user(): Promise<LingxiIdentityUser | null> {
    const token = await this.accessToken();
    if (!token) return null;
    const metadata = await this.metadata();
    if (!metadata.userinfo_endpoint) return null;
    const response = await fetch(metadata.userinfo_endpoint, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    const body = (await response.json()) as Record<string, unknown>;
    return {
      id: String(body.sub ?? ""),
      email: typeof body.email === "string" ? body.email : undefined,
      name: typeof body.name === "string" ? body.name : undefined,
      picture: typeof body.picture === "string" ? body.picture : undefined,
      emailVerified: body.email_verified === true,
    };
  }

  async logout(): Promise<void> {
    const idToken = this.tokens?.idToken;
    this.clearTokens();
    const metadata = await this.metadata();
    if (!metadata.end_session_endpoint) return;
    const params = new URLSearchParams({ post_logout_redirect_uri: window.location.origin, client_id: this.config.clientId });
    if (idToken) params.set("id_token_hint", idToken);
    window.location.assign(`${metadata.end_session_endpoint}?${params}`);
  }

  dispose(): void {
    this.releaseProvider?.();
    this.releaseProvider = null;
    this.releaseRefreshProvider?.();
    this.releaseRefreshProvider = null;
  }
}

export function createLingxiIdentityClient(): LingxiIdentityClient {
  const client = new LingxiIdentityClient(lingxiIdentityConfig());
  client.mountTokenProvider();
  return client;
}
