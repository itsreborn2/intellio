/**
 * Represents the structure of a single user statistic record from the API.
 * This should match the Pydantic schema from the backend.
 */
export interface UserStat {
  id: number;
  stat_type: 'HOURLY' | 'DAILY' | 'MONTHLY';
  report_at: string; // ISO 8601 date string
  total_users: number;
  new_users: number;
  active_users: number;
  total_chat_sessions: number;
  new_chat_sessions: number;
  sessions_per_user?: number | null;
  sessions_per_active_user?: number | null;
  active_user_percentage?: number | null;
  created_at: string; // ISO 8601 date string
}

/**
 * Represents the structure for the summary statistics card data, processed for UI display.
 */
export interface SummaryStat {
  title: string;
  value: string;
  change: string;
  changeType: 'increase' | 'decrease' | 'neutral' | 'neutral';
}
