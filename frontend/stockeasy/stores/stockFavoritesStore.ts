/**
 * 관심기업(즐겨찾기) Zustand 스토어
 * 
 * PM 지시사항에 따른 새로운 관심기업(즐겨찾기) 상태 관리
 * 카테고리별 관리, 정렬순서, 메모 기능 포함
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import StockFavoritesApi, { 
  StockFavorite, 
  StockFavoriteCreate, 
  StockFavoriteUpdate,
  CategoryInfo,
  StockFavoritesByCategory
} from '../app/utils/stockFavoritesApi';

// 스토어 상태 인터페이스
interface StockFavoritesState {
  // 데이터 상태
  favorites: StockFavorite[];
  favoritesByCategory: StockFavoritesByCategory[];
  categories: CategoryInfo[];
  favoriteStockCodes: Set<string>;
  
  // UI 상태
  isLoading: boolean;
  isToggling: boolean;
  error: string | null;
  selectedCategory: string | null;
  
  // 액션 메서드들
  loadFavorites: (category?: string) => Promise<void>;
  loadFavoritesByCategory: () => Promise<void>;
  loadCategories: () => Promise<void>;
  loadFavoriteStockCodes: (category?: string) => Promise<void>;
  
  addFavorite: (favoriteData: StockFavoriteCreate) => Promise<StockFavorite | null>;
  updateFavorite: (favoriteId: number, updateData: StockFavoriteUpdate) => Promise<StockFavorite | null>;
  removeFavorite: (favoriteId: number) => Promise<boolean>;

  
  checkFavorite: (stockCode: string, category?: string) => Promise<boolean>;
  isFavorite: (stockCode: string, category?: string) => boolean;
  reorderFavorites: (category: string, stockCodeOrders: Record<string, number>) => Promise<boolean>;
  
  setSelectedCategory: (category: string | null) => void;
  clearError: () => void;
  reset: () => void;
}

// 초기 상태
const initialState = {
  favorites: [],
  favoritesByCategory: [],
  categories: [],
  favoriteStockCodes: new Set<string>(),
  isLoading: false,
  isToggling: false,
  error: null,
  selectedCategory: null,
};

/**
 * 관심기업(즐겨찾기) Zustand 스토어
 */
