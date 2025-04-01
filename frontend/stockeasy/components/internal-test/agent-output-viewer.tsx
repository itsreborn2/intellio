'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, Clock, Play, AlertCircle } from 'lucide-react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../../main/components/ui/accordion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../main/components/ui/card'
import { Badge } from '../../../main/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../main/components/ui/tabs'
import { ScrollArea } from '../../../main/components/ui/scroll-area'

interface AgentResult {
  agent_name: string
  input: Record<string, any>
  output: Record<string, any>
  error: string | null
  execution_time: number
}

interface AgentOutputViewerProps {
  agentResults: AgentResult[]
  totalExecutionTime: number
  answer: string
}

export function AgentOutputViewer({ agentResults, totalExecutionTime, answer }: AgentOutputViewerProps) {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)

  // JSON을 포맷팅하여 출력
  const formatJson = (data: any) => {
    try {
      return JSON.stringify(data, null, 2)
    } catch (error) {
      return 'Error parsing JSON'
    }
  }

  // 에이전트 결과를 시간순으로 정렬
  const sortedResults = [...agentResults].sort((a, b) => {
    const aName = a.agent_name.toLowerCase();
    const bName = b.agent_name.toLowerCase();
    
    // orchestrator를 항상 맨 위로
    if (aName === 'orchestrator') return -1;
    if (bName === 'orchestrator') return 1;
    
    // 그 다음에 question_analyzer
    if (aName === 'question_analyzer' && bName !== 'orchestrator') return -1;
    if (bName === 'question_analyzer' && aName !== 'orchestrator') return 1;
    
    // 기본적으로는 알파벳 순
    return aName.localeCompare(bName);
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex justify-between">
            <span>최종 응답</span>
            <Badge variant="outline" className="ml-2 font-mono">
              <Clock className="mr-1 h-3 w-3" />
              {totalExecutionTime.toFixed(2)}초
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[200px] rounded-md border p-4">
            <div className="whitespace-pre-wrap">{answer}</div>
          </ScrollArea>
        </CardContent>
      </Card>

      <div>
        <h3 className="text-lg font-medium mb-4">에이전트별 실행 결과 ({agentResults.length}개)</h3>
        
        <div className="space-y-4">
          {sortedResults.map((result) => (
            <Card 
              key={result.agent_name}
              className={`${result.error ? 'border-destructive' : ''}`}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex justify-between">
                  <div className="flex items-center">
                    {result.error ? (
                      <AlertCircle className="mr-2 h-4 w-4 text-destructive" />
                    ) : (
                      <Play className="mr-2 h-4 w-4 text-primary" />
                    )}
                    {result.agent_name}
                  </div>
                  <Badge variant="outline" className="ml-2 font-mono text-xs">
                    <Clock className="mr-1 h-3 w-3" />
                    {result.execution_time.toFixed(2)}초
                  </Badge>
                </CardTitle>
                {result.error && (
                  <CardDescription className="text-destructive">
                    {result.error}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="input">
                  <TabsList className="mb-2">
                    <TabsTrigger value="input">입력</TabsTrigger>
                    <TabsTrigger value="output">출력</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="input">
                    <ScrollArea className="h-[200px] rounded-md border p-4">
                      <pre className="text-xs font-mono">{formatJson(result.input)}</pre>
                    </ScrollArea>
                  </TabsContent>
                  
                  <TabsContent value="output">
                    <ScrollArea className="h-[200px] rounded-md border p-4">
                      <pre className="text-xs font-mono">{formatJson(result.output)}</pre>
                    </ScrollArea>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
} 