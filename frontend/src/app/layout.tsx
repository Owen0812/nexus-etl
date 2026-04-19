import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Nexus ETL',
  description: 'Intelligent Agent-driven RAG Data Pipeline',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <nav className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
          <span className="text-indigo-400 font-bold text-xl">Nexus ETL</span>
          <span className="text-gray-600 text-sm">智能体驱动 RAG 管道</span>
        </nav>
        <main className="container mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  )
}
