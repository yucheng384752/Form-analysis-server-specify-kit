/** P1 / P2 / P3 record type discriminator. */
export type DataType = 'P1' | 'P2' | 'P3';

/** Tenant row from the API. */
export type TenantRow = {
  id: string;
  name?: string;
  code?: string;
  is_active?: boolean;
  is_default?: boolean;
};

/** /auth/whoami response shape. */
export type WhoAmI = {
  is_admin: boolean;
  tenant_id?: string | null;
  actor_user_id?: string | null;
  actor_role?: string | null;
  api_key_label?: string | null;
  must_change_password?: boolean;
};
