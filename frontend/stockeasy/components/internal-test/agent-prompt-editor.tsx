'use client'

import { useState, useEffect } from 'react'
import { Check, ChevronsUpDown, Plus, Trash } from 'lucide-react'

import { Button } from 'intellio-common/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from '../../../main/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from 'intellio-common/components/ui/popover'
import { Textarea } from '../../../main/components/ui/textarea'
import { Switch } from '../../../main/components/ui/switch'
import { Label } from '../../../main/components/ui/label'
import { cn } from '../../../main/lib/utils'
import { toast } from 'sonner'

export interface IAgentPromptConfig {
  agent_name: string
  prompt_template: string | null
  enabled: boolean
}

interface AgentPromptEditorProps {
  agentConfigs: IAgentPromptConfig[]
  onChange: (configs: IAgentPromptConfig[]) => void
}

export function AgentPromptEditor({ agentConfigs, onChange }: AgentPromptEditorProps) {
  const [configs, setConfigs] = useState<IAgentPromptConfig[]>(agentConfigs)
  const [availableAgents, setAvailableAgents] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        setIsLoading(true)
        const response = await fetch('/api/v1/stockeasy/_internal_test/agents')
        if (!response.ok) throw new Error('에이전트 목록을 가져오는데 실패했습니다.')
        
        const data = await response.json()
        setAvailableAgents(data)
      } catch (error) {
        console.error('에이전트 목록 가져오기 오류:', error)
        toast.error('에이전트 목록을 가져오는데 실패했습니다.')
      } finally {
        setIsLoading(false)
      }
    }

    fetchAgents()
  }, [])

  // 등록되지 않은 에이전트 목록
  const unregisteredAgents = availableAgents.filter(
    (agentName) => !configs.some((config) => config.agent_name === agentName)
  )

  const handleAddAgent = async (agentName: string) => {
    try {
      setIsLoading(true)
      // 에이전트 프롬프트 가져오기
      const response = await fetch(`/api/v1/stockeasy/_internal_test/agent_prompts/${agentName}`)
      if (!response.ok) throw new Error(`${agentName} 에이전트 정보를 가져오는데 실패했습니다.`)
      
      const data = await response.json()
      
      const newConfig: IAgentPromptConfig = {
        agent_name: agentName,
        prompt_template: data.prompt_template,
        enabled: true
      }
      
      const newConfigs = [...configs, newConfig]
      setConfigs(newConfigs)
      onChange(newConfigs)
      toast.success(`${agentName} 에이전트가 추가되었습니다.`)
    } catch (error) {
      console.error('에이전트 추가 오류:', error)
      toast.error(`에이전트 추가 중 오류가 발생했습니다.`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleRemoveAgent = (agentName: string) => {
    const newConfigs = configs.filter((config) => config.agent_name !== agentName)
    setConfigs(newConfigs)
    onChange(newConfigs)
    toast.info(`${agentName} 에이전트가 제거되었습니다.`)
  }

  const handlePromptChange = (agentName: string, prompt: string | null) => {
    const newConfigs = configs.map((config) => 
      config.agent_name === agentName ? { ...config, prompt_template: prompt } : config
    )
    setConfigs(newConfigs)
    onChange(newConfigs)
  }

  const handleEnabledChange = (agentName: string, enabled: boolean) => {
    const newConfigs = configs.map((config) => 
      config.agent_name === agentName ? { ...config, enabled } : config
    )
    setConfigs(newConfigs)
    onChange(newConfigs)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">에이전트 프롬프트 설정</h3>
        
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="w-[200px] justify-between">
              <Plus className="mr-2 h-4 w-4" />
              <span>에이전트 추가</span>
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[200px] p-0">
            <Command>
              <CommandInput placeholder="에이전트 검색..." />
              <CommandEmpty>
                추가할 에이전트가 없습니다.
              </CommandEmpty>
              <CommandGroup>
                {unregisteredAgents.map((agent) => (
                  <CommandItem
                    key={agent}
                    value={agent}
                    onSelect={() => handleAddAgent(agent)}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        "opacity-0"
                      )}
                    />
                    {agent}
                  </CommandItem>
                ))}
              </CommandGroup>
            </Command>
          </PopoverContent>
        </Popover>
      </div>

      {configs.length === 0 ? (
        <div className="text-center py-10 text-muted-foreground">
          에이전트를 추가하여 프롬프트를 테스트해보세요.
        </div>
      ) : (
        <div className="space-y-8">
          {configs.map((config) => (
            <div key={config.agent_name} className="border rounded-lg p-4 bg-card">
              <div className="flex justify-between items-center mb-4">
                <h4 className="font-semibold">{config.agent_name}</h4>
                <div className="flex gap-4 items-center">
                  <div className="flex items-center gap-2">
                    <Switch
                      id={`enabled-${config.agent_name}`}
                      checked={config.enabled}
                      onCheckedChange={(checked: boolean) => handleEnabledChange(config.agent_name, checked)}
                    />
                    <Label htmlFor={`enabled-${config.agent_name}`}>활성화</Label>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveAgent(config.agent_name)}
                  >
                    <Trash className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <Textarea
                placeholder="프롬프트 템플릿을 입력하세요."
                className="min-h-[200px] font-mono text-sm"
                value={config.prompt_template || ''}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => handlePromptChange(config.agent_name, e.target.value)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
} 