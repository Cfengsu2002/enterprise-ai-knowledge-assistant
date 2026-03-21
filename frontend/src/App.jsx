import { useState } from 'react'
import { fetchEnterprise, getApiBaseUrl, uploadFileMultipartResumable } from './api/client'
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
