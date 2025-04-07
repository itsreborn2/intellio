"use client"

import { Droppable, Draggable } from '@hello-pangea/dnd'
import { Button } from 'intellio-common/components/ui/button'
import { Input } from 'intellio-common/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from 'intellio-common/components/ui/dialog'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from 'intellio-common/components/ui/popover'
import { Folder, FolderOpen, Plus, Trash2, ChevronDown, ChevronRight, History, AlertCircle, FileText, X, MessageSquare, Check } from 'lucide-react'
import * as api from '@/services/api'  // 최상단에 추가
import { IRecentProjectsResponse, IProject, Category, ProjectDetail, TableResponse,  } from '@/types/index'
import { getRecentProjects, } from '@/services/api'
import { useRouter } from 'next/navigation'
import { useState, useEffect, Suspense, MutableRefObject } from 'react'

import { useApp } from '@/contexts/AppContext'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth';
import * as actionTypes from '@/types/actions'

interface ProjectCategorySectionProps {
  expandedSections: string[]
  toggleSection: (section: string) => void
  categories: Category[]
  setCategories: React.Dispatch<React.SetStateAction<Category[]>>
  dispatch: any
  onDragEnd: (result: any) => void
  categoryProjects: { [key: string]: IProject[] }  // 추가: 각 카테고리의 프로젝트 목록
  setCategoryProjects: React.Dispatch<React.SetStateAction<{ [key: string]: IProject[] }>>
  closeMenuOnProjectSelect: () => void  // 추가: 프로젝트 선택 시 메뉴 닫기 함수
  handleProjectClickRef?: MutableRefObject<((project: IProject) => Promise<void>) | null> // 추가: handleProjectClick 함수 ref
}

// 개별 카테고리 컴포넌트
const CategoryItem = ({ 
  category, 
  isExpanded, 
  toggleSection, 
  handleCategoryNameSubmit,
  setCategoryToDelete,
  projects,
  renderProjects
}: { 
  category: Category; 
  isExpanded: boolean; 
  toggleSection: (section: string) => void;
  handleCategoryNameSubmit: (categoryId: string, categoryName: string) => Promise<void>;
  setCategoryToDelete: React.Dispatch<React.SetStateAction<Category | null>>;
  projects: IProject[];
  renderProjects: (projects: IProject[], categoryId: string) => React.ReactNode;
}) => {
  const [isEditingLocal, setIsEditingLocal] = useState(false);
  const [localEditingName, setLocalEditingName] = useState(category.name);

  return (
    <div className="rounded-md overflow-hidden">
      <Droppable
        droppableId={`category-${category.id}`}
        type="PROJECT"
      >
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            className={cn(
              "transition-colors",
              snapshot.isDraggingOver && "bg-gray-50"
            )}
          >
            <div 
              className={cn(
                "flex items-center justify-between py-2 px-2 cursor-pointer hover:bg-[#3F424A] group"
              )}
              onClick={() => toggleSection(category.id)}
              onDoubleClick={() => !isEditingLocal && setIsEditingLocal(true)}
            >
              <div className="flex items-center flex-grow gap-2">
                {isExpanded ? 
                  <ChevronDown className="h-4 w-4 text-[#ABABAB] flex-shrink-0" /> : 
                  <ChevronRight className="h-4 w-4 text-[#ABABAB] flex-shrink-0" />
                }
                {isExpanded ? 
                  <FolderOpen className="h-4 w-4 text-[#ABABAB] flex-shrink-0" /> : 
                  <Folder className="h-4 w-4 text-[#ABABAB] flex-shrink-0" />
                }
                {isEditingLocal ? (
                  <Input
                    value={localEditingName}
                    onChange={(e) => setLocalEditingName(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleCategoryNameSubmit(category.id, localEditingName);
                        setIsEditingLocal(false);
                      }
                    }}
                    className="h-7 text-sm py-0 px-2"
                    autoFocus
                  />
                ) : (
                  <span className="font-medium text-sm text-[#ABABAB]">{category.name}</span>
                )}
              </div>
              
              <div className="flex items-center">
                {isEditingLocal ? (
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCategoryNameSubmit(category.id, localEditingName);
                        setIsEditingLocal(false);
                      }}
                    >
                      <Check className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        setLocalEditingName(category.name);
                        setIsEditingLocal(false);
                      }}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      setCategoryToDelete(category);
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-[#ABABAB]" />
                  </Button>
                )}
              </div>
            </div>
            
            {isExpanded && renderProjects(projects, category.id)}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </div>
  );
};

