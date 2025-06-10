'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Loader2, Send, Copy, RefreshCw } from 'lucide-react'

// 백엔드 API 기본 URL
const API_BASE_URL = 'http://localhost:8001'

interface IApiResponse {
  data?: any
  status: string
  message?: string
  error?: string
}

interface IApiCall {
  url: string
  method: 'GET' | 'POST'
  body?: any
  description: string
}

export default function ApiTestPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [response, setResponse] = useState<IApiResponse | null>(null)
  const [selectedApi, setSelectedApi] = useState<string>('')
  
  // 테스트용 입력값들
  const [stockCode, setStockCode] = useState('005930')
  const [etfCode, setEtfCode] = useState('069500')
  const [searchKeyword, setSearchKeyword] = useState('삼성')
  const [chartPeriod, setChartPeriod] = useState('1y')
  const [chartInterval, setChartInterval] = useState('1d')

  // 날짜 계산 함수
  const getDateRange = () => {
    const today = new Date()
    const threeMonthsAgo = new Date()
    threeMonthsAgo.setMonth(today.getMonth() - 3)
    
    const formatDate = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}${month}${day}`
    }
    
    return {
      startDate: formatDate(threeMonthsAgo),
      endDate: formatDate(today)
    }
  }

  // API 호출 함수
  const callApi = async (apiCall: IApiCall) => {
    setIsLoading(true)
    setSelectedApi(apiCall.description)
    
    try {
      const config: RequestInit = {
        method: apiCall.method,
        headers: {
          'Content-Type': 'application/json',
        },
      }
      
      if (apiCall.body) {
        config.body = JSON.stringify(apiCall.body)
      }
      
      const response = await fetch(`${API_BASE_URL}${apiCall.url}`, config)
      const data = await response.json()
      
      if (response.ok) {
        setResponse(data)
        toast.success(`API 호출 성공: ${apiCall.description}`)
      } else {
        setResponse({
          status: 'error',
          error: data.detail || '요청 실패',
          data
        })
        toast.error(`API 호출 실패: ${data.detail || '요청 실패'}`)
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류'
      setResponse({
        status: 'error',
        error: errorMessage
      })
      toast.error(`네트워크 오류: ${errorMessage}`)
    } finally {
      setIsLoading(false)
    }
  }

  // 응답 복사 함수
  const copyResponse = () => {
    if (response) {
      navigator.clipboard.writeText(JSON.stringify(response, null, 2))
      toast.success('응답이 클립보드에 복사되었습니다')
    }
  }

  // 응답 초기화 함수
  const clearResponse = () => {
    setResponse(null)
    setSelectedApi('')
  }

  return (
    <div className="space-y-6">
      <Tabs defaultValue="stock" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="stock">주식 API</TabsTrigger>
          <TabsTrigger value="etf">ETF API</TabsTrigger>
          <TabsTrigger value="market">시장 API</TabsTrigger>
          <TabsTrigger value="admin">관리 API</TabsTrigger>
        </TabsList>

        {/* 주식 API 테스트 */}
        <TabsContent value="stock" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>주식 데이터 API 테스트</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="stockCode">종목 코드</Label>
                  <Input
                    id="stockCode"
                    value={stockCode}
                    onChange={(e) => setStockCode(e.target.value)}
                    placeholder="예: 005930"
                  />
                </div>
                <div>
                  <Label htmlFor="searchKeyword">검색 키워드</Label>
                  <Input
                    id="searchKeyword"
                    value={searchKeyword}
                    onChange={(e) => setSearchKeyword(e.target.value)}
                    placeholder="예: 삼성"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="chartPeriod">차트 기간</Label>
                  <Input
                    id="chartPeriod"
                    value={chartPeriod}
                    onChange={(e) => setChartPeriod(e.target.value)}
                    placeholder="예: 1d, 1m, 1y"
                  />
                </div>
                <div>
                  <Label htmlFor="chartInterval">차트 간격</Label>
                  <Input
                    id="chartInterval"
                    value={chartInterval}
                    onChange={(e) => setChartInterval(e.target.value)}
                    placeholder="예: 1m, 5m, 1h"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/stock/list_for_stockai',
                    method: 'GET',
                    description: '전체 종목 리스트 조회'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  전체 종목 리스트
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: `/api/v1/stock/search?keyword=${searchKeyword}&limit=10`,
                    method: 'GET',
                    description: '종목명 검색'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  종목명 검색
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: `/api/v1/stock/price/${stockCode}`,
                    method: 'GET',
                    description: '실시간 주식 가격 조회'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  실시간 가격
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: `/api/v1/stock/info/${stockCode}`,
                    method: 'GET',
                    description: '종목 기본정보 조회'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  기본정보
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: `/api/v1/stock/chart/${stockCode}?period=${chartPeriod}&interval=${chartInterval}&compressed=true&gzip_enabled=true`,
                    method: 'GET',
                    description: '차트 데이터 조회 (압축)'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  차트 데이터 (압축)
                </Button>
                
                <Button
                  onClick={() => {
                    const { startDate, endDate } = getDateRange()
                    callApi({
                      url: `/api/v1/stock/supply-demand/${stockCode}?start_date=${startDate}&end_date=${endDate}&compressed=true&gzip_enabled=false`,
                      method: 'GET',
                      description: '수급 데이터 조회 (표준)'
                    })
                  }}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  수급 데이터 (표준)
                </Button>
                
                <Button
                  onClick={() => {
                    const { startDate, endDate } = getDateRange()
                    callApi({
                      url: `/api/v1/stock/supply-demand/${stockCode}?start_date=${startDate}&end_date=${endDate}&compressed=true&gzip_enabled=true`,
                      method: 'GET',
                      description: '수급 데이터 조회 (압축)'
                    })
                  }}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  수급 데이터 (압축)
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/stock/list/refresh',
                    method: 'GET',
                    description: '종목 리스트 새로고침'
                  })}
                  disabled={isLoading}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  리스트 새로고침
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ETF API 테스트 */}
        <TabsContent value="etf" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>ETF 데이터 API 테스트</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="etfCode">ETF 코드</Label>
                <Input
                  id="etfCode"
                  value={etfCode}
                  onChange={(e) => setEtfCode(e.target.value)}
                  placeholder="예: 069500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/etf/list',
                    method: 'GET',
                    description: 'ETF 목록 조회'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  ETF 목록
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: `/api/v1/etf/components/${etfCode}`,
                    method: 'GET',
                    description: 'ETF 구성종목 조회'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  구성종목 조회
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: `/api/v1/etf/components/${etfCode}/refresh`,
                    method: 'POST',
                    description: 'ETF 구성종목 갱신'
                  })}
                  disabled={isLoading}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  구성종목 갱신
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/etf/components/refresh-all',
                    method: 'POST',
                    description: '모든 ETF 구성종목 일괄 갱신'
                  })}
                  disabled={isLoading}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  전체 갱신
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 시장 API 테스트 */}
        <TabsContent value="market" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>시장 데이터 API 테스트</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/market/status',
                    method: 'GET',
                    description: '시장 상태 조회'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  시장 상태
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/market/indices',
                    method: 'GET',
                    description: '주요 지수 조회'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  주요 지수
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 관리 API 테스트 */}
        <TabsContent value="admin" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>관리 API 테스트</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/admin/system/health',
                    method: 'GET',
                    description: '시스템 헬스 체크'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  헬스 체크
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/admin/system/stats',
                    method: 'GET',
                    description: '시스템 통계'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  시스템 통계
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/admin/cache/stats',
                    method: 'GET',
                    description: '캐시 통계'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  캐시 통계
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/admin/etf/stats',
                    method: 'GET',
                    description: 'ETF 크롤러 통계'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  ETF 통계
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/admin/scheduler/trigger/etf',
                    method: 'POST',
                    description: 'ETF 업데이트 실행'
                  })}
                  disabled={isLoading}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  ETF 업데이트
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: '/api/v1/admin/cache/clear',
                    method: 'POST',
                    description: '캐시 초기화'
                  })}
                  disabled={isLoading}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  캐시 초기화
                </Button>
                
                <Button
                  onClick={() => callApi({
                    url: `/api/v1/admin/debug/supply-demand/${stockCode}?limit=10`,
                    method: 'GET',
                    description: '수급 데이터 디버깅'
                  })}
                  disabled={isLoading}
                >
                  <Send className="w-4 h-4 mr-2" />
                  수급 데이터 디버깅
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 응답 결과 표시 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              API 응답 결과
              {selectedApi && (
                <Badge variant="outline" className="text-sm">
                  {selectedApi}
                </Badge>
              )}
            </CardTitle>
            <div className="flex gap-2">
              {response && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyResponse}
                >
                  <Copy className="w-4 h-4 mr-2" />
                  복사
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={clearResponse}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                초기화
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-600">API 호출 중...</span>
            </div>
          ) : response ? (
            <Textarea
              value={JSON.stringify(response, null, 2)}
              readOnly
              className="min-h-[400px] font-mono text-sm"
            />
          ) : (
            <div className="flex items-center justify-center py-8 text-gray-500">
              API를 호출하면 결과가 여기에 표시됩니다.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
} 