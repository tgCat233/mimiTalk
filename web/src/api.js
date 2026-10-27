async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`HTTP ${res.status}: ${detail}`)
  }
  return res.status === 204 ? null : res.json()
}

export const api = {
  health: () => request('/api/health'),
  texts: () => request('/api/texts'),
  modelStatus: () => request('/api/model'),
  conversations: () => request('/api/conversations'),
  characters: () => request('/api/characters'),
  setFavorite: (characterId, favorite) =>
    request(`/api/characters/${characterId}/favorite`, {
      method: 'PUT',
      body: JSON.stringify({ favorite }),
    }),
  personas: () => request('/api/personas'),
  settings: () => request('/api/settings'),
  saveSettings: (payload) =>
    request('/api/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  persona: (id) => request(`/api/characters/${id}/persona`),
  savePersona: (id, systemPrompt) =>
    request(`/api/characters/${id}/persona`, {
      method: 'PUT',
      body: JSON.stringify({ system_prompt: systemPrompt }),
    }),
  createConversation: (characterId) =>
    request('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({ character_id: characterId }),
    }),
  deleteConversation: (id) =>
    request(`/api/conversations/${id}`, { method: 'DELETE' }),
  deleteMessage: (conversationId, messageId) =>
    request(`/api/conversations/${conversationId}/messages/${messageId}`, {
      method: 'DELETE',
    }),
  recallMessage: (conversationId, messageId) =>
    request(`/api/conversations/${conversationId}/messages/${messageId}/recall`, {
      method: 'POST',
    }),
  messages: (id, limit = 50) =>
    request(`/api/conversations/${id}/messages?limit=${limit}`),
  sendMessage: (id, payload) =>
    request(`/api/conversations/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  async uploadImage(file) {
    const maxBytes = 32 * 1024 * 1024
    if (file.size > maxBytes) {
      throw new Error('图片超过 32 MB，请压缩后再发送')
    }
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/uploads', { method: 'POST', body: form })
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
    return res.json()
  },
  async appearance() {
    const [bubbles, admins] = await Promise.all([
      fetch('/static/assets/bubbles/bubbles.json').then((r) => r.json()),
      fetch('/static/assets/avatars/admins.json').then((r) => r.json()),
    ])
    return {
      bubbles: bubbles.themes || [],
      bubbleDefault: bubbles.default || '9000',
      admins: admins.avatars || [],
    }
  },
  deleteUpload: (fileId) =>
    request(`/api/uploads/${fileId}`, { method: 'DELETE' }),
  saveConversationSettings: (id, payload) =>
    request(`/api/conversations/${id}/settings`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  ttsStatus: () => request('/api/tts/status'),
  ttsModels: () => request('/api/tts/models'),
  ttsSynthesize: (payload) =>
    request('/api/tts/synthesize', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  setCharacterVoice: (characterId, model) =>
    request('/api/tts/characters', {
      method: 'PUT',
      body: JSON.stringify({ character_id: characterId, model }),
    }),
  async ttsPreview(characterId, text, model) {
    const res = await fetch('/api/tts/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        character_id: characterId || null,
        text,
        model: model || null,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
    return res.blob()
  },
  async avatars() {
    const res = await fetch('/static/assets/avatars/avatars.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },
  async stickers() {
    const res = await fetch('/static/stickers/stickers.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },
  async streamReply(id, { signal, onEvent, recallNotice = false }) {
    const suffix = recallNotice ? '?recall_notice=1' : ''
    const res = await fetch(`/api/conversations/${id}/chat/stream${suffix}`, {
      method: 'POST',
      signal,
    })
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let index = buffer.indexOf('\n\n')
      while (index >= 0) {
        const chunk = buffer.slice(0, index)
        buffer = buffer.slice(index + 2)
        let event = 'message'
        let data = ''
        for (const line of chunk.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (data) onEvent(event, JSON.parse(data))
        index = buffer.indexOf('\n\n')
      }
    }
  },
}
