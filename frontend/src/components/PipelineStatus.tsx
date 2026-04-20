'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getTaskStatus } from '@/lib/api'

const STAGES: [string, string][] = [
  ['increment_checker', '增量检查'],
  ['orchestrator',      '任务编排'],
  ['vision_extractor',  '视觉提取'],
  ['semantic_chunker',  '语义切块'],
  ['metadata_tagger',   '元数据标注'],
  ['quality_agent',     '质量过滤'],
  ['embedding_writer',  '向量写入'],
]

// Stage that logically comes after the last completed one
function nextStage(done: string[]): string | null {
  for (const [key] of STAGES) {
    if (!done.includes(key)) return key
  }
  return null
}

interface QualityReport {
  total_chunks: number
  passed_chunks: number
  filtered_out: number
  avg_quality_score: number
  pass_rate: number
}

interface TaskResult {
  stages_completed?: string[]
  quality_report?: QualityReport
  chunk_count?: number
}

interface Props {
  taskId: string
  documentId: string | null
}

export default function PipelineStatus({ taskId, documentId }: Props) {
  const [status, setStatus] = useState('PENDING')
  const [result, setResult] = useState<TaskResult | null>(null)

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const data = await getTaskStatus(taskId)
        setStatus(data.status)
        // PROGRESS meta and SUCCESS result both carry stages_completed
        if (data.result) setResult(data.result)
        if (['SUCCESS', 'FAILURE'].includes(data.status)) clearInterval(poll)
      } catch { /* keep polling */ }
    }, 2000)
    return () => clearInterval(poll)
  }, [taskId])

  const done: string[] = result?.stages_completed ?? []
  const running = ['PENDING', 'STARTED', 'PROGRESS'].includes(status) ? nextStage(done) : null
  const qr = result?.quality_report

  const statusColor =
    status === 'SUCCESS'  ? 'bg-green-900 text-green-300' :
    status === 'FAILURE'  ? 'bg-red-900 text-red-300' :
    'bg-yellow-900 text-yellow-300 animate-pulse'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-200">Pipeline 执行状态</h3>
        <span className={`text-xs px-3 py-1 rounded-full font-mono ${statusColor}`}>{status}</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {STAGES.map(([key, label]) => {
          const isDone    = done.includes(key)
          const isRunning = running === key
          return (
            <div
              key={key}
              className={`flex items-center gap-2 text-sm p-2 rounded transition-colors ${
                isDone    ? 'text-green-400' :
                isRunning ? 'text-yellow-300 animate-pulse' :
                'text-gray-600'
              }`}
            >
              <span className="font-mono">
                {isDone ? '✓' : isRunning ? '▶' : '○'}
              </span>
              <span>{label}</span>
            </div>
          )
        })}
      </div>

      {qr && (
        <div className="bg-gray-800/60 rounded-lg p-4 text-sm space-y-2">
          <p className="text-gray-400 font-medium">质量报告</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-gray-300">
            <span>总切块：<strong>{qr.total_chunks}</strong></span>
            <span>通过：<strong className="text-green-400">{qr.passed_chunks}</strong></span>
            <span>过滤：<strong className="text-red-400">{qr.filtered_out}</strong></span>
            <span>平均分：<strong>{qr.avg_quality_score}</strong></span>
            <span>通过率：<strong>{(qr.pass_rate * 100).toFixed(1)}%</strong></span>
            {result?.chunk_count !== undefined && (
              <span>已向量化：<strong className="text-indigo-400">{result.chunk_count}</strong></span>
            )}
          </div>
        </div>
      )}

      {status === 'SUCCESS' && documentId && (
        <Link
          href={`/results/${documentId}`}
          className="inline-block w-full text-center bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium py-2 rounded-lg transition-colors"
        >
          查看切块结果 →
        </Link>
      )}

      {status === 'FAILURE' && (
        <p className="text-red-400 text-sm">Pipeline 处理失败，请重新上传。</p>
      )}

      {documentId && (
        <p className="text-gray-700 text-xs font-mono">doc: {documentId}</p>
      )}
    </div>
  )
}
