'use client'

import { useRef, useState } from 'react'
import { uploadDocument } from '@/lib/api'

interface Props {
  onUploadSuccess: (documentId: string, taskId: string) => void
}

export default function FileUpload({ onUploadSuccess }: Props) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('仅支持 PDF 文件')
      return
    }
    setError(null)
    setIsUploading(true)
    try {
      const result = await uploadDocument(file)
      onUploadSuccess(result.document_id, result.task_id)
    } catch {
      setError('上传失败，请重试')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div
      className={[
        'border-2 border-dashed rounded-xl p-14 text-center transition-colors cursor-pointer select-none',
        isDragging ? 'border-indigo-400 bg-indigo-950/30' : 'border-gray-700 hover:border-gray-500',
      ].join(' ')}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files[0]) }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      {isUploading ? (
        <p className="text-indigo-400 animate-pulse text-lg">正在上传...</p>
      ) : (
        <>
          <p className="text-gray-300 text-lg">拖拽 PDF 到此处，或点击选择文件</p>
          <p className="text-gray-600 text-sm mt-2">最大 100 MB · 仅支持 PDF</p>
        </>
      )}
      {error && <p className="text-red-400 mt-3 text-sm">{error}</p>}
    </div>
  )
}
