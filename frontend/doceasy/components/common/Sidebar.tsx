"use client"

import { useState, useEffect, Suspense } from 'react'

import { useRouter } from 'next/navigation'

import { useApp } from '@/contexts/AppContext'
import * as api from '@/services/api'
import { DragDropContext,   DropResult } from '@hello-pangea/dnd'
import {
  PenSquare,
  ScrollText,
  BarChart2,
  ChevronLeft,
  ChevronRight,
  Menu
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
import { useAuth } from '@/hooks/useAuth';
import { IRecentProjectsResponse, IProject, IMessage, ProjectDetail, Category, SidebarProps, Template } from '@/types/index'


// 사이드바 컨텐츠 컴포넌트
function SidebarContent({ className }: SidebarProps) {
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
  const { isAuthenticated } = useAuth();
  
  // 사이드바 접기/펼치기 상태 관리
  const [isCollapsed, setIsCollapsed] = useState(false);

  // 초기 상태 로드 (로컬 스토리지에서 사용자 선호도 가져오기)
  useEffect(() => {
    const savedState = localStorage.getItem('sidebarCollapsed');
    if (savedState !== null) {
      setIsCollapsed(savedState === 'true');
    }
  }, []);

  // 상태 변경 시 로컬 스토리지에 저장
  const toggleSidebar = () => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    localStorage.setItem('sidebarCollapsed', String(newState));
    
    // 사이드바 상태 변경 이벤트 발생 (레이아웃에서 감지하기 위함)
    window.dispatchEvent(new CustomEvent('sidebarStateChanged', {
      detail: { isCollapsed: newState }
    }));
  };

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

  const handleDragEnd = async (result: DropResult) => {
    if (!result.destination) return;
    
    const { source, destination, draggableId } = result;
    console.log('Drag ended:', { source, destination, draggableId });

    // 최근 프로젝트에서 영구 폴더로 이동하는 경우
    if (source.droppableId === 'recent-projects' && destination.droppableId.startsWith('category-')) {
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

  const toggleSection = (section: string) => {
    setExpandedSections(prev =>
      prev.includes(section)
        ? prev.filter(s => s !== section)
        : [...prev, section]
    )
  }

  return (
    <DragDropContext
      onBeforeDragStart={(start) => {
        console.log('BEFORE Drag Start:', {
          draggableId: start.draggableId,
          source: start.source,
          time: new Date().toISOString()
        });
      }}
      onDragStart={(start) => {
        console.log('Drag Start in Context:', {
          draggableId: start.draggableId,
          source: start.source,
          time: new Date().toISOString()
        });
      }}
      onDragEnd={(result) => {
        console.log('Drag End in Context:', {
          draggableId: result.draggableId,
          source: result.source,
          destination: result.destination,
          time: new Date().toISOString()
        });
        handleDragEnd(result);
      }}
    >
      <div className={`transition-all duration-300 ease-in-out border-r bg-gray-200 flex flex-col h-full ${isCollapsed ? 'w-[50px]' : 'w-[250px]'}`}>
        {isCollapsed ? (
          // 접힌 상태의 사이드바 UI
          <div className="flex flex-col h-full">
            <div className="p-3 flex items-center justify-center flex-shrink-0 border-b">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-8 w-8"
                      onClick={toggleSidebar}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>사이드바 펼치기</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            
            <div className="flex-1 flex flex-col items-center py-4 space-y-4">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-8 w-8"
                      onClick={async () => {
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
                      }}
                    >
                      <PenSquare className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>새로 만들기</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-8 w-8"
                      onClick={() => {
                        const stockEasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL || 'https://stockeasy.intellio.kr';
                        window.open(stockEasyUrl, '_blank');
                      }}
                    >
                      <BarChart2 className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>AI 주식정보 서비스</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        ) : (
          // 펼쳐진 상태의 사이드바 UI (기존 UI)
          <>
            <div className="p-4 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <ScrollText className="h-6 w-6 text-primary" />
                <h2 className="text-lg font-semibold tracking-tight">DocEasy</h2>
              </div>
              <div className="flex items-center">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-8 w-8"
                        onClick={async () => {
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
                        }}
                      >
                        <PenSquare className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>새로 만들기</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-8 w-8 ml-1"
                        onClick={toggleSidebar}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>사이드바 접기</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto">
              <div className="p-2">
                <div className="space-y-6 w-full">
                  <TemplateSection
                    expandedSections={expandedSections}
                    toggleSection={toggleSection}
                  />
                  <ProjectCategorySection
                    expandedSections={expandedSections}
                    toggleSection={toggleSection}
                    categories={categories}
                    setCategories={setCategories}
                    dispatch={dispatch}
                    onDragEnd={handleDragEnd}
                    categoryProjects={categoryProjects}
                    setCategoryProjects={setCategoryProjects}
                  />
                </div>
              </div>
            </div>
            
            {/* StockEasy 바로가기 버튼 */}
            <div className="p-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button 
                      variant="ghost" 
                      className="w-full flex items-center justify-start gap-2 px-2 py-2 hover:bg-gray-50"
                      onClick={() => {
                        // 환경 변수를 사용하여 StockEasy URL 설정
                        const stockEasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL || 'https://stockeasy.intellio.kr';
                        window.open(stockEasyUrl, '_blank');
                      }}
                    >
                      <BarChart2 className="h-4 w-4" />
                      <span className="text-left flex-grow font-medium">StockEasy</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>AI 주식정보 서비스</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </>
        )}
      </div>
    </DragDropContext>
  )
}

// 사이드바 컴포넌트
export const Sidebar = ({ className }: SidebarProps) => {
  return (
    <Suspense fallback={<div className="w-[50px] bg-background border-r"></div>}>
      <SidebarContent className={className} />
    </Suspense>
  )
}
