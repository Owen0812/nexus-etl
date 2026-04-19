const BASE = '/api/v1'

export async function uploadDocument(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/documents/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getTaskStatus(taskId: string) {
  const res = await fetch(`${BASE}/pipelines/task/${taskId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getDocument(documentId: string) {
  const res = await fetch(`${BASE}/documents/${documentId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listDocuments(skip = 0, limit = 20) {
  const res = await fetch(`${BASE}/documents?skip=${skip}&limit=${limit}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
