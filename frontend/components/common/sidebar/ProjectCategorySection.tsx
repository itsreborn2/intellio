"use client"

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
import { Folder, Plus, Trash2, FileText, ChevronDown, ChevronRight } from 'lucide-react'
import { AlertCircle } from 'lucide-react'
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd'
import * as api from '@/services/api'
import { useRouter } from 'next/navigation'
import { useState, useEffect } from 'react'
import { Category, Project } from '@/services/api'

interface ProjectCategorySectionProps {
  expandedSections: string[]
  toggleSection: (section: string) => void
  recentProjects: {
    today: Project[]
    yesterday: Project[]
    fourDaysAgo: Project[]
    older: Project[]
  }
  categories: Category[]
  setCategories: (categories: Category[]) => void
  dispatch: any
}

export function ProjectCategorySection({
  expandedSections,
  toggleSection,
  recentProjects,
  categories,
  setCategories,
  dispatch
}: ProjectCategorySectionProps) {
  const router = useRouter()
  const [isAddingCategory, setIsAddingCategory] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [categoryError, setCategoryError] = useState('')
  const [categoryToDelete, setCategoryToDelete] = useState<Category | null>(null)

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
      // 1. 먼저 상태 초기화
      dispatch({ type: 'SET_INITIAL_STATE' })
      
      const project = await api.getProject(projectId)
      
      // 2. 프로젝트 기본 정보 설정
      dispatch({ type: 'SET_CURRENT_PROJECT', payload: projectId })
      dispatch({ type: 'SET_PROJECT_TITLE', payload: project.name })
      
      // 3. 페이지 이동
      router.push(`/projects/${projectId}`)
    } catch (error) {
      console.error('프로젝트 로드 실패:', error)
    }
  }

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
    }
  }

  // 드래그 종료 핸들러
  const handleDragEnd = async (result: any) => {
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

        // TODO: 프로젝트 목록 새로고침 로직 추가
      } catch (error) {
        console.error('프로젝트 이동 실패:', error);
      }
    }
  }

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="space-y-6">
        {/* 최근 프로젝트 섹션 */}
        <div className="space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 px-2"
            onClick={() => toggleSection('recent')}
          >
            <FileText className="h-4 w-4 flex-shrink-0" />
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

        {/* 프로젝트 폴더 섹션 */}
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
      </div>
    </DragDropContext>
  )
}
