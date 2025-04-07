"use client"

import React, { useState, useEffect, Suspense, createContext, useContext, forwardRef, Ref } from 'react'
import { useRouter } from 'next/navigation'
import { useApp } from '@/contexts/AppContext'
import * as api from '@/services/api'
import { DragDropContext, DropResult, Droppable, Draggable } from '@hello-pangea/dnd'
import {
  PenSquare,
  ScrollText,
  BarChart2,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Plus,
  MessageSquare,
  Settings,
  Cog,
  User,
  Trash2
} from "lucide-react"
import { Button } from "intellio-common/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "intellio-common/components/ui/tooltip"
import { ProjectCategorySection } from './sidebar/ProjectCategorySection'
import { TemplateSection } from './sidebar/TemplateSection'
import { useAuth, useAuthCheck } from '@/hooks/useAuth';
import { IRecentProjectsResponse, IProject, IMessage, ProjectDetail, Category, SidebarProps as BaseSidebarProps, Template } from '@/types/index'
import { cn } from '@/lib/utils'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "intellio-common/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "intellio-common/components/ui/dropdown-menu"
import { LoginButton } from "@/components/auth/LoginButton"
import { FontSettings } from "@/components/settings/FontSettings"
import { Loader2 } from "lucide-react"

// 모바일 환경 감지 훅
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < 768); // 768px 미만을 모바일로 간주
    };

    // 초기 체크
    checkIsMobile();

    // 리사이즈 이벤트에 대응
    window.addEventListener('resize', checkIsMobile);
    return () => window.removeEventListener('resize', checkIsMobile);
  }, []);

  return isMobile;
};

// 사이드바 컨텐츠 컴포넌트
// 기존 SidebarProps를 확장하여 isMobileMenuOpen 속성 추가
interface ExtendedSidebarProps extends BaseSidebarProps {
  isMobileMenuOpen?: boolean;
}

