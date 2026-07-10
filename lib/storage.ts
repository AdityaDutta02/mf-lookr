// lib/storage.ts — Terminal AI Storage SDK (server-side only)
const GATEWAY_URL = process.env.TERMINAL_AI_GATEWAY_URL!

export async function storageUpload(key: string, buffer: Buffer, contentType: string, embedToken: string): Promise<{ key: string }> {
  const res = await fetch(`${GATEWAY_URL}/storage/${key}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${embedToken}`, 'Content-Type': contentType },
    body: buffer as unknown as BodyInit,
  })
  if (!res.ok) throw new Error(`Storage upload failed: ${res.status}`)
  return res.json() as Promise<{ key: string }>
}

export async function storageGet(key: string, embedToken: string): Promise<Response> {
  const res = await fetch(`${GATEWAY_URL}/storage/${key}`, { headers: { Authorization: `Bearer ${embedToken}` } })
  if (!res.ok) throw new Error(`Storage get failed: ${res.status}`)
  return res
}

export async function storageList(embedToken: string): Promise<Array<{ key: string; size: number; lastModified: string }>> {
  const res = await fetch(`${GATEWAY_URL}/storage`, { headers: { Authorization: `Bearer ${embedToken}` } })
  if (!res.ok) throw new Error(`Storage list failed: ${res.status}`)
  return res.json() as Promise<Array<{ key: string; size: number; lastModified: string }>>
}

export async function storageDelete(key: string, embedToken: string): Promise<void> {
  const res = await fetch(`${GATEWAY_URL}/storage/${key}`, { method: 'DELETE', headers: { Authorization: `Bearer ${embedToken}` } })
  if (!res.ok) throw new Error(`Storage delete failed: ${res.status}`)
}

export async function getPresignedUploadUrl(
  key: string, contentType: string, sizeBytes: number, embedToken: string,
): Promise<{ url: string; key: string; expiresIn: number; maxBytes: number }> {
  const res = await fetch(`${GATEWAY_URL}/storage/presign-upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${embedToken}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, content_type: contentType, size_bytes: sizeBytes }),
  })
  if (!res.ok) throw new Error(`Presigned upload URL failed: ${res.status}`)
  return res.json() as Promise<{ url: string; key: string; expiresIn: number; maxBytes: number }>
}

export async function getPresignedDownloadUrl(
  key: string, embedToken: string,
): Promise<{ url: string; expiresIn: number }> {
  const res = await fetch(`${GATEWAY_URL}/storage/presign-download`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${embedToken}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ key }),
  })
  if (!res.ok) throw new Error(`Presigned download URL failed: ${res.status}`)
  return res.json() as Promise<{ url: string; expiresIn: number }>
}
