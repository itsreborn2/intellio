"use client"

import { Droppable, Draggable } from '@hello-pangea/dnd'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Folder, Plus, Trash2, FileText, ChevronDown, ChevronRight, History, AlertCircle } from 'lucide-react'
import * as api from '@/services/api'  // 최상단에 추가
import { IRecentProjectsResponse, IProject, Category } from '@/types/index'
import { getRecentProjects, } from '@/services/api'
import { useRouter } from 'next/navigation'
import { useState, useEffect } from 'react'

import { useApp } from '@/contexts/AppContext'
import { cn } from '@/lib/utils'

import { useAuth } from '@/hooks/useAuth';

interface ProjectCategorySectionProps {
  expandedSections: string[]
  toggleSection: (section: string) => void
  categories: Category[]
  setCategories: React.Dispatch<React.SetStateAction<Category[]>>
  dispatch: any
  onDragEnd: (result: any) => void
  categoryProjects: { [key: string]: IProject[] }  // 추가: 각 카테고리의 프로젝트 목록
}

export function ProjectCategorySection({
  expandedSections,
  toggleSection,
  categories,
  setCategories,
  dispatch,
  onDragEnd,
  categoryProjects
}: ProjectCategorySectionProps) {
  const router = useRouter()
  const { state } = useApp()
  const [isAddingCategory, setIsAddingCategory] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [categoryError, setCategoryError] = useState('')
  const [categoryToDelete, setCategoryToDelete] = useState<Category | null>(null)
  const { isAuthenticated } = useAuth();

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
      
      // 성공 시 상태 업데이트
      setCategories(prev => [...prev, newCategory]);
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
        console.log('최근 프로젝트 로딩');
        const response:IRecentProjectsResponse = await getRecentProjects()
        dispatch({ type: 'UPDATE_RECENT_PROJECTS', payload: response })
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

        console.log('카테고리의 프로젝트 로드')
        // 2. 각 카테고리의 프로젝트 로드
        const projectsPromises = categoriesData.map(async (category) => {
          try {
            
            console.log(` - ${category.name} 폴더(${categoriesData.length}) `);
            const projects = await api.getCategoryProjects(category.id)
            //console.log('카테고리의 프로젝트들:', projects); // 전체 배열 확인
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
        dispatch({ type: 'UPDATE_CATEGORY_PROJECTS', payload: newCategoryProjects })
      } catch (error) {
        console.error('카테고리 로드 실패:', error)
      }
    }

    loadCategoriesAndProjects()
  }, [setCategories, dispatch, isAuthenticated])

  const handleProjectClick = (projectId: string, is_temp: any) => {
    console.log(`Project UUID: ${projectId}, is_temp:${is_temp}`);
    
    // {`category-${category.id}`}
    //임시로 막음. 어차피 동작 안하는데.
    //router.push(`/projects/${projectId}`)
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

  // 드래그 종료 핸들러
  const handleDragEnd = async (result: any) => {
    if (!result.destination) return;

    const sourceId = result.draggableId;
    const destinationId = result.destination.droppableId;

    // 카테고리(영구)로 드롭된 경우
    if (destinationId.startsWith('category-')) {
      const categoryId = destinationId.replace('category-', '');
      try {
        const response = await fetch(`/api/v1/projects/${sourceId}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            category_id: categoryId,
          }),
        });

        if (!response.ok) {
          throw new Error('프로젝트 이동에 실패했습니다.');
        }

        // 프로젝트 목록 새로고침
        const recentProjects:IRecentProjectsResponse= await api.getRecentProjects();
        dispatch({ type: 'UPDATE_RECENT_PROJECTS', payload: recentProjects });
      } catch (error) {
        console.error('프로젝트 이동 실패:', error);
      }
    }
  }

  const truncateTitle = (title: string, maxLength: number = 20) => {
    if (!title) return '(제목 없음)';
    return title.length > maxLength ? `${title.slice(0, maxLength)}...` : title;
  };

  const renderProjects = (projects: IProject[], sectionTitle: string) => {
    if (!Array.isArray(projects) || !projects?.length) return null;

    return (
      <div className="space-y-1">
        <div className="text-xs text-gray-500 px-2">{sectionTitle}</div>
        {projects.map((project, index) => {
          if (!project?.id) return null;
          //console.log('Project object:', project);  // 프로젝트 객체 전체 출력
          
          return (
            <Draggable
              key={project.id}
              draggableId={project.id}
              index={index}
            >
              {(provided, snapshot) => (
                <div
                  ref={provided.innerRef}
                  {...provided.draggableProps}
                  {...provided.dragHandleProps}
                  className={cn(
                    "relative flex items-center cursor-move",
                    snapshot.isDragging && "shadow-lg border-2 border-blue-500",
                    !snapshot.isDragging && "hover:bg-gray-50",
                    "rounded-md transition-all duration-200 ease-in-out"
                  )}
                >
                  <div className="flex-1 px-2 py-1">
                    <Button
                      type="button"
                      variant="ghost"
                      className={cn(
                        "w-full justify-start gap-2 px-2 max-w-full",
                        state.currentProjectId === project.id && "bg-gray-100"
                      )}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleProjectClick(project.id, project.is_temporary);
                      }}
                    >
                      <FileText className={cn(
                        "h-4 w-4 flex-shrink-0",
                        snapshot.isDragging && "text-blue-500"
                      )} />
                      <span className="truncate text-left" title={project.name}>
                        {truncateTitle(project.name, 15)}
                      </span>
                    </Button>
                  </div>
                </div>
              )}
            </Draggable>
          );
        })}
      </div>
    );
  };

  const renderCategoryProjects = (categoryId: string) => {
    const projects = state.categoryProjects[categoryId] || []
    //console.log(`카테고리 ${categoryId}의 프로젝트:`, projects)
    
    return projects.map((project: any, index: number) => (
      <Draggable
        key={project.id}
        draggableId={project.id}
        index={index}
      >
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.draggableProps}
            {...provided.dragHandleProps}
            className={`flex items-center px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 cursor-pointer ${
              state.currentProjectId === project.id ? 'bg-gray-100' : ''
            }`}
            onClick={() => handleProjectClick(project.id, project.is_temporary)}
          >
            <FileText className="w-4 h-4 mr-2" />
            <span className="truncate">{project.name}</span>
          </div>
        )}
      </Draggable>
    ))
  }

  const renderRecentProjects = () => {
    if (!Array.isArray(state.recentProjects?.today) || !state.recentProjects?.today?.length) return null;

    return (
      <div className="space-y-1">
        <div className="text-xs text-gray-500 px-2">최근 프로젝트</div>
        {state.recentProjects.today.map((project, index) => {
          if (!project?.id) return null;
          //console.log('Project object:', project);  // 프로젝트 객체 전체 출력
          
          return (
            <Draggable
              key={project.id}
              draggableId={project.id}
              index={index}
            >
              {(provided, snapshot) => (
                <div
                  ref={provided.innerRef}
                  {...provided.draggableProps}
                  {...provided.dragHandleProps}
                  className={cn(
                    "relative flex items-center cursor-move",
                    snapshot.isDragging && "shadow-lg border-2 border-blue-500",
                    !snapshot.isDragging && "hover:bg-gray-50",
                    "rounded-md transition-all duration-200 ease-in-out"
                  )}
                >
                  <div className="flex-1 px-2 py-1">
                    <Button
                      type="button"
                      variant="ghost"
                      className={cn(
                        "w-full justify-start gap-2 px-2 max-w-full",
                        state.currentProjectId === project.id && "bg-gray-100"
                      )}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleProjectClick(project.id, project.is_temporary);
                      }}
                    >
                      <FileText className={cn(
                        "h-4 w-4 flex-shrink-0",
                        snapshot.isDragging && "text-blue-500"
                      )} />
                      <span className="truncate text-left" title={project.name}>
                        {truncateTitle(project.name, 15)}
                      </span>
                    </Button>
                  </div>
                </div>
              )}
            </Draggable>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col space-y-4">
      {/* 최근 프로젝트 섹션 */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between px-2 py-1">
          <span className="text-sm font-medium text-gray-700">최근 프로젝트</span>
        </div>
        {isAuthenticated ? (
          expandedSections.includes('recent') && (
            <Droppable droppableId="recent-projects" type="PROJECT">
              {(provided, snapshot) => (
                <div
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  className={cn(
                    "space-y-2 min-h-[40px]",
                    snapshot.isDraggingOver && "bg-gray-100/50"
                  )}
                >
                  {state.recentProjects?.today && renderProjects(state.recentProjects.today, '오늘')}
                  {state.recentProjects?.yesterday && renderProjects(state.recentProjects.yesterday, '어제')}
                  {state.recentProjects?.four_days_ago && renderProjects(state.recentProjects.four_days_ago, '4일전')}
                  {provided.placeholder}
                </div>
              )}
            </Droppable>
          )
        ) : (
          <div className="text-center text-gray-500 py-2">
            로그인 후 최근 프로젝트를 볼 수 있습니다.
          </div>
        )}
      </div>

      {/* 프로젝트 폴더 섹션 */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between px-2 py-1">
          <span className="text-sm font-medium text-gray-700">프로젝트 폴더</span>
          {isAuthenticated && (
            <button
              onClick={handleAddCategory}
              className="p-1 text-gray-500 hover:text-gray-700"
            >
              <Plus className="w-4 h-4" />
            </button>
          )}
        </div>
        {isAuthenticated ? (
          <>
            {categories.map(category => (
              <Droppable key={category.id} droppableId={`category-${category.id}`} type="PROJECT">
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={cn(
                      "rounded-md border-2 border-transparent",
                      snapshot.isDraggingOver && "border-blue-500 bg-blue-50",
                      "transition-all duration-200 ease-in-out"
                    )}
                  >
                    <div className="relative flex items-center group">
                      <Button
                        variant="ghost"
                        className={cn(
                          "w-full justify-start text-sm h-8 pl-4",
                          snapshot.isDraggingOver && "bg-blue-50"
                        )}
                      >
                        <Folder className={cn(
                          "h-4 w-4 mr-2",
                          snapshot.isDraggingOver && "text-blue-500"
                        )} />
                        <span className="flex-1 text-left truncate">{category.name}</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 absolute right-0 hover:bg-red-100"
                        onClick={() => setCategoryToDelete(category)}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                    {/* 카테고리 내의 프로젝트 목록 */}
                    <div className="pl-6">
                      {renderCategoryProjects(category.id)}
                    </div>
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            ))}
            
            <Popover open={isAddingCategory} onOpenChange={setIsAddingCategory}>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm h-8 pl-4 text-gray-500 hover:text-gray-900"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  <span className="flex-1 text-left">새 폴더</span>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-72 p-4" align="start">
                <div className="space-y-2">
                  <h4 className="font-semibold text-sm leading-none">새 폴더 만들기</h4>
                  <div className="space-y-2">
                    <div className="relative">
                      <Input
                        type="text"
                        placeholder="폴더 이름을 입력하세요"
                        value={newCategoryName}
                        onChange={(e) => {
                          setNewCategoryName(e.target.value)
                          setCategoryError('')
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && newCategoryName.trim()) {
                            e.preventDefault()
                            handleAddCategory()
                          }
                        }}
                        className="pl-8"
                      />
                      <Folder className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                    </div>
                    {categoryError && (
                      <div className="text-xs text-destructive flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" />
                        {categoryError}
                      </div>
                    )}
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setIsAddingCategory(false)
                        setNewCategoryName('')
                        setCategoryError('')
                      }}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      취소
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleAddCategory}
                      disabled={!newCategoryName.trim()}
                      className="bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white shadow-sm"
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
            로그인 후 프로젝트 목록을 볼 수 있습니다.
          </div>
        )}
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
