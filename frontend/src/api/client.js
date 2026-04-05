/**
 * 开发模式（npm run dev）：默认走同源 `/api`，由 Vite 代理到后端。
 * 生产构建：用 VITE_API_URL。
 * 开发直连后端：frontend/.env 设 VITE_USE_API_PROXY=false
 */
function getBaseUrl() {
  if (import.meta.env.DEV && import.meta.env.VITE_USE_API_PROXY !== 'false') {
    return '/api'
  }
  return (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
}

/** 当前 API 基址（用于界面提示） */
export function getApiBaseUrl() {
  return getBaseUrl()
}

function isNetworkError(err) {
  return err instanceof TypeError && (err.message === 'Failed to fetch' || err.message.includes('fetch'))
}

/** 读 FastAPI 错误体（含非 JSON / detail 为数组时） */
async function readFetchError(res, fallbackLabel) {
  const raw = await res.text()
  let data = {}
  try {
    data = raw ? JSON.parse(raw) : {}
  } catch {
    data = {}
  }
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (detail != null) return JSON.stringify(detail)
  return raw.slice(0, 1200) || `${fallbackLabel}: ${res.status}`
}

export async function fetchEnterprise(id) {
  const base = getBaseUrl()
  let res
  try {
    res = await fetch(`${base}/enterprise/${id}`)
  } catch (err) {
    throw new Error(
      `[API ${base}] 无法连接后端。请确认服务已启动且已执行 docker compose up --build（前端走 /api 代理）。${err.message}`,
    )
  }
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`)
  }
  return res.json()
}

/** POST /rag/search — 语义检索（与 curl 示例一致） */
export async function ragSemanticSearch({ enterpriseId, query, limit = 8 }) {
  const base = getBaseUrl()
  let res
  try {
    res = await fetch(`${base}/rag/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        enterprise_id: enterpriseId,
        query,
        limit,
      }),
    })
  } catch (err) {
    throw new Error(`[RAG search] 无法连接后端。${err.message}`)
  }
  if (!res.ok) {
    throw new Error(await readFetchError(res, 'search failed'))
  }
  return res.json()
}

/** Stable key for localStorage resume metadata */
export function multipartResumeStorageKey(enterpriseId, file) {
  return `s3_multipart_v1:${enterpriseId}:${file.name}:${file.size}:${file.lastModified}`
}

export async function s3MultipartInit(body) {
  const base = getBaseUrl()
  let res
  try {
    res = await fetch(`${base}/upload/s3/multipart/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (err) {
    const hint =
      isNetworkError(err) && base.startsWith('/')
        ? ' 若刚改过 Vite 代理，请重启前端容器并强刷浏览器。'
        : ''
    throw new Error(`[步骤1/4 后端 init] 无法访问 ${base}。${err.message}${hint}`)
  }
  if (!res.ok) {
    throw new Error(`[步骤1/4 后端 init] ${await readFetchError(res, 'init failed')}`)
  }
  return res.json()
}

/** 经后端转发分片到 S3（同源 /api，不受桶 CORS 限制） */
export async function s3MultipartUploadPartProxy(sessionId, partNumber, body) {
  const base = getBaseUrl()
  const q = new URLSearchParams({ session_id: sessionId, part_number: String(partNumber) })
  return fetch(`${base}/upload/s3/multipart/part?${q}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream' },
    body,
  })
}

export async function s3MultipartPartUrl(sessionId, partNumber) {
  const base = getBaseUrl()
  let res
  try {
    const q = new URLSearchParams({ session_id: sessionId, part_number: String(partNumber) })
    res = await fetch(`${base}/upload/s3/multipart/part-url?${q}`)
  } catch (err) {
    throw new Error(`[步骤2/4 预签名] 无法访问后端。${err.message}`)
  }
  if (!res.ok) {
    throw new Error(await readFetchError(res, 'part-url failed'))
  }
  return res.json()
}

export async function s3MultipartListParts(sessionId) {
  const base = getBaseUrl()
  let res
  try {
    const q = new URLSearchParams({ session_id: sessionId })
    res = await fetch(`${base}/upload/s3/multipart/parts?${q}`)
  } catch (err) {
    throw new Error(`[ListParts] 无法访问后端。${err.message}`)
  }
  if (!res.ok) {
    throw new Error(await readFetchError(res, 'list parts failed'))
  }
  return res.json()
}

