import { apiClient } from "./http";
import { unwrapApiData } from "./apiUtils";
import type { ApiSuccess } from "../types/api";
import type {
  BackupCreatePayload,
  BackupListPayload,
  BackupRestorePayload,
  IntegrityPayload,
} from "../types/audit";

export const auditService = {
  async getIntegrity(): Promise<IntegrityPayload> {
    const response = await apiClient.get<ApiSuccess<IntegrityPayload>>("/api/audit/integrity");
    return unwrapApiData(response);
  },

  async exportAuditLog(): Promise<string> {
    const response = await apiClient.get("/api/audit/export", {
      responseType: "text",
    });
    return response.data as string;
  },

  async listBackups(): Promise<BackupListPayload> {
    const response = await apiClient.get<ApiSuccess<BackupListPayload>>("/api/audit/backups");
    return unwrapApiData(response);
  },

  async createBackup(): Promise<BackupCreatePayload> {
    const response = await apiClient.post<ApiSuccess<BackupCreatePayload>>("/api/audit/backup", {});
    return unwrapApiData(response);
  },

  async restoreBackup(snapshotName: string): Promise<BackupRestorePayload> {
    const response = await apiClient.post<ApiSuccess<BackupRestorePayload>>("/api/audit/restore", {
      snapshot_name: snapshotName,
    });
    return unwrapApiData(response);
  },

  async downloadBackup(snapshotName: string): Promise<Blob> {
    const response = await apiClient.get(`/api/audit/backups/${encodeURIComponent(snapshotName)}/download`, {
      responseType: "blob",
    });
    return response.data as Blob;
  },
};

