"use client"

import { useState, useEffect } from "react"
import { Label } from "intellio-common/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "intellio-common/components/ui/select"

export function FontSettings() {
  const [fontSize, setFontSize] = useState("medium")

  // 초기 폰트 크기 설정 로드
  useEffect(() => {
    const savedFontSize = localStorage.getItem("font-size") || "medium"
    setFontSize(savedFontSize)
    document.documentElement.setAttribute("data-font-size", savedFontSize)
  }, [])

  // 폰트 크기 변경 처리
  const handleFontSizeChange = (value: string) => {
    setFontSize(value)
    localStorage.setItem("font-size", value)
    document.documentElement.setAttribute("data-font-size", value)
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>폰트 크기</Label>
        <Select value={fontSize} onValueChange={handleFontSizeChange}>
          <SelectTrigger>
            <SelectValue placeholder="폰트 크기 선택" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="small">작게</SelectItem>
            <SelectItem value="medium">보통</SelectItem>
            <SelectItem value="large">크게</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
