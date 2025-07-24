/**
 * 관심기업(즐겨찾기) API 유틸리티
 * 
 * PM 지시사항에 따른 새로운 관심기업(즐겨찾기) 기능을 위한 API 호출 함수들
 * 카테고리별 관리, 정렬순서, 메모 기능 포함
 */

import axios from 'axios';
import { API_ENDPOINT_STOCKEASY } from '../../services/api';

// API 클라이언트 설정
const apiClient = axios.create({
  baseURL: API_ENDPOINT_STOCKEASY,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  }
});

// 타입 정의
export interface StockFavorite {
  id: number;
  user_id: string;
  stock_code: string;
  stock_name?: string;
  category: string;
  display_order: number;
  memo?: string;
  created_at: string;
  updated_at: string;
}

export interface StockFavoriteCreate {
  stock_code: string;
  stock_name?: string;
  category?: string;
  display_order?: number;
  memo?: string;
}

export interface StockFavoriteUpdate {
  stock_name?: string;
  category?: string;
  display_order?: number;
  memo?: string;
}

export interface StockFavoriteToggleRequest {
  stock_code: string;
  stock_name?: string;
  category?: string;
}

export interface StockFavoriteToggleResponse {
  is_favorite: boolean;
  message: string;
  favorite?: StockFavorite;
}

export interface CategoryInfo {
  category: string;
  count: number;
}

export interface StockFavoritesByCategory {
  category: string;
  favorites: StockFavorite[];
}

/**
 * 관심기업(즐겨찾기) API 클래스
 */
export class StockFavoritesApi {
  private static readonly BASE_URL = '/stock-favorites';

  /**
   * 사용자의 관심기업 목록을 조회합니다.
   * @param category 카테고리명 (선택사항)
   * @returns 관심기업 목록
   */
  static async getFavorites(category?: string): Promise<StockFavorite[]> {
    try {
      const params = category ? { category } : {};
      const response = await apiClient.get(this.BASE_URL, { params });
      return response.data;
    } catch (error) {
      console.error('관심기업 목록 조회 실패:', error);
      throw error;
    }
  }

  /**
   * 카테고리별로 그룹화된 관심기업 목록을 조회합니다.
   * @returns 카테고리별 관심기업 목록
   */
  static async getFavoritesByCategory(): Promise<StockFavoritesByCategory[]> {
    try {
      const response = await apiClient.get(`${this.BASE_URL}/by-category`);
      return response.data;
    } catch (error) {
      console.error('카테고리별 관심기업 목록 조회 실패:', error);
      throw error;
    }
  }

  /**
   * 사용자의 카테고리 목록을 조회합니다.
   * @returns 카테고리 정보 목록
   */
  static async getCategories(): Promise<CategoryInfo[]> {
    try {
      const response = await apiClient.get(`${this.BASE_URL}/categories`);
      return response.data;
    } catch (error) {
      console.error('카테고리 목록 조회 실패:', error);
      throw error;
    }
  }

  /**
   * 관심기업에 종목을 추가합니다.
   * @param favoriteData 추가할 관심기업 정보
   * @returns 생성된 관심기업 정보
   */
  static async addFavorite(favoriteData: StockFavoriteCreate): Promise<StockFavorite> {
    try {
      const response = await apiClient.post(this.BASE_URL, favoriteData);
      return response.data;
    } catch (error) {
      console.error('관심기업 추가 실패:', error);
      throw error;
    }
  }

  /**
   * 관심기업 정보를 수정합니다.
   * @param favoriteId 관심기업 ID
   * @param updateData 수정할 정보
   * @returns 수정된 관심기업 정보
   */
  static async updateFavorite(favoriteId: number, updateData: StockFavoriteUpdate): Promise<StockFavorite> {
    try {
      const response = await apiClient.put(`${this.BASE_URL}/${favoriteId}`, updateData);
      return response.data;
    } catch (error) {
      console.error('관심기업 수정 실패:', error);
      throw error;
    }
  }

  /**
   * 관심기업에서 종목을 제거합니다.
   * @param favoriteId 관심기업 ID
   * @returns 제거 성공 여부
   */
  static async removeFavorite(favoriteId: number): Promise<boolean> {
    try {
      await apiClient.delete(`${this.BASE_URL}/${favoriteId}`);
      return true;
    } catch (error) {
      console.error('관심기업 제거 실패:', error);
      throw error;
    }
  }

  /**
   * 관심기업 상태를 토글합니다.
   * @param toggleData 토글할 종목 정보
   * @returns 토글 결과
   */
  static async toggleFavorite(toggleData: StockFavoriteToggleRequest): Promise<StockFavoriteToggleResponse> {
    try {
      const response = await apiClient.post(`${this.BASE_URL}/toggle`, toggleData);
      return response.data;
    } catch (error) {
      console.error('관심기업 토글 실패:', error);
      throw error;
    }
  }

  /**
   * 특정 종목이 관심기업에 포함되어 있는지 확인합니다.
   * @param stockCode 종목 코드
   * @param category 카테고리명 (선택사항)
   * @returns 즐겨찾기 여부
   */
  static async checkFavorite(stockCode: string, category?: string): Promise<boolean> {
    try {
      const params = { stock_code: stockCode, ...(category && { category }) };
      const response = await apiClient.get(`${this.BASE_URL}/check`, { params });
      return response.data.is_favorite;
    } catch (error) {
      console.error('관심기업 확인 실패:', error);
      return false;
    }
  }

  /**
   * 사용자의 관심기업 종목 코드 목록을 조회합니다.
   * @param category 카테고리명 (선택사항)
   * @returns 종목 코드 목록
   */
  static async getFavoriteStockCodes(category?: string): Promise<string[]> {
    try {
      const params = category ? { category } : {};
      const response = await apiClient.get(`${this.BASE_URL}/stock-codes`, { params });
      return response.data;
    } catch (error) {
      console.error('관심기업 종목 코드 조회 실패:', error);
      throw error;
    }
  }

  /**
   * 카테고리 내 관심기업들의 순서를 재정렬합니다.
   * @param category 카테고리명
   * @param stockCodeOrders 종목코드와 순서 매핑
   * @returns 재정렬 성공 여부
   */
  static async reorderFavorites(category: string, stockCodeOrders: Record<string, number>): Promise<boolean> {
    try {
      const response = await apiClient.put(`${this.BASE_URL}/reorder`, {
        category,
        stock_code_orders: Object.entries(stockCodeOrders)
      });
      return response.data.success;
    } catch (error) {
      console.error('관심기업 순서 재정렬 실패:', error);
      throw error;
    }
  }
}

// 기본 내보내기
export default StockFavoritesApi;