// 프로젝트 카테고리 섹션 컨텐츠 컴포넌트
function ProjectCategorySectionContent({
  expandedSections,
  toggleSection,
  categories,
  setCategories,
  dispatch,
  onDragEnd,
  categoryProjects,
  setCategoryProjects,
  closeMenuOnProjectSelect,
  handleProjectClickRef
}: ProjectCategorySectionProps) {
  const router = useRouter()
  const { state } = useApp()
  const [isAddingCategory, setIsAddingCategory] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [categoryError, setCategoryError] = useState('')
  const [categoryToDelete, setCategoryToDelete] = useState<Category | null>(null)
  const { isAuthenticated } = useAuth();
  const [isLoading, setIsLoading] = useState(false);

  // 카테고리 이름 중복 체크
  const isCategoryNameDuplicate = (name: string) => {
    return categories.some(category => category.name === name)
  }
  //console.log('Rendering projects:', { sectionTitle, projects });
  //console.log('ProjectCategorySection : ', { categories })
  // 카테고리 추가 핸들러
  const handleAddCategory = async () => {
    if (!isAuthenticated) {  
      console.warn('로그인되지 않았습니다.');
      return;
    }
    if (!newCategoryName.trim()) {
      setCategoryError('폴더 이름을 입력해주세요.');
      return;
    }

    try {
      // api 서비스를 사용하도록 수정
      const newCategory = await api.createCategory(newCategoryName.trim());
      
      // 성공 시 상태 업데이트 - projects_count 추가
      setCategories(prev => [...prev, { ...newCategory, projects_count: 0 }]);
      setNewCategoryName('');
      setIsAddingCategory(false);
      setCategoryError('');
      
    } catch (error) {
      console.error('폴더 생성 실패:', error);
      
      // 에러 메시지 처리 개선
      let errorMessage = '폴더 생성에 실패했습니다.';
      if (error instanceof Error) {
        if (error.message.includes('ECONNREFUSED')) {
          errorMessage = '서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.';
        } else {
          errorMessage = error.message;
        }
      }
      
      setCategoryError(errorMessage);
      
      // 서버 연결 실패 시 자동으로 팝업 닫기
      if (error instanceof Error && error.message.includes('ECONNREFUSED')) {
        setTimeout(() => {
          setIsAddingCategory(false);
          setCategoryError('');
        }, 3000);
      }
    }
  };

  useEffect(() => {
    const fetchRecentProjects = async () => {
      try {
        if (!isAuthenticated) {  
          //console.warn('로그인되지 않았습니다.');
          return;
        }
        console.debug('최근 프로젝트 로딩');
        const response:IRecentProjectsResponse = await getRecentProjects()
        dispatch({ type: actionTypes.UPDATE_RECENT_PROJECTS, payload: response })
      } catch (error) {
        console.error('최근 프로젝트 목록을 가져오는데 실패했습니다:', error)
      }
    }

    // 컴포넌트 마운트 시와 currentProject가 변경될 때 프로젝트 목록 새로고침
    fetchRecentProjects()
  }, [dispatch, state.currentProjectId, isAuthenticated])

  useEffect(() => {
    const loadCategoriesAndProjects = async () => {
      if (!isAuthenticated) {  
        setCategories([]);
        return;
      }

      try {
        console.log('카테(영구) 목록 로드')
        // 1. 카테고리 목록 로드
        const categoriesData = await api.getCategories()
        setCategories(categoriesData)

        console.log('[loadCategoriesAndProjects] 카테고리의 프로젝트 로드')
        // 2. 각 카테고리의 프로젝트 로드
        const projectsPromises = categoriesData.map(async (category) => {
          try {
            
            console.log(` - ${category.name} 폴더(${categoriesData.length}) `);
            const projects = await api.getCategoryProjects(category.id)
            //console.log('카테고리의 프로젝트들:', projects); // 전체 배열 확인
            category.projects_count = projects.length
            console.log(` 개수 : ${projects.length}개`)
            projects.forEach((project: IProject) => {
              console.log(`   - 영구프로젝트 : ID:${project.id}, title:${project.name}, temp:${project.is_temporary}`);
            });
            return { categoryId: category.id, projects }
          } catch (error) {
            console.error(`카테고리 ${category.id}의 프로젝트 로드 실패:`, error)
            return { categoryId: category.id, projects: [] }
          }
        })

        const projectsResults = await Promise.all(projectsPromises)
        
        // categoryProjects 상태 업데이트
        const newCategoryProjects = projectsResults.reduce((acc, { categoryId, projects }) => {
          acc[categoryId] = projects
          return acc
        }, {} as { [key: string]: IProject[] })

        // categoryProjects 상태 업데이트
        setCategoryProjects(newCategoryProjects)
      } catch (error) {
        console.error('카테고리 로드 실패:', error)
      }
    }

    loadCategoriesAndProjects()
  }, [setCategories, dispatch, isAuthenticated, setCategoryProjects])

  // 프로젝트 클릭 처리 함수를 ref에 등록
  useEffect(() => {
    if (handleProjectClickRef) {
      handleProjectClickRef.current = handleProjectClick;
    }
  }, [handleProjectClickRef]);

  const handleProjectClick = async (project: IProject) => {
    setIsLoading(true);
    try {
      // 프로젝트 정보 가져오기
      const projectInfo = await api.getProjectInfo(project.id)
      console.log(`handleProjectClick current view: ${state.currentView}`)
      
      // 현재 view가 upload인 경우에만 chat으로 변경, 나머지는 유지
      if (state.currentView === 'upload') {
        dispatch({ type: actionTypes.SET_VIEW, payload: 'chat' })
      }

      dispatch({ type: actionTypes.SET_CURRENT_PROJECT, payload: projectInfo })
      dispatch({ type: actionTypes.SET_PROJECT_TITLE, payload: projectInfo.name })

      // 채팅 메시지 초기화
      dispatch({ type: actionTypes.CLEAR_CHAT_MESSAGE })
      
      // 문서 목록 요청
      const documents = await api.getDocumentList(project.id)
      dispatch({ type: actionTypes.SET_DOCUMENT_LIST, payload: documents })

      // 테이블 히스토리 요청
      try {
        const tableHistory:TableResponse = await api.getTableHistory(project.id)
        console.log('테이블 히스토리 로드 결과:', tableHistory)
        dispatch({ type: actionTypes.UPDATE_TABLE_DATA, payload: tableHistory })
      } catch (error) {
        console.error('테이블 히스토리 로드 실패:', error)
      }
      
      // 문서 목록 로드 후, 현재 모드에 맞게 문서 선택 상태 설정
      if (state.analysis.mode === 'table') {
        const documentIds = Object.values(documents)
          .filter(doc => doc.project_id === project.id)
          .map(doc => doc.id);
          
        dispatch({ 
          type: actionTypes.SELECT_DOCUMENTS, 
          payload: documentIds 
        });
      }
      
      // 모바일에서 메뉴 닫기
      closeMenuOnProjectSelect();
    } catch (error) {
      console.error('프로젝트 로드 실패:', error);
    } finally {
      setIsLoading(false);
    }
  }

  const handleDeleteCategory = async () => {
    if (!categoryToDelete) return;

    try {
      
      console.log('카테고리 : ', categoryToDelete)
      console.log('카테고리ID : ', categoryToDelete.id)
      await api.deleteCategory(categoryToDelete.id);
      
      // 성공적으로 삭제된 경우에만 상태 업데이트
      setCategories(prev => prev.filter(c => c.id !== categoryToDelete.id));
      setCategoryToDelete(null);
      
      // 선택적: 성공 메시지 표시
      console.log('폴더가 성공적으로 삭제되었습니다.');
      
    } catch (error) {
      console.error('카테고리 삭제 실패:', error);
      
      // 에러 메시지 처리
      let errorMessage = '폴더 삭제에 실패했습니다.';
      if (error instanceof Error) {
        if (error.message.includes('ECONNREFUSED')) {
          errorMessage = '서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.';
        } else {
          errorMessage = error.message;
        }
      }
      
      // 에러 상태 설정 (UI에 표시하려면 상태 변수 추가 필요)
      console.error(errorMessage);
    }
  };

  // 프로젝트 삭제 처리
  const handleDeleteProject = async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // 클릭 이벤트 전파 방지
    
    try {
      await api.deleteProject(projectId);
      
      // 최근 프로젝트 목록에서 제거
      dispatch({
        type: actionTypes.UPDATE_RECENT_PROJECTS,
        payload: {
          today: (state.recentProjects.today || []).filter(p => p.id !== projectId),
          last_7_days: (state.recentProjects.last_7_days || []).filter(p => p.id !== projectId),
          last_30_days: (state.recentProjects.last_30_days || []).filter(p => p.id !== projectId)
        }
      });
      
      // 카테고리 프로젝트 목록에서 제거
      setCategoryProjects(prev => {
        const newCategoryProjects = { ...prev };
        Object.keys(newCategoryProjects).forEach(categoryId => {
          newCategoryProjects[categoryId] = newCategoryProjects[categoryId].filter(
            p => p.id !== projectId
          );
        });
        return newCategoryProjects;
      });

      // 현재 프로젝트가 삭제된 프로젝트인 경우 앱의 상태를 초기화
      if (state.currentProjectId === projectId) {
        dispatch({ type: 'SET_INITIAL_STATE' });
      }
    } catch (error) {
      console.error('프로젝트 삭제 실패:', error);
    }
  };

  const truncateTitle = (title: string, maxLength: number = 20) => {
    if (!title) return '(제목 없음)';
    return title.length > maxLength ? `${title.slice(0, maxLength)}...` : title;
  };

  // 카테고리 이름 수정 시작
  const handleCategoryDoubleClick = (category: Category) => {
    setIsAddingCategory(true);
  };

  // 카테고리 이름 수정 취소
  const handleCategoryEditCancel = (category: Category) => {
    setIsAddingCategory(false);
  };

  // 카테고리 이름 수정 완료
  const handleCategoryNameSubmit = async (categoryId: string, categoryName: string) => {
    try {
      // 수정된 카테고리 업데이트
      await api.updateCategory(categoryId, { name: categoryName });
      
      // 성공적으로 업데이트된 경우 카테고리 목록 업데이트
      setCategories(prev => prev.map(c => 
        c.id === categoryId ? { ...c, name: categoryName } : c
      ));
    } catch (error) {
      console.error('카테고리 이름 수정 실패:', error);
    } finally {
      setIsAddingCategory(false);
    }
  };

  // 프로젝트 렌더링 함수
  const renderProjects = (projects: IProject[], categoryId: string) => {
    return (
      <div className="space-y-1 pl-2 pr-1 py-1">
        {projects.map((project, index) => (
          <Draggable key={project.id} draggableId={project.id} index={index}>
            {(provided, snapshot) => (
              <div
                ref={provided.innerRef}
                {...provided.draggableProps}
                {...provided.dragHandleProps}
                className={cn(
                  "flex items-center gap-2 w-full text-left px-3 py-2 rounded-md transition-colors group",
                  snapshot.isDragging ? "bg-blue-100" : "hover:bg-[#3F424A]"
                )}
                onClick={() => handleProjectClick(project)}
              >
                <MessageSquare className="h-4 w-4 text-[#ABABAB] flex-shrink-0" />
                <span className="text-sm truncate flex-grow text-[#ABABAB]">{project.name}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 ml-auto"
                  onClick={(e) => handleDeleteProject(project.id, e)}
                >
                  <Trash2 className="h-4 w-4 text-[#ABABAB]" />
                </Button>
              </div>
            )}
          </Draggable>
        ))}
        {projects.length === 0 && (
          <div className="text-xs text-[#ABABAB] italic py-1 px-3">저장된 프로젝트 없음</div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* 카테고리 헤더 */}
      <div className="flex items-center justify-between px-2 py-1">
        <span className="text-sm text-[#F4F4F4] uppercase">폴더 목록</span>
        
        {isAuthenticated ? (
          <>
            <Popover open={isAddingCategory} onOpenChange={setIsAddingCategory}>
              <PopoverTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="px-2 h-7"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-72 p-3" align="end">
                <div className="space-y-3">
                  <div>
                    <div className="text-sm font-medium mb-2">새 폴더 추가</div>
                    <Input
                      placeholder="폴더 이름 입력"
                      value={newCategoryName}
                      onChange={(e) => {
                        setNewCategoryName(e.target.value);
                        setCategoryError('');
                      }}
                      className="w-full"
                    />
                    {categoryError && (
                      <div className="text-xs text-red-500 mt-1 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        {categoryError}
                      </div>
                    )}
                  </div>
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      onClick={handleAddCategory}
                      disabled={!newCategoryName.trim()}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white"
                    >
                      생성
                    </Button>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </>
        ) : (
          <div className="text-center text-gray-500 py-2">
            
          </div>
        )}
      </div>
      
      {/* 카테고리 목록 */}
      <div className="space-y-1">
        {categories.map(category => (
          <CategoryItem
            key={category.id}
            category={category}
            isExpanded={expandedSections.includes(category.id)}
            toggleSection={toggleSection}
            handleCategoryNameSubmit={handleCategoryNameSubmit}
            setCategoryToDelete={setCategoryToDelete}
            projects={categoryProjects[category.id] || []}
            renderProjects={renderProjects}
          />
        ))}
      </div>

      {/* 삭제 확인 다이얼로그 */}
      <Dialog open={!!categoryToDelete} onOpenChange={() => setCategoryToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>폴더 삭제</DialogTitle>
            <DialogDescription>
              '{categoryToDelete?.name}' 폴더를 삭제하시겠습니까?
              <br />
              폴더 안의 모든 프로젝트가 기본 위치로 이동됩니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCategoryToDelete(null)}
            >
              취소
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteCategory}
            >
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// 프로젝트 카테고리 섹션 컴포넌트
export function ProjectCategorySection(props: ProjectCategorySectionProps) {
  return (
    <Suspense fallback={<div className="space-y-2 animate-pulse">
      <div className="h-6 bg-gray-200 rounded w-3/4"></div>
      <div className="h-4 bg-gray-200 rounded w-1/2"></div>
      <div className="h-4 bg-gray-200 rounded w-2/3"></div>
    </div>}>
      <ProjectCategorySectionContent {...props} />
    </Suspense>
  )
}
