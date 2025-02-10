import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Send } from "lucide-react"

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center">
        <Link href="/" className="mr-6 flex items-center space-x-2">
          <span className="font-bold">Intellio</span>
        </Link>
        <nav className="flex flex-1 items-center space-x-6 text-sm font-medium">
          <Link href="/solutions" className="transition-colors hover:text-primary">
            솔루션
          </Link>
          <Link href="/industries" className="transition-colors hover:text-primary">
            서비스
          </Link>
          <Link href="/about" className="transition-colors hover:text-primary">
            About Us
          </Link>
        </nav>
        <div className="flex items-center space-x-4">
          <Link href="https://t.me/maddingStock" target="_blank" rel="noreferrer">
            <Button variant="ghost" size="icon">
              <Send className="h-4 w-4" />
              <span className="sr-only">Telegram</span>
            </Button>
          </Link>
          <Button size="sm">업무 자동화 문의</Button>
        </div>
      </div>
    </header>
  )
}

