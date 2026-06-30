const BASE = ''

async function getJSON(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export async function fetchFields() {
  return getJSON(`${BASE}/api/fields`)
}

export async function scanInput() {
  return getJSON(`${BASE}/api/scan`)
}

export async function fetchRecords(search = '') {
  const qs = search ? `?search=${encodeURIComponent(search)}` : ''
  return getJSON(`${BASE}/api/records${qs}`)
}

export async function fetchRecord(id) {
  return getJSON(`${BASE}/api/records/${encodeURIComponent(id)}`)
}

export async function updateRecord(id, summary) {
  const res = await fetch(`${BASE}/api/records/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ summary }),
  })
  if (!res.ok) throw new Error(`Update failed: ${res.status}`)
  return res.json()
}

export function processStream(files) {
  const params = files ? `?files=${encodeURIComponent(files.join(','))}` : ''
  return new EventSource(`${BASE}/api/process${params}`)
}

export async function exportZip(recordIds) {
  const res = await fetch(`${BASE}/api/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ record_ids: recordIds }),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/)
        || disposition.match(/filename="?(.+?)"?$/)
  const filename = match ? decodeURIComponent(match[1]) : 'export.zip'
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
