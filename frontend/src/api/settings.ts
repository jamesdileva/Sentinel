import { api } from "./client";

export interface SettingItem {
  key: string;
  label: string;
  value: string;
  default: string;
  source: "env" | "default";
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