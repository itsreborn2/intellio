"use client"

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'
import { AppContext, useApp } from '@/contexts/AppContext'
import * as api from '@/services/api'
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd'
import { cn } from "@/lib/utils"
import {
  Folder,
  History,
  ChevronDown,
  ChevronRight,
  FileText,
  Zap,
  Plus,
  AlertTriangle,
  Trash2,
  AlertCircle,
  FileType,
  PenSquare,
  ScrollText
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ProjectCategorySection } from './sidebar/ProjectCategorySection'
import { TemplateSection } from './sidebar/TemplateSection'

interface Project {
  id: string
  name: string
  created_at: string
  formatted_date?: string
  is_temporary: boolean
  will_be_deleted?: boolean
}

interface ProjectGroup {
  today: Project[]
  yesterday: Project[]
  fourDaysAgo: Project[]
  older: Project[]
}

interface Category {
  id: string
  name: string
}

interface Template {
  id: string
  name: string
  description: string
}

interface SidebarProps {
  className?: string;
}

export const Sidebar = ({ className }: SidebarProps) => {
  const router = useRouter()
  const { state, dispatch } = useApp()
  const [categories, setCategories] = useState<Category[]>([]);
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
  const [categoryProjects, setCategoryProjects] = useState<{ [key: string]: Project[] }>({})  

  useEffect(() => {
    const fetchRecentProjects = async () => {
      try {
        const response = await api.getRecentProjects()
        
        dispatch({ 
          type: 'UPDATE_RECENT_PROJECTS', 
          payload: {
            today: response.today || [],
            yesterday: response.yesterday || [],
            fourDaysAgo: response.four_days_ago || [],
            older: []
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
              yesterday: response.yesterday || [],
              fourDaysAgo: response.four_days_ago || [],
              older: []
            }
          })

          // 2. 카테고리 목록 로드
          const categoriesData = await api.getCategories()
          setCategories(categoriesData)

          // 3. 각 카테고리의 프로젝트 로드
          const projectsPromises = categoriesData.map(async (category) => {
            try {
              const projects = await api.getCategoryProjects(category.id)
              return { categoryId: category.id, projects }
            } catch (error) {
              console.error(`카테고리 ${category.id}의 프로젝트 로드 실패:`, error)
              return { categoryId: category.id, projects: [] }
            }
          })

          const projectsResults = await Promise.all(projectsPromises)
          const newCategoryProjects = projectsResults.reduce((acc, { categoryId, projects }) => {
            acc[categoryId] = projects
            return acc
          }, {} as { [key: string]: Project[] })

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

  useEffect(() => {
    const loadCategories = async () => {
      try {
        const data = await api.getCategories();
        setCategories(data);
      } catch (error) {
        console.error('카테고리 로드 실패:', error);
      }
    };
    loadCategories();
  }, []);

  const handleDragEnd = async (result: DropResult) => {
    if (!result.destination) return;
    
    const { source, destination, draggableId } = result;
    console.log('Drag ended:', { source, destination, draggableId });

    // 최근 프로젝트에서 영구 폴더로 이동하는 경우
    if (source.droppableId === 'recent-projects' && destination.droppableId.startsWith('category-')) {
      try {
        // 이동된 프로젝트 찾기
        const movedProject = [...(state.recentProjects.today || []), 
                            ...(state.recentProjects.yesterday || []),
                            ...(state.recentProjects.four_days_ago || [])]
                            .find(p => p.id === draggableId);

        if (!movedProject) {
          console.error('이동할 프로젝트를 찾을 수 없습니다.');
          return;
        }

        const categoryId = destination.droppableId.replace('category-', '');

        // 프로젝트를 영구 프로젝트로 변경
        await api.updateProjectToPermanent(draggableId, categoryId);

        // 백엔드로 카테고리(영구폴더) 변경 요청
        await api.addProjectToCategory(draggableId, categoryId);

        // // 최근 프로젝트 목록에서 제거
        // const updatedRecentProjects = {
        //   today: (state.recentProjects.today || []).filter(p => p.id !== draggableId),
        //   yesterday: (state.recentProjects.yesterday || []).filter(p => p.id !== draggableId),
        //   four_days_ago: (state.recentProjects.four_days_ago || []).filter(p => p.id !== draggableId)
        // };

        // 카테고리(영구폴더)에 프로젝트 추가
        setCategoryProjects(prev => ({
          ...prev,
          [categoryId]: [...(prev[categoryId] || []), {
            id: movedProject.id,
            name: movedProject.title,
          }]
        }));

        // UI 업데이트. 최근 프로젝트 영역은 굳이 업데이트할 필요가 없고
        // 프로젝트 폴더만 업데이트해주면 되겠는걸?
        // 근데 이렇게 비효율적으로 매번 읽어야하나..
        // 2. 카테고리 목록 로드
        const categoriesData = await api.getCategories()
        setCategories(categoriesData)

        // 3. 각 카테고리의 프로젝트 로드
        const projectsPromises = categoriesData.map(async (category) => {
          try {
            const projects = await api.getCategoryProjects(category.id)
            return { categoryId: category.id, projects }
          } catch (error) {
            console.error(`카테고리 ${category.id}의 프로젝트 로드 실패:`, error)
            return { categoryId: category.id, projects: [] }
          }
        })

        const projectsResults = await Promise.all(projectsPromises)
        const newCategoryProjects = projectsResults.reduce((acc, { categoryId, projects }) => {
          acc[categoryId] = projects
          return acc
        }, {} as { [key: string]: Project[] })

        dispatch({
          type: 'UPDATE_CATEGORY_PROJECTS',
          payload: newCategoryProjects
        })

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

  const handleProjectClick = async (projectId: string) => {
    try {
      dispatch({ type: 'SET_INITIAL_STATE' })
      
      const project = await api.getProject(projectId)
      
      dispatch({ type: 'SET_CURRENT_PROJECT', payload: projectId })
      dispatch({ type: 'SET_PROJECT_TITLE', payload: project.name })
      
      if (project.documents) {
        dispatch({ 
          type: 'SET_DOCUMENTS', 
          payload: project.documents
        })
      }
      
      if (project.analysis) {
        dispatch({
          type: 'SET_MODE',
          payload: project.analysis.mode
        })
        
        if (project.analysis.tableData) {
          dispatch({
            type: 'UPDATE_TABLE_DATA',
            payload: project.analysis.tableData
          })
        }
      }
      
      if (project.messages) {
        project.messages.forEach(message => {
          dispatch({
            type: 'ADD_MESSAGE',
            payload: message
          })
        })
      }
      
      dispatch({ 
        type: 'SET_VIEW', 
        payload: project.analysis?.mode || 'table' 
      })
      
    } catch (error) {
      console.error('프로젝트 로드 실패:', error)
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
      // onDragUpdate={(update) => {
      //   console.log('Drag Update:', {
      //     draggableId: update.draggableId,
      //     source: update.source,
      //     destination: update.destination,
      //     time: new Date().toISOString()
      //   });
      // }}
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
      <div className="w-[250px] border-r bg-gray-200 flex flex-col h-full">
        <div className="p-4 flex items-center justify-between flex-shrink-0 border-b">
          <div className="flex items-center gap-2">
            <ScrollText className="h-6 w-6 text-primary" />
            <h2 className="text-lg font-semibold tracking-tight">DocEasy</h2>
          </div>
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
                      // 현재 프로젝트 상태 저장
                      if (state.currentProject) {
                        await api.autosaveProject(state.currentProject, {
                          title: state.projectTitle,
                          documents: state.documents,
                          messages: state.messages,
                          analysis: state.analysis,
                          currentView: state.currentView
                        });
                      }

                      // 앱 상태 초기화
                      dispatch({ type: 'SET_INITIAL_STATE' });
                      
                    } catch (error) {
                      console.error('Error saving current project:', error);
                    } finally {
                      setIsLoading(false);
                    }
                  }}
                >
                  <PenSquare className={cn("h-4 w-4", isLoading && "animate-spin")} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>새로 만들기</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
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
              />
            </div>
          </div>
        </div>
      </div>
    </DragDropContext>
  )
}
