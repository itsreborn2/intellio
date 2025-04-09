import Link from "next/link"
import { Github, Twitter, Linkedin } from "lucide-react"

export default function Footer() {
  return (
    <footer className="border-0 mt-auto pt-12">
      <div className="container py-16">
        <div className="mx-auto max-w-4xl text-center">
          <div className="mb-4">
            <p className="font-medium text-sm">주식회사 인텔리오</p>
            <div className="text-xs text-muted-foreground space-y-1 mt-3">
              <p>대표이사 : 김상균, 조훈</p>
              <p>경기도 수원시 영통구 대학4로 17, 316-47호(이의동)</p>
              <p>사업자 등록번호 : 819-88-03184</p>
              <p>E-mail : intellio.korea@gmail.com</p>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground mt-6">
            © 2025 Intellio Corporation All Rights Reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}

