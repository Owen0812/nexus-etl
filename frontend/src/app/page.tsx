import Link from 'next/link'

export default function Home() {
  return (
    <div className="max-w-2xl mx-auto text-center py-24 space-y-6">
      <h2 className="text-4xl font-bold tracking-tight">智能体驱动 RAG 管道</h2>
      <p className="text-gray-400 text-lg leading-relaxed">
        上传 PDF 文档，6 个 Agent 自动完成增量检查、视觉提取、语义切块、
        元数据标注和质量过滤，最终向量化入库。
      </p>
      <div className="flex justify-center gap-4 pt-4">
        <Link
          href="/dashboard"
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-lg font-medium transition-colors"
        >
          进入控制台
        </Link>
        <a
          href="/api/v1/health"
          target="_blank"
          className="border border-gray-700 hover:border-gray-500 text-gray-300 px-6 py-3 rounded-lg font-medium transition-colors"
        >
          API 状态
        </a>
      </div>
    </div>
  )
}
