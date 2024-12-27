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
  Clock,
  ChevronDown,
  ChevronRight,
  FileText,
  Zap,
  Plus,
  AlertTriangle,
  Trash2,
  AlertCircle,
  Layout,
  PenSquare
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
  const [recentProjects, setRecentProjects] = useState<ProjectGroup>({ 
    today: [], 
    yesterday: [], 
    fourDaysAgo: [],
    older: [] 
  })
  const [isLoading, setIsLoading] = useState(true)
  const [expandedSections, setExpandedSections] = useState<string[]>(['recent', 'template'])
  const [newCategoryName, setNewCategoryName] = useState('')
  const [categoryError, setCategoryError] = useState('')
  const [isAddingCategory, setIsAddingCategory] = useState(false)
  const [isTemplateDialogOpen, setIsTemplateDialogOpen] = useState(false);
  const [categoryToDelete, setCategoryToDelete] = useState<Category | null>(null);

  // 프로젝트 목록 조회 함수
  const fetchProjects = async () => {
    try {
      const response = await api.getRecentProjects()
      
      // API 응답을 ProjectGroup 형식으로 변환
      const groupedProjects: ProjectGroup = {
        today: response.today.map(item => ({
          id: item.id,
          name: item.title,
          created_at: item.created_at,
          formatted_date: item.formatted_date,
          is_temporary: true,
          will_be_deleted: false
        })),
        yesterday: response.yesterday.map(item => ({
          id: item.id,
          name: item.title,
          created_at: item.created_at,
          formatted_date: item.formatted_date,
          is_temporary: true,
          will_be_deleted: false
        })),
        fourDaysAgo: response.four_days_ago.map(item => ({
          id: item.id,
          name: item.title,
          created_at: item.created_at,
          formatted_date: item.formatted_date,
          is_temporary: true,
          will_be_deleted: true
        })),
        older: []
      }

      setRecentProjects(groupedProjects)
    } catch (error) {
      console.error('프로젝트 목록 조회 실패:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  useEffect(() => {
    const handleProjectCreated = () => {
      fetchProjects()
    }

    window.addEventListener('projectCreated', handleProjectCreated)
    return () => {
      window.removeEventListener('projectCreated', handleProjectCreated)
    }
  }, [])

  // 카테고리 로드
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

  // 드래그 종료 핸들러
  const handleDragEnd = async (result: DropResult) => {
    if (!result.destination) return;

    const sourceId = result.draggableId;
    const destinationId = result.destination.droppableId;

    // 카테고리로 드롭된 경우
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
        const updatedRecentProjects = recentProjects.filter(
          project => project.id !== sourceId
        );
        setRecentProjects(updatedRecentProjects);
      } catch (error) {
        console.error('프로젝트 이동 실패:', error);
      }
    }
  };

  // 카테고리 이름 중복 체크
  const isCategoryNameDuplicate = (name: string) => {
    return categories.some(category => category.name === name)
  }

  // 카테고리 추가 핸들러
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
          type: "PERMANENT"  // type을 명시적으로 설정
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
      // 1. 먼저 상태 초기화
      dispatch({ type: 'SET_INITIAL_STATE' })
      
      const project = await api.getProject(projectId)
      
      // 2. 프로젝트 기본 정보 설정
      dispatch({ type: 'SET_CURRENT_PROJECT', payload: projectId })
      dispatch({ type: 'SET_PROJECT_TITLE', payload: project.name })
      
      // 3. 문서 목록 설정
      if (project.documents) {
        dispatch({ 
          type: 'SET_DOCUMENTS', 
          payload: project.documents
        })
      }
      
      // 4. 분석 데이터 설정
      if (project.analysis) {
        // 분석 모드 설정
        dispatch({
          type: 'SET_MODE',
          payload: project.analysis.mode
        })
        
        // 테이블 데이터 설정
        if (project.analysis.tableData) {
          dispatch({
            type: 'UPDATE_TABLE_DATA',
            payload: project.analysis.tableData
          })
        }
      }
      
      // 5. 메시지 설정
      if (project.messages) {
        project.messages.forEach(message => {
          dispatch({
            type: 'ADD_MESSAGE',
            payload: message
          })
        })
      }
      
      // 6. 뷰 설정
      dispatch({ 
        type: 'SET_VIEW', 
        payload: project.analysis?.mode || 'table' 
      })
      
    } catch (error) {
      console.error('프로젝트 로드 실패:', error)
    }
  }

  // 문서 컨텐츠 로드 함수 (필요할 때만 호출)
  const loadDocumentContent = async (docId: string) => {
    try {
      const content = await api.getDocumentContent(state.currentProjectId, docId)
      dispatch({
        type: 'UPDATE_DOCUMENT_CONTENT',
        payload: {
          id: docId,
          content,
          isLoaded: true
        }
      })
    } catch (error) {
      console.error('문서 컨텐츠 로드 실패:', error)
    }
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev =>
      prev.includes(section)
        ? prev.filter(s => s !== section)
        : [...prev, section]
    )
  }

  // 최근 프로젝트 섹션 렌더링
  const renderRecentProjects = () => (
    <div className="space-y-1">
      <Button
        variant="ghost"
        className="w-full justify-start gap-2 px-2"
        onClick={() => toggleSection('recent')}
      >
        <Clock className="h-4 w-4 flex-shrink-0" />
        <span className="text-left flex-grow">최근 프로젝트</span>
        {expandedSections.includes('recent') ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </Button>
      
      {expandedSections.includes('recent') && (
        <div className="space-y-1">
          <Droppable droppableId="recent-projects">
            {(provided) => (
              <div
                ref={provided.innerRef}
                {...provided.droppableProps}
                className="space-y-4"
              >
                {/* 오늘 */}
                {recentProjects.today.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-gray-500 pl-4">오늘</div>
                    {recentProjects.today.map((project, index) => (
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
                            className={`
                              relative flex items-center
                              ${snapshot.isDragging ? 'opacity-50' : ''}
                            `}
                          >
                            <Button
                              variant="ghost"
                              className="w-full justify-start text-sm h-8 pl-4"
                              onClick={() => handleProjectClick(project.id)}
                            >
                              <FileText className="h-4 w-4 mr-2" />
                              <span className="flex-1 text-left truncate">
                                {project.name}
                              </span>
                            </Button>
                          </div>
                        )}
                      </Draggable>
                    ))}
                  </div>
                )}

                {/* 어제 */}
                {recentProjects.yesterday.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-gray-500 pl-4">어제</div>
                    {recentProjects.yesterday.map((project, index) => (
                      <Draggable
                        key={project.id}
                        draggableId={project.id}
                        index={recentProjects.today.length + index}
                      >
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            className={`
                              relative flex items-center
                              ${snapshot.isDragging ? 'opacity-50' : ''}
                            `}
                          >
                            <Button
                              variant="ghost"
                              className="w-full justify-start text-sm h-8 pl-4"
                              onClick={() => handleProjectClick(project.id)}
                            >
                              <FileText className="h-4 w-4 mr-2" />
                              <span className="flex-1 text-left truncate">
                                {project.name}
                              </span>
                            </Button>
                          </div>
                        )}
                      </Draggable>
                    ))}
                  </div>
                )}

                {/* 4일 전 */}
                {recentProjects.fourDaysAgo.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-gray-500 pl-4">4일 전</div>
                    {recentProjects.fourDaysAgo.map((project, index) => (
                      <Draggable
                        key={project.id}
                        draggableId={project.id}
                        index={recentProjects.today.length + recentProjects.yesterday.length + index}
                      >
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            className={`
                              relative flex items-center
                              ${snapshot.isDragging ? 'opacity-50' : ''}
                            `}
                          >
                            <Button
                              variant="ghost"
                              className="w-full justify-start text-sm h-8 pl-4"
                              onClick={() => handleProjectClick(project.id)}
                            >
                              <FileText className="h-4 w-4 mr-2" />
                              <span className="flex-1 text-left truncate">
                                {project.name}
                              </span>
                            </Button>
                          </div>
                        )}
                      </Draggable>
                    ))}
                  </div>
                )}
                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </div>
      )}
    </div>
  )

  // 템플릿 섹션 렌더링
  const renderTemplates = () => (
    <div className="space-y-1">
      <Button
        variant="ghost"
        className="w-full justify-start gap-2 px-2"
        onClick={() => toggleSection('templates')}
      >
        <Layout className="h-4 w-4 flex-shrink-0" />
        <span className="text-left flex-grow">템플릿</span>
        {expandedSections.includes('templates') ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </Button>
      
      {expandedSections.includes('templates') && (
        <div className="pl-2 space-y-1">
          {templates.map(template => (
            <Popover key={template.id}>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm h-8 pl-4"
                >
                  <FileText className="h-4 w-4 mr-2" />
                  <span className="flex-1 text-left truncate">
                    {template.name}
                  </span>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-80 p-4">
                <div className="space-y-2">
                  <h4 className="font-medium">{template.name}</h4>
                  <p className="text-sm text-muted-foreground">
                    {template.description}
                  </p>
                  <Button 
                    className="w-full"
                    onClick={() => {
                      // TODO: 템플릿 사용 로직 구현
                      console.log('템플릿 사용:', template.id);
                    }}
                  >
                    이 템플릿 사용하기
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
          ))}
        </div>
      )}
    </div>
  )

  // 프로젝트 폴더 섹션 렌더링
  const renderCategories = () => (
    <div className="space-y-1">
      <Button
        variant="ghost"
        className="w-full justify-start gap-2 px-2"
        onClick={() => toggleSection('folders')}
      >
        <Folder className="h-4 w-4 flex-shrink-0" />
        <span className="text-left flex-grow">프로젝트 폴더</span>
        {expandedSections.includes('folders') ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </Button>
      
      {expandedSections.includes('folders') && (
        <div className="space-y-1">
          {categories.map(category => (
            <Droppable key={category.id} droppableId={`category-${category.id}`}>
              {(provided, snapshot) => (
                <div
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  className={`rounded group ${snapshot.isDraggingOver ? 'bg-gray-100' : ''}`}
                >
                  <div className="relative flex items-center">
                    <Button
                      variant="ghost"
                      className="w-full justify-start text-sm h-8 pl-4"
                    >
                      <Folder className="h-4 w-4 mr-2" />
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
      )}
    </div>
  )

  const handleDeleteCategory = async () => {
    if (!categoryToDelete) return;

    try {
      await fetch(`/api/v1/categories/${categoryToDelete.id}`, {
        method: 'DELETE',
      });
      
      // 카테고리 목록 새로고침
      const updatedCategories = categories.filter(c => c.id !== categoryToDelete.id);
      setCategories(updatedCategories);
      setCategoryToDelete(null);
    } catch (error) {
      console.error('카테고리 삭제 실패:', error);
      // toast({
      //   title: "오류",
      //   description: "폴더를 삭제하는 중 문제가 발생했습니다.",
      //   variant: "destructive",
      // });
    }
  };

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className={`w-[250px] border-r bg-gray-200 ${className || ''}`}>
        <div className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-6 w-6 text-primary" />
            <span className="text-xl font-bold text-primary">Intellio</span>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <PenSquare className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-auto p-2">
          <div className="space-y-6">
            <div className="space-y-1">
              {renderTemplates()}
            </div>
            <div className="space-y-1">
              {renderRecentProjects()}
            </div>
            <div className="space-y-1">
              {renderCategories()}
            </div>
          </div>
        </div>
      </div>
    </DragDropContext>
  )
}
