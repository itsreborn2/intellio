"use client"

import { Button } from '@/components/ui/button'
import { FileType, ChevronDown, ChevronRight } from 'lucide-react'

interface TemplateSectionProps {
  expandedSections: string[]
  toggleSection: (section: string) => void
}

export function TemplateSection({
  expandedSections,
  toggleSection
}: TemplateSectionProps) {
  return (
    <div className="space-y-1">
      <Button
        variant="ghost"
        className="w-full justify-start gap-2 px-2"
        onClick={() => toggleSection('templates')}
      >
        <FileType className="h-4 w-4 flex-shrink-0" />
        <span className="text-left flex-grow">템플릿</span>
        {expandedSections.includes('templates') ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </Button>
      
      {expandedSections.includes('templates') && (
        <div className="space-y-1">
          {/* 템플릿 목록은 향후 구현 */}
          <div className="text-xs text-gray-500 pl-4">
            템플릿 기능은 곧 제공될 예정입니다
          </div>
        </div>
      )}
    </div>
  )
}
