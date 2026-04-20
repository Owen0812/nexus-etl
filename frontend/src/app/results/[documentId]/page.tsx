'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { getDocument, getDocumentChunks } from '@/lib/api'

interface ChunkMeta {
  section_title?: string
  content_type?: string
  entities?: string[]
  importance_score?: number
}

interface Chunk {
  id: string
  chunk_index: number
  chunk_type: string | null
  token_count: number | null
  quality_score: number | null
  content: string
  chunk_metadata: ChunkMeta | null
}

interface DocInfo {
  filename: string
  status: string
  created_at: string
}

function QualityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.7 ? 'bg-green-500' : score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400 tabular-nums">{pct}</span>
    </div>
  )
}

function TypeBadge({ type }: { type: string | null }) {
  const styles: Record<string, string> = {
    table: 'bg-blue-900/60 text-blue-300',
    text:  'bg-gray-800 text-gray-400',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-mono ${styles[type ?? 'text'] ?? styles.text}`}>
      {type ?? 'text'}
    </span>
  )
}

function ChunkCard({ chunk }: { chunk: Chunk }) {
  const [expanded, setExpanded] = useState(false)
  const meta = chunk.chunk_metadata

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <span className="text-gray-600 text-xs font-mono">#{chunk.chunk_index}</span>
          <TypeBadge type={chunk.chunk_type} />
          {meta?.section_title && (
            <span className="text-gray-300 text-sm font-medium truncate max-w-xs">
              {meta.section_title}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          {chunk.token_count != null && <span>{chunk.token_count} tokens</span>}
          {chunk.quality_score != null && <QualityBar score={chunk.quality_score} />}
        </div>
      </div>

      {/* Content */}
      <div
        className={`text-sm text-gray-300 leading-relaxed whitespace-pre-wrap font-mono bg-gray-950 rounded-lg p-3 ${
          !expanded ? 'max-h-24 overflow-hidden relative' : ''
        }`}
      >
        {chunk.content}
        {!expanded && (
          <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-gray-950" />
        )}
      </div>
      <button
        onClick={() => setExpanded(v => !v)}
        className="text-xs text-indigo-400 hover:text-indigo-300"
      >
        {expanded ? '收起' : '展开全文'}
      </button>

      {/* Metadata pills */}
      {meta && (
        <div className="flex flex-wrap gap-2 pt-1">
          {meta.content_type && (
            <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
              {meta.content_type}
            </span>
          )}
          {meta.importance_score != null && (
            <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
              重要度 {meta.importance_score.toFixed(2)}
            </span>
          )}
          {meta.entities?.slice(0, 5).map(e => (
            <span key={e} className="text-xs bg-indigo-900/40 text-indigo-300 px-2 py-0.5 rounded">
              {e}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ResultsPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const [doc, setDoc] = useState<DocInfo | null>(null)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [docData, chunkData] = await Promise.all([
          getDocument(documentId),
          getDocumentChunks(documentId),
        ])
        setDoc(docData)
        setChunks(chunkData)
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [documentId])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-20 text-center text-gray-500 animate-pulse">
        加载中…
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto py-20 text-center text-red-400">{error}</div>
    )
  }

  const tableCount = chunks.filter(c => c.chunk_type === 'table').length
  const avgScore = chunks.length
    ? chunks.reduce((s, c) => s + (c.quality_score ?? 0), 0) / chunks.length
    : 0

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back + title */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard" className="text-gray-500 hover:text-gray-300 text-sm">
          ← 返回控制台
        </Link>
      </div>

      <div>
        <h2 className="text-2xl font-semibold text-gray-100 truncate">{doc?.filename}</h2>
        <p className="text-gray-500 text-sm mt-1">
          {doc?.created_at ? new Date(doc.created_at).toLocaleString('zh-CN') : ''} · 状态: {doc?.status}
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '总切块', value: chunks.length },
          { label: '表格块', value: tableCount },
          { label: '平均质量分', value: (avgScore * 100).toFixed(1) + '%' },
        ].map(stat => (
          <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-indigo-400">{stat.value}</div>
            <div className="text-xs text-gray-500 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Chunk list */}
      <div className="space-y-3">
        {chunks.length === 0 ? (
          <p className="text-gray-600 text-center py-12">暂无切块数据</p>
        ) : (
          chunks.map(chunk => <ChunkCard key={chunk.id} chunk={chunk} />)
        )}
      </div>
    </div>
  )
}