// SidebarContent를 forwardRef로 감싸서 ref를 받을 수 있도록 수정
const SidebarContent = forwardRef<HTMLDivElement, ExtendedSidebarProps>(
  ({ className, isMobileMenuOpen }, ref) => {
    const router = useRouter()
    const { state, dispatch } = useApp()
    const [categories, setCategories] = useState<Category[]>([]);
    const [categoryProjects, setCategoryProjects] = useState<{ [key: string]: IProject[] }>({})
    const [templates, setTemplates] = useState<Template[]>([
      { id: 'template1', name: '기본 템플릿', description: '일반적인 문서 분석용 템플릿' },
      { id: 'template2', name: '계약서 분석', description: '계약서 분석 전용 템플릿' },
      { id: 'template3', name: '이력서 분석', description: '이력서 분석 전용 템플릿' },
    ]);
    const [isLoading, setIsLoading] = useState(true)
    const [expandedSections, setExpandedSections] = useState<string[]>(['recent', 'template', 'folders'])
    const [newCategoryName, setNewCategoryName] = useState('')
    const [categoryError, setCategoryError] = useState('')
    const [isAddingCategory, setIsAddingCategory] = useState(false)
    const [isTemplateDialogOpen, setIsTemplateDialogOpen] = useState(false);
    const [categoryToDelete, setCategoryToDelete] = useState<Category | null>(null);
    const { user, isAuthenticated, logout } = useAuth();
    const [isCollapsed, setIsCollapsed] = useState(false);
    const isMobile = useIsMobile();
    const [isLoginDialogOpen, setIsLoginDialogOpen] = useState(false);
    const [isAuthLoading, setIsAuthLoading] = useState(true);
    const [isSettingsDialogOpen, setIsSettingsDialogOpen] = useState(false);

    // 쿠키 기반 인증 상태 확인
    useAuthCheck();

    // ProjectCategorySection의 handleProjectClick을 저장할 ref
    const handleProjectClickRef = React.useRef<(project: IProject) => Promise<void>>(null);

    // 섹션 토글 함수
    const toggleSection = (section: string) => {
      setExpandedSections(prev => 
        prev.includes(section)
          ? prev.filter(s => s !== section)
          : [...prev, section]
      );
    };

    // 사이드바 접기/펼치기 상태 관리
    const toggleSidebar = () => {
      const newIsCollapsed = !isCollapsed;
      setIsCollapsed(newIsCollapsed);
      localStorage.setItem('sidebarCollapsed', String(newIsCollapsed));
      
      // 사이드바 상태 변경 이벤트 발생
      const event = new CustomEvent('sidebarStateChanged', { 
        detail: { isCollapsed: newIsCollapsed } 
      });
      window.dispatchEvent(event);
    };
    
    // 모바일 메뉴 닫기
    const closeMenu = () => {
      // 레이아웃에 메뉴 닫기 이벤트 전달
      const event = new CustomEvent('closeMobileMenu'); 
      window.dispatchEvent(event);
    };

    // 프로젝트 선택 시 모바일에서 사이드바 닫기 함수
    const closeMenuOnProjectSelect = () => {
      if (isMobile) {
        closeMenu();
      }
    }

    // 초기 상태 로드 (기본값: 펼침)
    useEffect(() => {
      // Always start expanded, ignore localStorage for initial load
      setIsCollapsed(false);
      // const savedState = localStorage.getItem('sidebarCollapsed');
      // if (savedState !== null) {
      //   setIsCollapsed(savedState === 'true');
      // }
    }, []);
  
    // 외부 햄버거 버튼 이벤트 리스너 제거
    /*
    useEffect(() => {
      const handleExternalToggleSidebar = () => {
        setIsMenuOpen(prev => !prev);
      };
      window.addEventListener('toggleSidebar', handleExternalToggleSidebar);
      return () => {
        window.removeEventListener('toggleSidebar', handleExternalToggleSidebar);
      };
    }, []);
    */

    useEffect(() => {
      const fetchRecentProjects = async () => {
        try {
          if (!isAuthenticated) {  
            //console.warn('로그인되지 않았습니다.');
            return;
          }
          const response:IRecentProjectsResponse = await api.getRecentProjects()
          
          dispatch({ 
            type: 'UPDATE_RECENT_PROJECTS', 
            payload: {
              today: response.today || [],
              last_7_days: response.last_7_days || [],
              last_30_days: response.last_30_days || []
            }
          })
          setIsLoading(false)
        } catch (error) {
          console.error('최근 프로젝트 로딩 실패:', error)
          setIsLoading(false)
        }
      }

      // 초기 로딩 시에만 프로젝트 목록을 가져옴
      if (isLoading) {
        fetchRecentProjects()
      }
    }, [dispatch, isLoading])

    useEffect(() => {
      const handleProjectCreated = () => {
        const fetchProjects = async () => {
          try {
            // 1. 최근 프로젝트 목록 갱신
            const response = await api.getRecentProjects()
            dispatch({ 
              type: 'UPDATE_RECENT_PROJECTS', 
              payload: {
                today: response.today || [],
                last_7_days: response.last_7_days || [],
                last_30_days: response.last_30_days || []
              }
            })

            // 2. 카테고리 목록 로드
            const categoriesData = await api.getCategories()
            setCategories(categoriesData)

            // 3. 각 카테고리의 프로젝트 로드
            const projectsPromises = categoriesData.map(async (category) => {
              try {
                const projects = await api.getCategoryProjects(category.id)
                category.projects_count = projects.length
                return { categoryId: category.id, projects }
              } catch (error) {
                console.error(`카테고리 ${category.id}의 프로젝트 로드 실패:`, error)
                return { categoryId: category.id, projects: [] }
              }
            })

            const projectsResults = await Promise.all(projectsPromises)
            const newCategoryProjects = projectsResults.reduce((acc, result) => {
              if (result && result.categoryId) {
                acc[result.categoryId] = result.projects
              }
              return acc
            }, {} as { [key: string]: IProject[] })

            dispatch({
              type: 'UPDATE_CATEGORY_PROJECTS',
              payload: newCategoryProjects
            })

          } catch (error) {
            console.error('프로젝트 목록 조회 실패:', error)
          } finally {
            setIsLoading(false)
          }
        }

        fetchProjects()
      }

      window.addEventListener('projectCreated', handleProjectCreated)
      return () => {
        window.removeEventListener('projectCreated', handleProjectCreated)
      }
    }, [dispatch])

    // 새 프로젝트 생성 함수
    const handleNewProject = async () => {
      setIsLoading(true);
      try {
        if (state.currentProjectId) {
          // 기존 로직 유지
        }
        dispatch({ type: 'SET_INITIAL_STATE' });
      } catch (error) {
        console.error('Error saving current project:', error);
      } finally {
        setIsLoading(false);
      }
      closeMenuOnProjectSelect();
    };

    const handleDragEnd = async (result: DropResult) => {
      if (!result.destination) return;
      
      const { source, destination, draggableId } = result;
      console.log('Drag ended:', { source, destination, draggableId });

      // 최근 프로젝트에서 영구 폴더로 이동하는 경우
      if (source.droppableId.startsWith('recent-projects') && destination.droppableId.startsWith('category-')) {
        try {
          // 이동된 프로젝트 찾기
          const movedProject = [...(state.recentProjects.today || []), 
                              ...(state.recentProjects.last_7_days || []),
                              ...(state.recentProjects.last_30_days || [])]
                              .find(p => p.id === draggableId);

          if (!movedProject) {
            console.error('이동할 프로젝트를 찾을 수 없습니다.');
            return;
          }

          const categoryId = destination.droppableId.replace('category-', '');

          // 프로젝트를 영구 프로젝트로 변경하고 카테고리에 추가
          // updateProjectToPermanent 함수는 이미 프로젝트를 영구적으로 변경하고 카테고리에 추가하는 작업을 수행함
          //const updatedProject = await api.updateProjectToPermanent(draggableId, categoryId);
          // 백엔드로 카테고리(영구폴더) 변경 요청
          await api.addProjectToCategory(draggableId, categoryId);
          //console.log('프로젝트가 영구 폴더로 이동됨:', updatedProject);

          // UI 업데이트를 위해 해당 카테고리의 프로젝트만 다시 로드
          try {
            // 해당 카테고리의 프로젝트만 다시 로드
            const projects = await api.getCategoryProjects(categoryId);
            
            // 카테고리 목록에서 해당 카테고리 찾아서 프로젝트 수 업데이트
            setCategories(prev => 
              prev.map(category => 
                category.id === categoryId 
                  ? { ...category, projects_count: projects.length } 
                  : category
              )
            );
            
            // 카테고리 프로젝트 상태 업데이트
            setCategoryProjects(prev => ({
              ...prev,
              [categoryId]: projects
            }));
            
            // 카테고리 프로젝트 상태를 전역 상태에 반영
            dispatch({
              type: 'UPDATE_CATEGORY_PROJECTS',
              payload: {
                ...state.categoryProjects,
                [categoryId]: projects
              }
            });
            
            // 최근 프로젝트 목록도 새로고침
            const recentProjectsResponse = await api.getRecentProjects();
            dispatch({ 
              type: 'UPDATE_RECENT_PROJECTS', 
              payload: recentProjectsResponse
            });
            
          } catch (error) {
            console.error(`카테고리 ${categoryId}의 프로젝트 로드 실패:`, error);
          }

        } catch (error) {
          console.error('프로젝트 이동 실패:', error);
        }
      }
    };

    const isCategoryNameDuplicate = (name: string) => {
      return categories.some(category => category.name === name)
    }

    const handleAddCategory = async () => {
      if (!newCategoryName.trim()) {
        setCategoryError('폴더 이름을 입력해주세요.');
        return;
      }

      try {
        const response = await fetch('/api/v1/categories/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            name: newCategoryName.trim(),
            type: "PERMANENT"  
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || '폴더 생성에 실패했습니다.');
        }

        const newCategory = await response.json();
        setCategories([...categories, newCategory]);
        setNewCategoryName('');
        setIsAddingCategory(false);
        setCategoryError('');
      } catch (error) {
        console.error('폴더 생성 실패:', error);
        setCategoryError(error instanceof Error ? error.message : '폴더 생성에 실패했습니다.');
      }
    }

    const handleDeleteProject = async (projectId: string) => {
      try {
        await api.deleteProject(projectId);
        dispatch({
          type: 'DELETE_PROJECT',
          payload: projectId
        });
      } catch (error) {
        console.error('프로젝트 삭제 실패:', error);
      }
    }

    // 로그아웃 처리 함수
    const handleLogout = async () => {
      await logout();
      // AppContext 상태 초기화
      dispatch({ type: 'SET_INITIAL_STATE' });
      dispatch({ type: 'SET_PROJECT_TITLE', payload: '' });
      console.log('[Sidebar] 로그아웃 및 상태 초기화 완료');
      setIsSettingsDialogOpen(false);
    };

    useEffect(() => {
      // 인증 상태가 확인되면 로딩 상태를 false로 설정
      setIsAuthLoading(false)
    }, [isAuthenticated, user]);

    // 레이아웃에서 모바일 메뉴 토글 이벤트 리스닝
    useEffect(() => {
      const handleToggleMobileMenu = (event: CustomEvent) => {
        // setIsMenuOpen(event.detail.isOpen); // 내부 상태 변경 제거
      };

      // 이벤트 리스너 등록
      window.addEventListener('toggleMobileMenu', handleToggleMobileMenu as EventListener);
      
      return () => {
        // 컴포넌트 언마운트 시 이벤트 리스너 제거
        window.removeEventListener('toggleMobileMenu', handleToggleMobileMenu as EventListener);
      };
    }, []);

    const effectiveIsMenuOpen = isMobile && (isMobileMenuOpen ?? false);

    // 가장 바깥쪽 div에 ref 연결
    return (
      <>
        {/* isMobileMenuOpen && isMobile 조건 추가하여 모바일에서 메뉴 열렸을 때만 오버레이 표시 */}
        {isMobileMenuOpen && isMobile && (
          <div 
            className="fixed inset-0 bg-black bg-opacity-50 z-[9998] md:hidden"
            onClick={closeMenu} // 오버레이 클릭 시 메뉴 닫기
          />
        )}
        <DragDropContext onDragEnd={handleDragEnd}>
          <div
            ref={ref} // 전달받은 ref 연결
            className={cn(
              "flex flex-col h-full bg-[#202123] text-white transition-all duration-300 ease-in-out border-r border-[#2e2f33]",
              isMobile
                ? `fixed top-0 left-0 z-[9999] w-64 transform ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`
                : isCollapsed ? "w-[60px]" : "w-[300px]", // 데스크탑 너비 수정 (60px)
              className
            )}
          >
            {/* 사이드바 헤더 */}
            <div className="flex items-center justify-between p-3">
              {!isCollapsed && (
                <div className="flex items-center gap-2">
                  <h1 className="font-bold text-[#10A37F]">Doceasy</h1>
                </div>
              )}
              
              {/* 헤더 버튼들 */}
              <div className="flex items-center ml-auto gap-1">
                {!isCollapsed && (
                  <>
                    {/* 토글 버튼 */}
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={isMobile ? closeMenu : toggleSidebar} // 모바일에서는 메뉴 닫기, 데스크탑에서는 사이드바 토글
                      className="h-8 w-8"
                    >
                      <ChevronLeft className="h-5 w-5" />
                    </Button>
                  </>
                )}
                {isCollapsed && (
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={toggleSidebar}
                    className="h-8 w-8"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </Button>
                )}
              </div>
            </div>
            
            {/* 새 프로젝트 버튼 */}
            <div className="p-3">
              <Button 
                className={`${isCollapsed ? 'h-10 w-10' : 'w-full'} bg-[#858B9D] text-[#FFFFFF] hover:bg-[#10A37F] hover:text-white flex items-center justify-center gap-2 rounded-md`}
                onClick={handleNewProject}
              >
                <Plus className={`${isCollapsed ? 'h-[22px] w-[22px]' : 'h-4 w-4'}`} strokeWidth={2.5} />
                {!isCollapsed && <span className="ml-2 text-sm font-semibold text-[#FFFFFF]">새 프로젝트</span>}
              </Button>
            </div>
            
            {/* 사이드바 내용 - 접혀있지 않을 때만 세부 내용 표시 */}
            <div className="flex-1 overflow-y-auto">
              {/* 카테고리 및 프로젝트 영역 */}
              {!isCollapsed ? (
                <div className="p-1">
                  {/* ProjectCategorySection 컴포넌트 - 폴더 목록을 가장 위로 이동 */}
                  <ProjectCategorySection 
                    expandedSections={expandedSections}
                    toggleSection={toggleSection}
                    categories={categories}
                    setCategories={setCategories}
                    dispatch={dispatch}
                    onDragEnd={handleDragEnd}
                    categoryProjects={categoryProjects}
                    setCategoryProjects={setCategoryProjects}
                    closeMenuOnProjectSelect={closeMenuOnProjectSelect}
                    handleProjectClickRef={handleProjectClickRef}
                  />
                  
                  {/* 최근 프로젝트 목록 (채팅 스타일로) */}
                  <div className="space-y-1 mt-4 ">
                    <div className="flex items-center justify-between px-2 py-1">
                      <span className="text-sm font-semibold text-[#F4F4F4] uppercase">최근 프로젝트</span>
                    </div>
                    
                    {state.recentProjects.today && state.recentProjects.today.length > 0 && (
                      <Droppable droppableId="recent-projects" type="PROJECT">
                        {(provided, snapshot) => (
                          <div 
                            ref={provided.innerRef}
                            {...provided.droppableProps}
                            className={cn(
                              "space-y-1",
                              snapshot.isDraggingOver && "bg-gray-50"
                            )}
                          >
                            {state.recentProjects.today.map((project, index) => (
                              <Draggable key={project.id} draggableId={project.id} index={index}>
                                {(provided, snapshot) => (
                                  <div
                                    ref={provided.innerRef}
                                    {...provided.draggableProps}
                                    {...provided.dragHandleProps}
                                    className={cn(
                                      "flex items-center gap-2 w-full text-left px-3 py-2 rounded-md transition-colors",
                                      snapshot.isDragging ? "bg-blue-100" : "hover:bg-[#3F424A]"
                                    )}
                                    onClick={() => {
                                      if (handleProjectClickRef.current) {
                                        handleProjectClickRef.current(project);
                                      }
                                      closeMenuOnProjectSelect();
                                    }}
                                  >
                                    <MessageSquare className="h-4 w-4 text-[#ABABAB] flex-shrink-0" />
                                    {/* 프로젝트 이름 텍스트 색상 변경 */}
                                    <span className="text-sm truncate text-[#ABABAB]">{project.name}</span> 
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-7 w-7 p-0 opacity-0 hover:opacity-100 ml-auto"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteProject(project.id);
                                      }}
                                    >
                                      <Trash2 className="h-4 w-4 text-[#ABABAB]" />
                                    </Button>
                                  </div>
                                )}
                              </Draggable>
                            ))}
                            {provided.placeholder}
                          </div>
                        )}
                      </Droppable>
                    )}
                    
                    {state.recentProjects.last_7_days && state.recentProjects.last_7_days.length > 0 && (
                      <>
                        <div className="text-xs text-[#ABABAB] px-3 py-2 font-medium">Last 7 Days</div>
                        <Droppable droppableId="recent-projects-7days" type="PROJECT">
                          {(provided, snapshot) => (
                            <div 
                              ref={provided.innerRef}
                              {...provided.droppableProps}
                              className={cn(
                                "space-y-1",
                                snapshot.isDraggingOver && "bg-gray-50"
                              )}
                            >
                              {state.recentProjects.last_7_days.map((project, index) => (
                                <Draggable key={project.id} draggableId={project.id} index={index}>
                                  {(provided, snapshot) => (
                                    <div
                                      ref={provided.innerRef}
                                      {...provided.draggableProps}
                                      {...provided.dragHandleProps}
                                      className={cn(
                                        "flex items-center gap-2 w-full text-left px-3 py-2 rounded-md transition-colors",
                                        snapshot.isDragging ? "bg-blue-100" : "hover:bg-gray-100"
                                      )}
                                      onClick={() => {
                                        if (handleProjectClickRef.current) {
                                          handleProjectClickRef.current(project);
                                        }
                                        closeMenuOnProjectSelect();
                                      }}
                                    >
                                      <MessageSquare className="h-4 w-4 text-[#ABABAB] flex-shrink-0" />
                                      {/* 프로젝트 이름 텍스트 색상 변경 */}
                                      <span className="text-sm truncate text-[#ABABAB]">{project.name}</span>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-7 w-7 p-0 opacity-0 hover:opacity-100 ml-auto"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleDeleteProject(project.id);
                                        }}
                                      >
                                        <Trash2 className="h-4 w-4 text-[#ABABAB]" />
                                      </Button>
                                    </div>
                                  )}
                                </Draggable>
                              ))}
                              {provided.placeholder}
                            </div>
                          )}
                        </Droppable>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div>
                  {/* 접힌 상태에서는 아무것도 표시하지 않음 */}
                </div>
              )}
            </div>
            
            {/* 사이드바 푸터 */}
            <div className={`p-4 ${isCollapsed ? 'flex justify-center' : ''}`}>
              {/* 접혔을 때만 보이는 하단 버튼 영역 */}
              {isCollapsed && (
                <div className="mt-auto pt-2 pb-2 flex flex-col items-center space-y-1">
                  {/* 마이페이지 버튼 */}
                  <TooltipProvider delayDuration={300}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-10 w-10 rounded-md text-[#ABABAB] hover:bg-[#10A37F] hover:text-white m-1"
                          // TODO: 마이페이지 이동 로직 추가
                        >
                          <User className="h-[22px] w-[22px]" strokeWidth={2.5} />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right" sideOffset={5}>
                        마이페이지
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  {/* 설정 버튼 */}
                  <TooltipProvider delayDuration={300}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-10 w-10 rounded-md text-[#ABABAB] hover:bg-[#10A37F] hover:text-white m-1"
                          // TODO: 설정 페이지 이동 로직 추가
                        >
                          <Settings className="h-[22px] w-[22px]" strokeWidth={2.5} />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right" sideOffset={5}>
                        설정
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              )}
              {!isCollapsed && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <User className="h-4 w-4 mr-2" />
                    <span className="text-sm truncate">
                      {isAuthLoading ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1 inline" />
                      ) : isAuthenticated && user ? (
                        user.email
                      ) : (
                        "로그인이 필요합니다"
                      )}
                    </span>
                  </div>

                  {/* 설정 버튼 */}
                  {isAuthLoading ? (
                    <div className="flex items-center">
                      <Loader2 className="h-4 w-4 animate-spin" />
                    </div>
                  ) : isAuthenticated && user ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="w-8 h-8 p-0 hover:bg-[#3F424A]">
                          <Settings className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => {}}>
                          <User className="h-4 w-4 mr-2" />
                          <span>{user.email}</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                          <Dialog>
                            <DialogTrigger asChild>
                              <div className="flex items-center w-full">
                                <Cog className="h-4 w-4 mr-2" />
                                <span>앱 설정</span>
                              </div>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>설정</DialogTitle>
                                <DialogDescription>
                                  애플리케이션 설정을 변경할 수 있습니다
                                </DialogDescription>
                              </DialogHeader>
                              <FontSettings />
                            </DialogContent>
                          </Dialog>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={handleLogout}>
                          <Trash2 className="h-4 w-4 mr-2" />
                          <span>로그아웃</span>
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : (
                    <Dialog open={isLoginDialogOpen} onOpenChange={setIsLoginDialogOpen}>
                      <DialogTrigger asChild>
                        <Button variant="ghost" size="icon" className="w-8 h-8 p-0 hover:bg-[#3F424A]">
                          <Settings className="h-4 w-4" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>로그인 선택</DialogTitle>
                          <DialogDescription>
                            소셜 계정으로 로그인하세요
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div className="flex flex-col space-y-2">
                            <LoginButton provider="google" redirectTo="doceasy" />
                            <LoginButton provider="naver" redirectTo="doceasy" />
                          </div>
                        </div>
                      </DialogContent>
                    </Dialog>
                  )}
                </div>
              )}
            </div>
          </div>
        </DragDropContext>
      </>
    )
  }
);

// Sidebar 컴포넌트도 forwardRef로 감싸서 ref를 전달받도록 수정
export const Sidebar = forwardRef<HTMLDivElement, ExtendedSidebarProps>(
  ({ className, isMobileMenuOpen }, ref) => {
    return (
      <Suspense fallback={<div className="w-[300px] bg-white border-r animate-pulse"></div>}>
        {/* SidebarContent에 ref 전달 */}
        <SidebarContent ref={ref} className={className} isMobileMenuOpen={isMobileMenuOpen} />
      </Suspense>
    )
  }
);
Sidebar.displayName = 'Sidebar'; // 디버깅을 위한 displayName 설정