export const useStockFavoritesStore = create<StockFavoritesState>()(
  devtools(
    (set, get) => ({
      ...initialState,

      /**
       * 관심기업 목록을 로드합니다.
       * @param category 카테고리명 (선택사항)
       */
      loadFavorites: async (category?: string) => {
        set({ isLoading: true, error: null });
        
        try {
          const favorites = await StockFavoritesApi.getFavorites(category);
          const favoriteStockCodes = new Set(favorites.map(f => f.stock_code));
          
          set({ 
            favorites, 
            favoriteStockCodes,
            isLoading: false 
          });
        } catch (error) {
          console.error('관심기업 목록 로드 실패:', error);
          set({ 
            error: '관심기업 목록을 불러오는데 실패했습니다.',
            isLoading: false 
          });
        }
      },

      /**
       * 카테고리별 관심기업 목록을 로드합니다.
       */
      loadFavoritesByCategory: async () => {
        set({ isLoading: true, error: null });
        
        try {
          const favoritesByCategory = await StockFavoritesApi.getFavoritesByCategory();
          
          // 전체 즐겨찾기 목록도 업데이트
          const allFavorites = favoritesByCategory.flatMap(category => category.favorites);
          const favoriteStockCodes = new Set(allFavorites.map(f => f.stock_code));
          
          set({ 
            favoritesByCategory,
            favorites: allFavorites,
            favoriteStockCodes,
            isLoading: false 
          });
        } catch (error) {
          console.error('카테고리별 관심기업 목록 로드 실패:', error);
          set({ 
            error: '카테고리별 관심기업 목록을 불러오는데 실패했습니다.',
            isLoading: false 
          });
        }
      },

      /**
       * 카테고리 목록을 로드합니다.
       */
      loadCategories: async () => {
        try {
          const categories = await StockFavoritesApi.getCategories();
          set({ categories });
        } catch (error) {
          console.error('카테고리 목록 로드 실패:', error);
          set({ error: '카테고리 목록을 불러오는데 실패했습니다.' });
        }
      },

      /**
       * 관심기업 종목 코드 목록을 로드합니다.
       * @param category 카테고리명 (선택사항)
       */
      loadFavoriteStockCodes: async (category?: string) => {
        try {
          const stockCodes = await StockFavoritesApi.getFavoriteStockCodes(category);
          const favoriteStockCodes = new Set(stockCodes);
          set({ favoriteStockCodes });
        } catch (error) {
          console.error('관심기업 종목 코드 로드 실패:', error);
        }
      },

      /**
       * 관심기업에 종목을 추가합니다.
       * @param favoriteData 추가할 관심기업 정보
       * @returns 생성된 관심기업 정보 또는 null
       */
      addFavorite: async (favoriteData: StockFavoriteCreate) => {
        set({ isLoading: true, error: null });
        
        try {
          const newFavorite = await StockFavoritesApi.addFavorite(favoriteData);
          
          const { favorites, favoriteStockCodes } = get();
          const updatedFavorites = [...favorites, newFavorite];
          const updatedStockCodes = new Set(Array.from(favoriteStockCodes).concat([newFavorite.stock_code]));
          
          set({ 
            favorites: updatedFavorites,
            favoriteStockCodes: updatedStockCodes,
            isLoading: false 
          });
          
          // 카테고리 목록도 업데이트
          get().loadCategories();
          
          return newFavorite;
        } catch (error) {
          console.error('관심기업 추가 실패:', error);
          set({ 
            error: '관심기업 추가에 실패했습니다.',
            isLoading: false 
          });
          return null;
        }
      },

      /**
       * 관심기업 정보를 수정합니다.
       * @param favoriteId 관심기업 ID
       * @param updateData 수정할 정보
       * @returns 수정된 관심기업 정보 또는 null
       */
      updateFavorite: async (favoriteId: number, updateData: StockFavoriteUpdate) => {
        set({ isLoading: true, error: null });
        
        try {
          const updatedFavorite = await StockFavoritesApi.updateFavorite(favoriteId, updateData);
          
          const { favorites } = get();
          const updatedFavorites = favorites.map(f => 
            f.id === favoriteId ? updatedFavorite : f
          );
          
          set({ 
            favorites: updatedFavorites,
            isLoading: false 
          });
          
          return updatedFavorite;
        } catch (error) {
          console.error('관심기업 수정 실패:', error);
          set({ 
            error: '관심기업 수정에 실패했습니다.',
            isLoading: false 
          });
          return null;
        }
      },

      /**
       * 관심기업에서 종목을 제거합니다.
       * @param favoriteId 관심기업 ID
       * @returns 제거 성공 여부
       */
      removeFavorite: async (favoriteId: number) => {
        set({ isLoading: true, error: null });
        
        try {
          const success = await StockFavoritesApi.removeFavorite(favoriteId);
          
          if (success) {
            const { favorites } = get();
            const removedFavorite = favorites.find(f => f.id === favoriteId);
            const updatedFavorites = favorites.filter(f => f.id !== favoriteId);
            
            // 종목 코드 세트에서도 제거 (다른 카테고리에 없는 경우에만)
            const favoriteStockCodes = new Set(updatedFavorites.map(f => f.stock_code));
            
            set({ 
              favorites: updatedFavorites,
              favoriteStockCodes,
              isLoading: false 
            });
            
            // 카테고리 목록도 업데이트
            get().loadCategories();
          }
          
          return success;
        } catch (error) {
          console.error('관심기업 제거 실패:', error);
          set({ 
            error: '관심기업 제거에 실패했습니다.',
            isLoading: false 
          });
          return false;
        }
      },



      /**
       * 특정 종목이 관심기업에 포함되어 있는지 서버에서 확인합니다.
       * @param stockCode 종목 코드
       * @param category 카테고리명 (선택사항)
       * @returns 즐겨찾기 여부
       */
      checkFavorite: async (stockCode: string, category?: string) => {
        try {
          return await StockFavoritesApi.checkFavorite(stockCode, category);
        } catch (error) {
          console.error('관심기업 확인 실패:', error);
          return false;
        }
      },

      /**
       * 로컬 상태에서 특정 종목이 관심기업에 포함되어 있는지 확인합니다.
       * @param stockCode 종목 코드
       * @param category 카테고리명 (선택사항)
       * @returns 즐겨찾기 여부
       */
      isFavorite: (stockCode: string, category?: string) => {
        const { favorites } = get();
        
        if (category) {
          return favorites.some(f => f.stock_code === stockCode && f.category === category);
        } else {
          return favorites.some(f => f.stock_code === stockCode);
        }
      },

      /**
       * 카테고리 내 관심기업들의 순서를 재정렬합니다.
       * @param category 카테고리명
       * @param stockCodeOrders 종목코드와 순서 매핑
       * @returns 재정렬 성공 여부
       */
      reorderFavorites: async (category: string, stockCodeOrders: Record<string, number>) => {
        set({ isLoading: true, error: null });
        
        try {
          const success = await StockFavoritesApi.reorderFavorites(category, stockCodeOrders);
          
          if (success) {
            // 로컬 상태도 업데이트
            await get().loadFavorites();
          }
          
          set({ isLoading: false });
          return success;
        } catch (error) {
          console.error('관심기업 순서 재정렬 실패:', error);
          set({ 
            error: '관심기업 순서 변경에 실패했습니다.',
            isLoading: false 
          });
          return false;
        }
      },

      /**
       * 선택된 카테고리를 설정합니다.
       * @param category 카테고리명 또는 null
       */
      setSelectedCategory: (category: string | null) => {
        set({ selectedCategory: category });
      },

      /**
       * 에러 상태를 초기화합니다.
       */
      clearError: () => {
        set({ error: null });
      },

      /**
       * 스토어 상태를 초기화합니다.
       */
      reset: () => {
        set(initialState);
      },
    }),
    {
      name: 'stock-favorites-store',
    }
  )
);

// 기본 내보내기
export default useStockFavoritesStore;
