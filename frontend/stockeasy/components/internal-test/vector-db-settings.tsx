'use client'

import { useState } from 'react'
import { Input } from 'intellio-common/components/ui/input'
import { Label } from 'intellio-common/components/ui/label'
import { Textarea } from '../../../main/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '../../../main/components/ui/card'
import { Switch } from '../../../main/components/ui/switch'
import { toast } from 'sonner'

export interface IVectorDBConfig {
  namespace: string | null
  metadata_filter: Record<string, any> | null
  top_k: number | null
}

interface VectorDBSettingsProps {
  config: IVectorDBConfig
  onChange: (config: IVectorDBConfig) => void
}

export function VectorDBSettings({ config, onChange }: VectorDBSettingsProps) {
  const [showMetadataEditor, setShowMetadataEditor] = useState(!!config.metadata_filter)
  const [metadataString, setMetadataString] = useState(
    config.metadata_filter ? JSON.stringify(config.metadata_filter, null, 2) : '{\n  \n}'
  )
  const [isValidJson, setIsValidJson] = useState(true)

  const handleNamespaceChange = (namespace: string) => {
    onChange({
      ...config,
      namespace: namespace.trim() || null
    })
  }

  const handleTopKChange = (topK: string) => {
    const parsedTopK = parseInt(topK, 10)
    onChange({
      ...config,
      top_k: isNaN(parsedTopK) ? null : parsedTopK
    })
  }

  const handleMetadataChange = (metadata: string) => {
    setMetadataString(metadata)
    
    try {
      if (metadata.trim()) {
        const parsedMetadata = JSON.parse(metadata)
        setIsValidJson(true)
        onChange({
          ...config,
          metadata_filter: parsedMetadata
        })
      } else {
        setIsValidJson(true)
        onChange({
          ...config,
          metadata_filter: null
        })
      }
    } catch (e) {
      setIsValidJson(false)
    }
  }

  const handleToggleMetadataEditor = (enabled: boolean) => {
    setShowMetadataEditor(enabled)
    if (!enabled) {
      onChange({
        ...config,
        metadata_filter: null
      })
      setMetadataString('{\n  \n}')
      setIsValidJson(true)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>벡터 DB 설정</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="namespace">네임스페이스</Label>
          <Input
            id="namespace"
            placeholder="기본 네임스페이스 사용"
            value={config.namespace || ''}
            onChange={(e) => handleNamespaceChange(e.target.value)}
          />
          <p className="text-sm text-muted-foreground">
            비워두면 기본 네임스페이스가 사용됩니다.
          </p>
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="top_k">검색 결과 수 (Top K)</Label>
          <Input
            id="top_k"
            type="number"
            placeholder="기본값 사용"
            min="1"
            max="100"
            value={config.top_k || ''}
            onChange={(e) => handleTopKChange(e.target.value)}
          />
          <p className="text-sm text-muted-foreground">
            비워두면 기본값이 사용됩니다.
          </p>
        </div>
        
        <div className="space-y-2 pt-4 border-t">
          <div className="flex items-center justify-between">
            <Label htmlFor="use-metadata">메타데이터 필터 사용</Label>
            <Switch
              id="use-metadata"
              checked={showMetadataEditor}
              onCheckedChange={handleToggleMetadataEditor}
            />
          </div>
          
          {showMetadataEditor && (
            <div className="space-y-2 mt-4">
              <Label htmlFor="metadata_filter">
                메타데이터 필터 (JSON)
                {!isValidJson && (
                  <span className="ml-2 text-destructive text-sm">유효하지 않은 JSON 형식</span>
                )}
              </Label>
              <Textarea
                id="metadata_filter"
                placeholder='{ "key": "value" }'
                rows={6}
                className={`font-mono ${!isValidJson ? 'border-destructive' : ''}`}
                value={metadataString}
                onChange={(e) => handleMetadataChange(e.target.value)}
              />
              <p className="text-sm text-muted-foreground">
                메타데이터 필터를 JSON 형식으로 입력하세요.
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
} 