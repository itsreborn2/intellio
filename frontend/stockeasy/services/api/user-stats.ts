import { UserStat } from '@/types/api/user-stats';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

/**
 * Fetches user statistics from the backend API.
 * @param statType - The type of statistics to fetch ('DAILY' or 'MONTHLY').
 * @param limit - The number of recent records to fetch.
 * @returns A promise that resolves to an array of UserStat objects.
 */
async function fetchUserStats(statType: 'DAILY' | 'MONTHLY', limit: number): Promise<UserStat[]> {
  const url = `${API_BASE_URL}/stats/users?stat_type=${statType}`;
  
  try {
    const response = await fetch(url, {
      next: { revalidate: 3600 }, // Revalidate every hour
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch ${statType} user stats: ${response.statusText}`);
    }

    const result = await response.json();

    if (!result.success || !Array.isArray(result.data)) {
      throw new Error('Invalid data format received from API');
    }

    // Return only the number of records specified by the limit
    return result.data.slice(0, limit);

  } catch (error) {
    console.error(`Error in fetchUserStats (${statType}):`, error);
    return []; // Return empty array on error to prevent crashes
  }
}

/**
 * Fetches and processes both daily and monthly stats to provide summary data for the admin dashboard.
 * @returns An object containing daily and monthly statistics.
 */
export async function getSummaryData() {
  try {
    const [dailyStats, monthlyStats] = await Promise.all([
      fetchUserStats('DAILY', 2),   // Fetch today's and yesterday's data
      fetchUserStats('MONTHLY', 2), // Fetch this month's and last month's data
    ]);

    return {
      daily: dailyStats,
      monthly: monthlyStats,
    };
  } catch (error) {
    console.error('Error fetching summary data:', error);
    return {
      daily: [],
      monthly: [],
    };
  }
}
