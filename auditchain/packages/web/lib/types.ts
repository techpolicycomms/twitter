/**
 * Shared TypeScript types for AuditChain frontend.
 */

export type Role = "ADMIN" | "AUDITOR" | "CLIENT";

export type AuditStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface Organization {
  id: string;
  name: string;
  industry: string;
  website?: string;
}

export interface User {
  id: string;
  email: string;
  role: Role;
  firstName?: string;
  lastName?: string;
  walletAddress?: string;
  orgId: string;
  organization: Organization;
  createdAt: string;
}

export interface AuditScope {
  fairness: boolean;
  explainability: boolean;
  robustness: boolean;
}

export interface FairnessResult {
  score: number;
  demographic_parity: {
    value: number;
    max_gap: number;
    pass: boolean;
    threshold: number;
    selection_rates: Record<string, number>;
  };
  equalized_odds: {
    value: number;
    tpr_gap: number;
    fpr_gap: number;
    pass: boolean;
  };
  disparate_impact: {
    value: number;
    pass: boolean;
    threshold: number;
  };
  summary: string;
}

export interface FeatureImportance {
  name: string;
  importance: number;
}

export interface ExplainResult {
  score: number;
  shap: {
    score: number;
    top_features: FeatureImportance[];
    summary_plot_b64?: string;
  };
  lime: {
    score: number;
    local_explanations: Array<{
      instance_index: number;
      features: Array<{ feature: string; weight: number; direction: string }>;
      prediction_probability: number;
    }>;
  };
  explanation_quality: string;
}

export interface RobustResult {
  score: number;
  adversarial_robustness: number;
  missing_data_handling: string;
  edge_case_failures: number;
  total_tests: number;
  summary: string;
}

export interface Certificate {
  id: string;
  tokenId: number;
  txHash: string;
  ipfsHash: string;
  isRevoked: boolean;
  revokedAt?: string;
  auditId: string;
  issuedAt: string;
}

export interface Audit {
  id: string;
  status: AuditStatus;
  modelHash: string;
  modelType: string;
  modelName: string;
  modelVersion?: string;
  scope: AuditScope;
  fairnessResult?: FairnessResult;
  explainResult?: ExplainResult;
  robustResult?: RobustResult;
  trustScore?: number;
  errorMessage?: string;
  certificate?: Certificate;
  orgId: string;
  organization?: Organization;
  submittedAt: string;
  startedAt?: string;
  completedAt?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  user: User;
}
