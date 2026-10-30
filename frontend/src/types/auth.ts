export interface AuthUser {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthCredentials {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
}
