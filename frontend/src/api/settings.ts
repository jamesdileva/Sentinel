import { api } from "./client";

export interface SettingItem {
  key: string;
  label: string;
  value: string;
  default: string;
  // Exact provenance (v1.17.19.21, audit B9): "env" is the process
  // environment, "env-file" is the repo's .env. Both override the model
  // default, and the process environment wins over .env — which is why the
  // badge distinguishes them instead of labelling both "env".
  source: "env" | "env-file" | "default";
  secret: boolean;
}

export interface SettingGroup {
  name: string;
  items: SettingItem[];
}

export interface SettingsWarning {
  key: string;
  level: "error" | "warning";
  message: string;
}

export interface SettingsReport {
  generated_at: string;
  version: string;
  groups: SettingGroup[];
  warnings: SettingsWarning[];
}

/** Read-only configuration report (v1.17.18.0): grouped settings with value /
 * default / source plus validation warnings. No writes by design. */
export async function getSettings(): Promise<SettingsReport> {
  const { data } = await api.get<SettingsReport>("/v1/settings");
  return data;
}