export async function s3MultipartComplete(sessionId, parts) {
  const base = getBaseUrl()
  let res
  try {
    res = await fetch(`${base}/upload/s3/multipart/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, parts }),
    })
  } catch (err) {
    throw new Error(`[步骤4/4 complete] 无法访问后端。${err.message}`)
  }
  if (!res.ok) {
    throw new Error(await readFetchError(res, 'complete failed'))
  }
  return res.json()
}

export async function s3MultipartAbort(sessionId) {
  const base = getBaseUrl()
  let res
  try {
    res = await fetch(`${base}/upload/s3/multipart/abort`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
  } catch (err) {
    throw new Error(`[abort] 无法访问后端。${err.message}`)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `abort failed: ${res.status}`)
  }
  return data
}

function forceS3Proxy() {
  return import.meta.env.VITE_S3_UPLOAD_VIA_PROXY === 'true'
}

/** S3 PUT 返回 ETag 在响应头；后端代理返回 JSON { ETag } */
async function readEtagFromPutResponse(putRes) {
  const ct = putRes.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    const j = await putRes.json()
    return j.ETag
  }
  return putRes.headers.get('ETag')
}

/**
 * Upload file in chunks via presigned URLs; resume using GET /parts + localStorage.
 */
export async function uploadFileMultipartResumable(file, enterpriseId, opts = {}) {
  const { onProgress } = opts
  const storageKey = multipartResumeStorageKey(enterpriseId, file)
  let saved = null
  try {
    saved = JSON.parse(localStorage.getItem(storageKey) || 'null')
  } catch {
    saved = null
  }

  let sessionId = saved?.session_id
  let partSize = saved?.part_size_bytes
  const fileSize = file.size

  if (sessionId) {
    try {
      if (saved?.file_size !== fileSize || saved?.filename !== file.name) {
        sessionId = null
      } else {
        await s3MultipartListParts(sessionId)
        partSize = saved.part_size_bytes
      }
    } catch {
      sessionId = null
    }
  }

  if (!sessionId) {
    const init = await s3MultipartInit({
      enterprise_id: enterpriseId,
      filename: file.name,
      file_size: fileSize,
      content_type: file.type || undefined,
      title: file.name,
    })
    sessionId = init.session_id
    partSize = init.part_size_bytes
    localStorage.setItem(
      storageKey,
      JSON.stringify({
        session_id: sessionId,
        part_size_bytes: partSize,
        file_size: fileSize,
        filename: file.name,
        enterprise_id: enterpriseId,
      }),
    )
  }

  const listed = await s3MultipartListParts(sessionId)
  const done = new Map()
  for (const p of listed.parts || []) {
    done.set(p.PartNumber, p.ETag)
  }

  const totalParts = Math.ceil(fileSize / partSize)

  for (let pn = 1; pn <= totalParts; pn += 1) {
    if (done.has(pn)) continue

    const { url } = await s3MultipartPartUrl(sessionId, pn)
    const start = (pn - 1) * partSize
    const end = Math.min(start + partSize, fileSize)
    const chunk = file.slice(start, end)
    // 必须用 ArrayBuffer：Blob 会带 Content-Type（如 PDF 的 application/pdf），
    // 预签名 PUT 未签该头时 S3 可能 403，浏览器侧常表现为 Failed to fetch。
    const body = await chunk.arrayBuffer()

    let putRes
    if (forceS3Proxy()) {
      putRes = await s3MultipartUploadPartProxy(sessionId, pn, body)
    } else {
      try {
        putRes = await fetch(url, {
          method: 'PUT',
          body,
        })
      } catch (err) {
        // 直连 S3 失败（多为桶 CORS / 网络）时改走后端代理，不经浏览器访问 S3
        try {
          putRes = await s3MultipartUploadPartProxy(sessionId, pn, body)
        } catch (err2) {
          const origin =
            typeof window !== 'undefined' && window.location?.origin
              ? ` 你当前页面 Origin 为「${window.location.origin}」，桶 CORS 的 AllowedOrigins 须与此完全一致。`
              : ''
          throw new Error(
            `[步骤3/4 上传分片 ${pn}/${totalParts}] 直连 S3 失败且经后端代理也失败。` +
              `直连错误: ${err.message}；代理错误: ${err2.message}。` +
              `可在 frontend/.env 设 VITE_S3_UPLOAD_VIA_PROXY=true 强制只走后端代理。${origin}`,
          )
        }
      }
      if (putRes && !putRes.ok && putRes.status === 403) {
        putRes = await s3MultipartUploadPartProxy(sessionId, pn, body)
      }
    }

    if (!putRes.ok) {
      const t = await putRes.text()
      throw new Error(`Part ${pn} upload failed: ${putRes.status} ${t}`)
    }

    const etag = await readEtagFromPutResponse(putRes)
    if (!etag) {
      throw new Error(
        `Part ${pn}: 响应无 ETag（直连 S3 时请确认桶 CORS 的 ExposeHeaders 包含 ETag）`,
      )
    }
    done.set(pn, etag.trim())

    if (onProgress) {
      onProgress({ uploadedParts: done.size, totalParts })
    }
  }

  const parts = Array.from(done.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([PartNumber, ETag]) => ({ PartNumber, ETag }))

  const result = await s3MultipartComplete(sessionId, parts)
  localStorage.removeItem(storageKey)
  return result
}
