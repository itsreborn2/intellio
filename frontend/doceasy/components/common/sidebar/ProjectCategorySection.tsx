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
import { Folder, FolderOpen, Plus, Trash2, ChevronDown, ChevronRight, History, AlertCircle, FileText, X } from 'lucide-react'
import * as api from '@/services/api'  // 최상단에 추가
import { IRecentProjectsResponse, IProject, Category, ProjectDetail, TableResponse,  } from '@/types/index'
import { getRecentProjects, } from '@/services/api'
import { useRouter } from 'next/navigation'
import { useState, useEffect, Suspense } from 'react'

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
}

// 프로젝트 카테고리 섹션 컨텐츠 컴포넌트
function ProjectCategorySectionContent({
  expandedSections,
  toggleSection,
  categories,
  setCategories,
  dispatch,
  onDragEnd,
  categoryProjects,
  setCategoryProjects
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
        setCategoryProjects(newCategoryProjects)
      } catch (error) {
        console.error('카테고리 로드 실패:', error)
      }
    }

    loadCategoriesAndProjects()
  }, [setCategories, dispatch, isAuthenticated, setCategoryProjects])

  const handleProjectClick = async (project: IProject) => {
    if(state.currentProjectId === project.id)
      return;

    console.log(`Current project:${state.currentProjectId}, Project UUID: ${project.id}, is_temp:${project.is_temporary}`);
    
    // 프로젝트 기본정보 요청
    const projectInfo:ProjectDetail = await api.getProjectInfo(project.id)
    console.log(`Change Project To ${projectInfo.name}`)
    
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
    } catch (error) {
      console.error('프로젝트 삭제 실패:', error);
    }
  };

  // 드래그 종료 핸들러
  const handleDragEnd = async (result: any) => {
    // 상위 컴포넌트의 onDragEnd 호출
    onDragEnd(result);

    if (!result.destination) return;

    const sourceId = result.draggableId;
    const destinationId = result.destination.droppableId;

    // 카테고리(영구)로 드롭된 경우
    if (destinationId.startsWith('category-')) {
      const categoryId = destinationId.replace('category-', '');
      try {
        // 이동된 프로젝트 찾기
        const movedProject = [...(state.recentProjects.today || []), 
                            ...(state.recentProjects.last_7_days || []),
                            ...(state.recentProjects.last_30_days || [])]
                            .find(p => p.id === sourceId);

        if (!movedProject) {
          console.error('이동할 프로젝트를 찾을 수 없습니다.');
          return;
        }

        // 프로젝트를 영구 프로젝트로 변경
        await api.updateProjectToPermanent(sourceId, categoryId);

        // 백엔드로 카테고리(영구폴더) 변경 요청
        await api.addProjectToCategory(sourceId, categoryId);

        // 상태 업데이트를 위한 새 프로젝트 객체 생성
        const updatedProject = {
          ...movedProject,
          is_temporary: false,
          retention_period: 'PERMANENT',
        };

        // 로컬 상태 업데이트
        setCategoryProjects(prev => ({
          ...prev,
          [categoryId]: [...(prev[categoryId] || []), updatedProject]
        }));

        // 최근 프로젝트 목록에서 제거
        dispatch({
          type: 'UPDATE_RECENT_PROJECTS',
          payload: {
            today: (state.recentProjects.today || []).filter(p => p.id !== sourceId),
            last_7_days: (state.recentProjects.last_7_days || []).filter(p => p.id !== sourceId),
            last_30_days: (state.recentProjects.last_30_days || []).filter(p => p.id !== sourceId)
          }
        });

        // 서버에서 최신 데이터 다시 가져오기
        const [recentProjects, categoriesData] = await Promise.all([
          api.getRecentProjects(),
          api.getCategories()
        ]);

        // 최근 프로젝트 업데이트
        dispatch({ type: 'UPDATE_RECENT_PROJECTS', payload: recentProjects });

        // 카테고리 프로젝트 목록 새로고침
        const projectsPromises = categoriesData.map(async (category) => {
          try {
            const projects = await api.getCategoryProjects(category.id);
            return { categoryId: category.id, projects };
          } catch (error) {
            console.error(`카테고리 ${category.id}의 프로젝트 로드 실패:`, error);
            return { categoryId: category.id, projects: [] };
          }
        });

        const projectsResults = await Promise.all(projectsPromises);
        const newCategoryProjects = projectsResults.reduce((acc, { categoryId, projects }) => {
          acc[categoryId] = projects;
          return acc;
        }, {} as { [key: string]: IProject[] });

        // 카테고리 프로젝트 상태 업데이트
        setCategoryProjects(newCategoryProjects);

      } catch (error) {
        console.error('프로젝트 이동 실패:', error);
      }
    }
  }

  const truncateTitle = (title: string, maxLength: number = 20) => {
    if (!title) return '(제목 없음)';
    return title.length > maxLength ? `${title.slice(0, maxLength)}...` : title;
  };

  const renderProjectList = (sectionTitle: string, projects: IProject[]) => {
    if (!projects || projects.length === 0) return null;

    return (
      <div key={sectionTitle} className="mb-2">
        <div className="flex items-center mb-1 text-xs font-medium text-gray-500 px-2">
          {sectionTitle}
          <span className="ml-1 text-xs">({projects.length})</span>
        </div>
        <div className="space-y-0.5">
          {projects.map((project, index) => (
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
                    "flex items-center px-3 py-1 text-sm rounded-md cursor-pointer group w-full",
                    state.currentProject?.id === project.id
                      ? "bg-gray-50 text-gray-700"
                      : "text-gray-600 hover:bg-gray-50",
                    snapshot.isDragging && "bg-blue-50 shadow-sm"
                  )}
                  onClick={() => handleProjectClick(project)}
                >
                  <span className="truncate flex-1 min-w-0">{project.name}</span>
                  <button
                    className="opacity-0 group-hover:opacity-100 hover:text-red-500 p-1 rounded-sm flex-shrink-0 ml-2"
                    onClick={(e) => handleDeleteProject(project.id, e)}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </Draggable>
          ))}
        </div>
      </div>
    );
  };

  const renderRecentProjects = () => {
    return (
      <div className="mb-4">
        <div className="flex items-center px-2 mb-1">
          <History className="w-4 h-4 mr-1 text-gray-400" />
          <span className="text-xs text-gray-500">최근 프로젝트</span>
        </div>
        <div className="space-y-0.5">
          {state.recentProjects?.today?.map((project, index) => (
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
                    "flex items-center px-3 py-1 text-sm rounded-md cursor-pointer group w-full",
                    state.currentProject?.id === project.id
                      ? "bg-gray-50 text-gray-700"
                      : "text-gray-600 hover:bg-gray-50",
                    snapshot.isDragging && "bg-blue-50 shadow-sm"
                  )}
                  onClick={() => handleProjectClick(project)}
                >
                  <span className="truncate flex-1 min-w-0">{project.name}</span>
                  <button
                    className="opacity-0 group-hover:opacity-100 hover:text-red-500 p-1 rounded-sm flex-shrink-0 ml-2"
                    onClick={(e) => handleDeleteProject(project.id, e)}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </Draggable>
          ))}
        </div>
      </div>
    );
  };

  const renderProjectSection = () => {
    const recentProjects = state.recentProjects;
    if (!recentProjects) return null;

    return (
      <div className="overflow-y-auto overflow-x-hidden max-h-[calc(100vh-16rem)] scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent hover:scrollbar-thumb-gray-400">
        {renderProjectList("오늘", recentProjects.today)}
        {renderProjectList("지난 7일", recentProjects.last_7_days)}
        {renderProjectList("지난 30일", recentProjects.last_30_days)}
      </div>
    );
  };

  const renderCategoryProjects = (categoryId: string) => {
    const projects = categoryProjects[categoryId] || []
    
    return projects.map((project, index) => (
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
              "flex items-center px-3 py-1 text-sm rounded-md cursor-pointer group w-full",
              state.currentProject?.id === project.id
                ? "bg-gray-50 text-gray-700"
                : "text-gray-600 hover:bg-gray-50",
              snapshot.isDragging && "bg-blue-50 shadow-sm"
            )}
            onClick={() => handleProjectClick(project)}
          >
            <span className="truncate flex-1 min-w-0">{project.name}</span>
            <button
              className="opacity-0 group-hover:opacity-100 hover:text-red-500 p-1 rounded-sm flex-shrink-0 ml-2"
              onClick={(e) => handleDeleteProject(project.id, e)}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </Draggable>
    ))
  }

  const renderProjects = (projects: IProject[], sectionTitle: string) => {
    if (!Array.isArray(projects) || !projects?.length) return null;

    return (
      <div className="space-y-0.4">
        <div className="text-xs text-gray-500 px-2">{sectionTitle}</div>
        {projects.map((project, index) => {
          if (!project?.id) return null;
          
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
                    snapshot.isDragging && "shadow-lg border-2 border-gray-200",
                    "rounded-md transition-all duration-200 ease-in-out"
                  )}
                >
                  <div className="flex-1 px-2 py-1">
                    <Button
                      type="button"
                      variant="ghost"
                      className={cn(
                        "w-full justify-start gap-2 px-2 max-w-full",
                        state.currentProjectId === project.id && "bg-gray-50",
                        !snapshot.isDragging && "hover:bg-gray-50"
                      )}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleProjectClick(project);
                      }}
                    >
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

  // 상태 추가
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState<string>("");

  // 카테고리 이름 수정 시작
  const handleCategoryDoubleClick = (category: Category) => {
    setEditingCategoryId(category.id);
    setEditingName(category.name);  // 원래 이름을 상태에 저장
  };

  // 카테고리 이름 수정 취소
  const handleCategoryEditCancel = (category: Category) => {
    setEditingCategoryId(null);
    setEditingName(category.name);  // 원래 이름으로 복원
  };

  // 카테고리 이름 수정 완료
  const handleCategoryNameSubmit = async (categoryId: string, category: Category) => {
    try {
      if (!editingName.trim()) {
        handleCategoryEditCancel(category);  // 빈 문자열이면 원래 이름으로 복원
        return;
      }

      // 이름이 변경되지 않았다면 수정 취소
      if (editingName === category.name) {
        handleCategoryEditCancel(category);
        return;
      }

      await api.updateCategory(categoryId, { name: editingName });

      setCategories(prev => 
        prev.map(cat => 
          cat.id === categoryId ? { ...cat, name: editingName } : cat
        )
      );
    } catch (error) {
      console.error('카테고리 이름 수정 실패:', error);
      handleCategoryEditCancel(category);  // 에러 발생 시 원래 이름으로 복원
    } finally {
      setEditingCategoryId(null);
    }
  };

  return (
    <div className="flex flex-col space-y-2">
      {/* 프로젝트 폴더 섹션 */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between px-2 py-1">
          <span className="text-sm font-semibold text-gray-700">프로젝트 폴더</span>
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
                      snapshot.isDraggingOver && "border-gray-200 bg-gray-50",
                      "transition-all duration-200 ease-in-out"
                    )}
                  >
                    <div className="relative flex items-center group">
                      <Button
                        variant="ghost"
                        className={cn(
                          "w-full justify-start text-sm h-8 pl-4",
                          snapshot.isDraggingOver && "bg-gray-50"
                        )}
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          handleCategoryDoubleClick(category);
                        }}
                      >
                        <div 
                          className="mr-1" 
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSection(`category-${category.id}`);
                          }}
                        >
                          {expandedSections.includes(`category-${category.id}`) ? (
                            <FolderOpen className={cn(
                              "h-4 w-4",
                              snapshot.isDraggingOver && "text-gray-600"
                            )} />
                          ) : (
                            <Folder className={cn(
                              "h-4 w-4",
                              snapshot.isDraggingOver && "text-gray-600"
                            )} />
                          )}
                        </div>
                        {editingCategoryId === category.id ? (
                          <Input
                            value={editingName}
                            onChange={(e) => setEditingName(e.target.value)}
                            onBlur={() => handleCategoryNameSubmit(category.id, category)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleCategoryNameSubmit(category.id, category);
                              } else if (e.key === 'Escape') {
                                handleCategoryEditCancel(category);
                              }
                            }}
                            className="h-6 px-1 py-0 text-sm"
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <span className="flex-1 text-left truncate">{category.name}</span>
                        )}
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
                    {expandedSections.includes(`category-${category.id}`) && (
                      <div className="pl-3">
                        {renderCategoryProjects(category.id)}
                      </div>
                    )}
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
                  <Plus className="h-4 w-4 mr-0.5" />
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

      {/* 최근 프로젝트 섹션 */}
      {isAuthenticated && (
        <div className="space-y-3">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="text-sm font-semibold text-gray-700">최근 프로젝트</span>
          </div>
          <Droppable droppableId="recent-projects" type="PROJECT">
            {(provided, snapshot) => (
              <div
                ref={provided.innerRef}
                {...provided.droppableProps}
                className={cn(
                  "flex-1 overflow-hidden",
                  snapshot.isDraggingOver && "bg-gray-100/50"
                )}
              >
                <div className="space-y-2">
                  {state.recentProjects?.today && renderProjectList('오늘', state.recentProjects.today)}
                  {state.recentProjects?.last_7_days && renderProjectList('지난 7일', state.recentProjects.last_7_days)}
                  {state.recentProjects?.last_30_days && renderProjectList('지난 30일', state.recentProjects.last_30_days)}
                </div>
                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </div>
      )}
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
