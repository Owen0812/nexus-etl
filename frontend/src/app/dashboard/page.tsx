'use client'

import { useState } from 'react'
import FileUpload from '@/components/FileUpload'
import PipelineStatus from '@/components/PipelineStatus'

export default function Dashboard() {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [documentId, setDocumentId] = useState<string | null>(null)

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-semibold mb-1">文档处理控制台</h2>
        <p className="text-gray-500 text-sm">上传 PDF，实时查看 Pipeline 进度</p>
      </div>

      <FileUpload
        onUploadSuccess={(docId, tId) => {
          setDocumentId(docId)
          setTaskId(tId)
        }}
      />

      {taskId && (
        <PipelineStatus taskId={taskId} documentId={documentId} />
      )}
    </div>
  )
}
