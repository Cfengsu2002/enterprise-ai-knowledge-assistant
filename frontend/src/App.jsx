import { useState } from 'react'
import {
  fetchEnterprise,
  getApiBaseUrl,
  ragSemanticSearch,
  uploadFileMultipartResumable,
} from './api/client'
import './App.css'

function App() {
  const [enterpriseId, setEnterpriseId] = useState('1')
  const [enterprise, setEnterprise] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)

  const [searchQuery, setSearchQuery] = useState('')
  const [searchLimit, setSearchLimit] = useState('8')
  const [searching, setSearching] = useState(false)
  const [searchResults, setSearchResults] = useState(null)
  const [searchError, setSearchError] = useState(null)

  const handleFetch = async () => {
    setError(null)
    setEnterprise(null)
    setLoading(true)
    try {
      const id = Number(enterpriseId)
      if (Number.isNaN(id) || id < 1) {
        setError('Please enter a valid ID (positive number)')
        return
      }
      const data = await fetchEnterprise(id)
      setEnterprise(data ?? null)
    } catch (e) {
      setError(e.message || 'Failed to fetch enterprise')
    } finally {
      setLoading(false)
    }
  }

  const handleMultipartUpload = async () => {
    setUploadResult(null)
    setError(null)
    if (!uploadFile) {
      setError('Choose a file first')
      return
    }
    const id = Number(enterpriseId)
    if (Number.isNaN(id) || id < 1) {
      setError('Enterprise ID must be a positive number')
      return
    }
    setUploading(true)
    setUploadProgress(null)
    try {
      const result = await uploadFileMultipartResumable(uploadFile, id, {
        onProgress: ({ uploadedParts, totalParts }) => {
          setUploadProgress({ uploadedParts, totalParts })
        },
      })
      setUploadResult(result)
      setUploadProgress(null)
    } catch (e) {
      setError(e.message || 'Multipart upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleSemanticSearch = async () => {
    setSearchError(null)
    setSearchResults(null)
    const id = Number(enterpriseId)
    if (Number.isNaN(id) || id < 1) {
      setSearchError('Enterprise ID must be a positive number')
      return
    }
    const q = (searchQuery || '').trim()
    if (!q) {
      setSearchError('Enter a search query')
      return
    }
    let limit = Number(searchLimit)
    if (Number.isNaN(limit) || limit < 1) limit = 8
    if (limit > 50) limit = 50
    setSearching(true)
    try {
      const data = await ragSemanticSearch({ enterpriseId: id, query: q, limit })
      setSearchResults(Array.isArray(data.results) ? data.results : [])
    } catch (e) {
      setSearchError(e.message || 'Search failed')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="app">
      <h1>Enterprise AI Knowledge Assistant</h1>
      <div className="card">
        <label htmlFor="enterprise-id">Enterprise ID</label>
        <input
          id="enterprise-id"
          type="number"
          min="1"
          value={enterpriseId}
          onChange={(e) => setEnterpriseId(e.target.value)}
        />
        <button onClick={handleFetch} disabled={loading}>
          {loading ? 'Loading…' : 'Fetch enterprise'}
        </button>
      </div>

      <div className="card">
        <h2>语义搜索（RAG）</h2>
        <p className="hint">
          使用上方 <strong>Enterprise ID</strong>，对已写入向量库的文档做相似度检索（<code>POST /rag/search</code>
          ）。
        </p>
        <label htmlFor="search-query">查询语句</label>
        <textarea
          id="search-query"
          className="textarea"
          rows={3}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="例如：housing prices Gainesville"
          disabled={searching}
        />
        <label htmlFor="search-limit">返回条数（1–50）</label>
        <input
          id="search-limit"
          type="number"
          min="1"
          max="50"
          value={searchLimit}
          onChange={(e) => setSearchLimit(e.target.value)}
          disabled={searching}
        />
        <button type="button" onClick={handleSemanticSearch} disabled={searching}>
          {searching ? '搜索中…' : '搜索'}
        </button>
        {searchError && <p className="error">{searchError}</p>}
        {searchResults && (
          <div className="search-results">
            <h3>结果 {searchResults.length} 条</h3>
            {searchResults.length === 0 ? (
              <p className="hint">无匹配片段。请确认该 enterprise 已上传并索引文档。</p>
            ) : (
              <ul className="search-hit-list">
                {searchResults.map((hit) => (
                  <li key={hit.id} className="search-hit">
                    <div className="search-hit-meta">
                      <span className="search-score">score {(hit.score ?? 0).toFixed(4)}</span>
                      <span className="search-doc">
                        {hit.document_title || `document #${hit.document_id}`}
                      </span>
                      <span className="search-chunk">
                        chunk #{hit.chunk_index} · id {hit.id} · document {hit.document_id}
                      </span>
                      {hit.embedding_model && (
                        <span className="search-model" title={hit.embedding_model}>
                          {hit.embedding_model.split('/').pop()}
                        </span>
                      )}
                    </div>
                    <pre className="search-hit-content">{hit.content}</pre>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h2>S3 分片上传（断点续传）</h2>
        <p className="hint">
          需配置后端 <code>S3_BUCKET</code> 与 AWS 凭证。直连 S3 时<strong>桶 CORS</strong>须允许{' '}
          <code>PUT</code> 与 <code>ExposeHeaders: ETag</code>；若仍 Failed to fetch，会自动经同源{' '}
          <code>/api</code> 由后端上传分片（无需改桶 CORS）。当前 API 基址：<code>{getApiBaseUrl()}</code>。
          <br />
          <strong>当前页面 Origin（须出现在桶 CORS 的 AllowedOrigins 中）：</strong>{' '}
          <code>{typeof window !== 'undefined' ? window.location.origin : ''}</code>
          <br />
          中断后重新选择同一文件可续传（localStorage + ListParts）。
        </p>
        <input
          type="file"
          onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
          disabled={uploading}
        />
        <button type="button" onClick={handleMultipartUpload} disabled={uploading}>
          {uploading ? '上传中…' : '上传 / 续传'}
        </button>
        {uploadProgress && (
          <p>
            进度：已就绪分片 {uploadProgress.uploadedParts} / {uploadProgress.totalParts}
          </p>
        )}
        {uploadResult && (
          <div className="result">
            <h3>完成</h3>
            <pre>{JSON.stringify(uploadResult, null, 2)}</pre>
          </div>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {enterprise !== null && enterprise !== undefined && (
        <div className="result">
          <h2>Enterprise</h2>
          {enterprise ? (
            <pre>{JSON.stringify(enterprise, null, 2)}</pre>
          ) : (
            <p>No enterprise found for this ID.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default App
