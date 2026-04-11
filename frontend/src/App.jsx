import { useState, useEffect, useRef } from 'react'
import './App.css'

// ─── Small helpers ────────────────────────────────────────────────────────────

function Badge({ label, color = 'accent' }) {
  return <span className={`badge badge-${color}`}>{label}</span>
}

function Spinner() {
  return <span className="spinner" aria-label="loading" />
}

function toTitle(str) {
  return str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function parseInline(text) {
  const tokens = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/)
  return tokens.map((token, i) => {
    if (/^\*\*(.+)\*\*$/.test(token)) return <strong key={i}>{token.slice(2, -2)}</strong>
    if (/^\*(.+)\*$/.test(token)) return <em key={i}>{token.slice(1, -1)}</em>
    if (/^`(.+)`$/.test(token)) return <code key={i} style={{ background: 'rgba(255,255,255,0.1)', padding: '0 3px', borderRadius: 3 }}>{token.slice(1, -1)}</code>
    return token
  })
}

function renderMarkdown(text) {
  if (!text) return null
  return text.split('\n').map((line, idx) => {
    const listMatch = /^[*\-]\s+(.+)$/.exec(line)
    if (listMatch) {
      return <li key={idx} style={{ marginLeft: '1.2rem', listStyle: 'disc' }}>{parseInline(listMatch[1])}</li>
    }
    if (line === '') return <br key={idx} />
    return <p key={idx} style={{ margin: '0.2em 0' }}>{parseInline(line)}</p>
  })
}

// ─── Model Picker ─────────────────────────────────────────────────────────────

const PROVIDER_COLORS = {
  ollama_local:         '#22c55e',
  docker_model_runner:  '#3b82f6',
  openai:               '#10b981',
  anthropic:            '#f59e0b',
  groq:                 '#ef4444',
  mistral:              '#8b5cf6',
  google:               '#0ea5e9',
  together:             '#f97316',
  cohere:               '#ec4899',
}

const TIER_COLORS = { 1: '#6b7280', 2: '#22c55e', 3: '#3b82f6', 4: '#f59e0b', 5: '#ef4444' }

function ProviderDot({ providerId }) {
  return (
    <span
      className="mp-provider-dot"
      style={{ background: PROVIDER_COLORS[providerId] || '#6b7280' }}
    />
  )
}

/**
 * ModelPicker — self-contained provider-aware model selector.
 * Props:
 *   value      {provider_id, model_id} | null
 *   onChange   ({provider_id, model_id}) => void
 *   suggestion {model_id, provider, ...} | null  — highlights the suggested model
 *   localOnly  bool — only show local providers (ollama, docker model runner)
 *   label      string
 */
function ModelPicker({ value, onChange, suggestion, localOnly = false, label }) {
  const [open, setOpen] = useState(false)
  const [providers, setProviders] = useState([])
  const [activeProvider, setActiveProvider] = useState(value?.provider_id || 'ollama_local')
  const [modelData, setModelData] = useState({}) // provider_id → {models, loading, error}
  const [search, setSearch] = useState('')
  const dropRef = useRef(null)

  // Fetch providers list on mount
  useEffect(() => {
    fetch('/api/providers')
      .then(r => r.json())
      .then(d => {
        const list = localOnly
          ? (d.providers || []).filter(p => p.type === 'local')
          : (d.providers || [])
        setProviders(list)
        const current = value?.provider_id
        if (current && list.some(p => p.id === current)) {
          setActiveProvider(current)
        } else if (list.length > 0) {
          setActiveProvider(list[0].id)
        }
      })
      .catch(() => {})
  }, [localOnly]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch models for the active provider tab
  useEffect(() => {
    if (!activeProvider || modelData[activeProvider]) return
    setModelData(prev => ({ ...prev, [activeProvider]: { models: [], loading: true, error: null } }))
    fetch(`/api/providers/${activeProvider}/models`)
      .then(r => r.json())
      .then(d => {
        setModelData(prev => ({
          ...prev,
          [activeProvider]: { models: d.models || [], loading: false, error: d.error || null, fetchedLive: d.fetched_live },
        }))
      })
      .catch(e => {
        setModelData(prev => ({
          ...prev,
          [activeProvider]: { models: [], loading: false, error: e.message },
        }))
      })
  }, [activeProvider]) // eslint-disable-line react-hooks/exhaustive-deps

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handler(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const provData = modelData[activeProvider] || { models: [], loading: false }
  const filtered = (provData.models || []).filter(
    m => !search || m.id.toLowerCase().includes(search.toLowerCase())
  )
  const activeProv = providers.find(p => p.id === activeProvider)

  function selectModel(m) {
    onChange({ provider_id: activeProvider, model_id: m.id })
    setOpen(false)
    setSearch('')
  }

  function isSuggested(m) {
    if (!suggestion) return false
    const sugId = suggestion.model_id || ''
    return m.id === sugId || m.id === sugId.split(':')[0]
  }

  return (
    <div className="model-picker" ref={dropRef}>
      {label && <div className="mp-label">{label}</div>}
      <button
        className="mp-trigger"
        onClick={() => setOpen(v => !v)}
        type="button"
      >
        <span className="mp-value">
          {value?.model_id ? (
            <>
              <ProviderDot providerId={value.provider_id} />
              <span className="mp-model-text">{value.model_id}</span>
            </>
          ) : (
            <span className="mp-placeholder">Select a model…</span>
          )}
        </span>
        <span className="mp-chevron">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="mp-dropdown">
          {/* Provider tabs */}
          <div className="mp-providers">
            {providers.map(p => (
              <button
                key={p.id}
                className={`mp-provider-btn ${activeProvider === p.id ? 'active' : ''}`}
                onClick={() => { setActiveProvider(p.id); setSearch('') }}
                type="button"
              >
                <span className={`mp-status ${p.configured ? 'ok' : 'off'}`} />
                {p.label}
              </button>
            ))}
          </div>

          {activeProv && !activeProv.configured && (
            <div className="mp-unconfigured">
              {activeProv.type === 'local'
                ? `${activeProv.label} is not running. Start it to see live models.`
                : `Set ${activeProv.key_env_var} to enable ${activeProv.label}. Showing catalogue below.`}
            </div>
          )}

          {/* Search */}
          <input
            className="mp-search"
            placeholder="Filter models…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
          />

          {/* Model list */}
          <div className="mp-list">
            {provData.loading && <div className="mp-loading">Loading…</div>}
            {!provData.loading && filtered.length === 0 && (
              <div className="mp-empty">No models found</div>
            )}
            {filtered.map(m => {
              const suggested = isSuggested(m)
              const selected = value?.model_id === m.id && value?.provider_id === activeProvider
              return (
                <div
                  key={m.id}
                  className={`mp-model-item${selected ? ' selected' : ''}${suggested ? ' suggested' : ''}`}
                  onClick={() => selectModel(m)}
                >
                  <div className="mp-model-row">
                    <span className="mp-model-id">{m.id}</span>
                    <span className="mp-model-chips">
                      {m.tier != null && (
                        <span className="tier-chip-s" style={{ background: TIER_COLORS[m.tier] }}>
                          T{m.tier}
                        </span>
                      )}
                      {suggested && <span className="suggested-chip">⭐</span>}
                      {m.source === 'catalog' && <span className="catalog-chip-s">catalogue</span>}
                    </span>
                  </div>
                  {m.description && (
                    <div className="mp-model-desc">{m.description}</div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Builder screen ───────────────────────────────────────────────────────────

function BuilderView({ onAgentReady }) {
  const [jd, setJd] = useState(
    'We need an AI agent to handle customer service for our e-commerce platform.\n' +
    'It should answer questions, check order status via our database, send emails,\n' +
    'remember conversation history, and escalate to human agents when needed.\n' +
    'The agent must be reliable and secure since it deals with customer data.'
  )
  const [builderModel, setBuilderModel] = useState({ provider_id: 'ollama_local', model_id: '' })
  const [agentModel, setAgentModel] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [builderInfo, setBuilderInfo] = useState(null)

  useEffect(() => {
    // Fetch builder identity (who is the meta-agent?) and seed the builder model
    fetch('/api/models/discover')
      .then(r => r.json())
      .then(data => {
        setBuilderInfo(data.builder)
        if (data.builder?.model_id) {
          setBuilderModel({ provider_id: 'ollama_local', model_id: data.builder.model_id })
        }
      })
      .catch(() => {})
  }, [])

  async function handleBuild() {
    if (jd.trim().length < 20) {
      setError('Please enter a more detailed job description.')
      return
    }
    setError('')
    setLoading(true)
    setResult(null)
    try {
      const resp = await fetch('/api/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_description: jd, model: builderModel.model_id || 'gemma3:latest', scaffold: true }),
      })
      if (!resp.ok) throw new Error(await resp.text())
      const data = await resp.json()
      setResult(data)
      if (data.recommended_model) {
        setAgentModel({
          provider_id: data.recommended_model.provider || 'ollama_local',
          model_id: data.recommended_model.model_id,
        })
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const typeColors = {
    simple_reflex: 'green',
    model_based: 'blue',
    goal_based: 'purple',
    utility_based: 'orange',
    conversational: 'cyan',
    automated: 'gray',
  }

  return (
    <div className="builder-layout">
      {/* Left panel — input */}
      <div className="panel panel-left">
        <div className="panel-header">
          <h2>Job Description</h2>
          <p className="panel-sub">Describe what the agent should do</p>
        </div>

        {builderInfo && (
          <div className="builder-identity">
            <span className="builder-label">Meta-Agent Builder</span>
            <code className="builder-model">{builderInfo.model_id}</code>
            <span className="badge badge-green">Local Ollama</span>
            <span className="builder-tier">Tier {builderInfo.tier}/5</span>
          </div>
        )}

        <textarea
          className="jd-textarea"
          value={jd}
          onChange={e => setJd(e.target.value)}
          placeholder="Describe the agent's role, responsibilities, tools it needs…"
          rows={12}
        />

        <ModelPicker
          label="Builder Analysis Model"
          value={builderModel}
          onChange={setBuilderModel}
          localOnly={true}
        />

        {error && <div className="error-box">{error}</div>}

        <button
          className="btn btn-primary btn-full"
          onClick={handleBuild}
          disabled={loading}
        >
          {loading ? <><Spinner /> Analyzing…</> : '🔬 Analyze & Build Agent'}
        </button>

        {result && (
          <button
            className="btn btn-accent btn-full"
            onClick={() => onAgentReady(result, agentModel || builderModel)}
          >
            💬 Launch Agent Chat →
          </button>
        )}
      </div>

      {/* Right panel — results */}
      <div className="panel panel-right">
        {!result && !loading && (
          <div className="empty-state">
            <div className="empty-icon">🤖</div>
            <h3>Meta-Agent Builder</h3>
            <p>Enter a job description and click <strong>Analyze &amp; Build Agent</strong> to generate a specialized AI agent with a full system prompt.</p>
          </div>
        )}

        {loading && (
          <div className="empty-state">
            <Spinner />
            <p style={{ marginTop: '1rem' }}>Analyzing job description…</p>
          </div>
        )}

        {result && (
          <div className="results">
            {/* Model recommendation card */}
            {result.recommended_model && (
              <div className="result-card result-model-rec">
                <h4>Recommended Model for this Agent</h4>
                <div className="model-rec-header">
                  <code className="model-rec-id">{result.recommended_model.model_id}</code>
                  <span className={`badge badge-${result.recommended_model.is_local ? 'green' : 'blue'}`}>
                    {result.recommended_model.provider_label}
                  </span>
                  <span className="tier-pill">
                    Tier {result.recommended_model.tier}/5
                    {result.recommended_model.required_tier && result.recommended_model.tier !== result.recommended_model.required_tier
                      ? ` → need ${result.recommended_model.required_tier}` : ''}
                  </span>
                </div>
                <p className="model-rec-reason">{result.recommended_model.reason}</p>
                {result.recommended_model.warning && (
                  <p className="model-rec-warning">⚠️ {result.recommended_model.warning}</p>
                )}
                {result.recommended_model.alternatives?.length > 0 && (
                  <div className="model-alts">
                    <span className="alts-label">Alternatives:</span>
                    {result.recommended_model.alternatives.map((alt, i) => (
                      <span key={i} className="alt-chip" title={alt.reason}>
                        {alt.model_id}
                        <small> ({alt.provider_label || alt.provider})</small>
                      </span>
                    ))}
                  </div>
                )}                <div className="agent-model-picker-wrapper">
                  <p className="agent-model-picker-label">Override agent runtime model:</p>
                  <ModelPicker
                    value={agentModel}
                    onChange={setAgentModel}
                    suggestion={result.recommended_model}
                  />
                </div>              </div>
            )}

            {/* Hero card */}
            <div className="result-card result-hero">
              <div className="hero-type">
                <Badge
                  label={result.agent_type.replace('_', ' ').toUpperCase()}
                  color={typeColors[result.agent_type] || 'accent'}
                />
                <span className="complexity-pill">
                  Complexity {result.complexity_level}/5
                </span>
                <span className={`source-pill source-${result.analysis_source}`}>
                  {result.analysis_source === 'llm' ? '🧠 NLP' : '🔤 Keyword'}
                </span>
              </div>
              <div className="hero-name">{result.agent_name}</div>
              <p className="rationale">{result.rationale}</p>
              {result.scaffold_path && (
                <p className="scaffold-note">📁 Scaffolded: <code>{result.scaffold_path}</code></p>
              )}
            </div>

            {/* Analysis grid */}
            <div className="result-grid">
              <div className="result-card">
                <h4>Analysis</h4>
                <table className="prop-table">
                  <tbody>
                    <tr><td>Domain</td><td>{result.domain.replace('_', ' ')}</td></tr>
                    <tr><td>Sub-domain</td><td>{result.sub_domain.replace('_', ' ')}</td></tr>
                    <tr><td>Interaction</td><td>{result.interaction_type}</td></tr>
                    <tr><td>Problem type</td><td>{result.problem_type}</td></tr>
                    <tr><td>Autonomy</td><td>{result.autonomy_level}</td></tr>
                  </tbody>
                </table>
              </div>

              <div className="result-card">
                <h4>Capabilities</h4>
                <div className="tag-list">
                  {result.required_capabilities.map(c => (
                    <span key={c} className="tag">{c}</span>
                  ))}
                  {result.required_capabilities.length === 0 && (
                    <span className="text-muted">None detected</span>
                  )}
                </div>
              </div>

              <div className="result-card">
                <h4>Tools</h4>
                <div className="tag-list">
                  {result.recommended_tools.slice(0, 10).map(t => (
                    <span key={t} className="tag tag-tool">{t.replace(/_/g, ' ')}</span>
                  ))}
                  {result.recommended_tools.length > 10 && (
                    <span className="tag tag-more">+{result.recommended_tools.length - 10} more</span>
                  )}
                </div>
              </div>

              {result.custom_tools_needed && result.custom_tools_needed.length > 0 && (
                <div className="result-card">
                  <h4>Custom Tools Needed</h4>
                  <ul className="safety-list">
                    {result.custom_tools_needed.map((t, i) => (
                      <li key={i}><strong>{t.name}</strong> — {t.description}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* System prompt */}
            <div className="result-card result-prompt">
              <h4>Generated System Prompt</h4>
              <pre className="prompt-pre">{result.system_prompt}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Chat screen ──────────────────────────────────────────────────────────────

function ChatView({ agentData, model, onBack }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [systemVisible, setSystemVisible] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage() {
    const text = input.trim()
    if (!text || streaming) return

    const userMsg = { role: 'user', content: text }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setStreaming(true)

    // Add empty assistant message that we'll fill in
    const assistantIdx = nextMessages.length
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_prompt: agentData.system_prompt,
          messages: nextMessages,
          model,
        }),
      })

      if (!resp.ok) {
        throw new Error(await resp.text())
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accumulated = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const chunk = JSON.parse(line.slice(6))
            if (chunk.error) throw new Error(chunk.error)
            accumulated += chunk.token
            setMessages(prev => {
              const updated = [...prev]
              updated[assistantIdx] = { role: 'assistant', content: accumulated }
              return updated
            })
            if (chunk.done) break
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (e) {
      setMessages(prev => {
        const updated = [...prev]
        updated[assistantIdx] = { role: 'assistant', content: `Error: ${e.message}` }
        return updated
      })
    } finally {
      setStreaming(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const agentName = agentData.agent_name ||
    (agentData.agent_type || 'agent')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase()) + ' Agent'

  return (
    <div className="chat-layout">
      {/* Chat header */}
      <div className="chat-header">
        <button className="btn-ghost" onClick={onBack}>← Back</button>
        <div className="chat-title">
          <span className="chat-agent-name">{agentName}</span>
          <span className="chat-model-badge">{model}</span>
        </div>
        <button
          className="btn-ghost"
          onClick={() => setSystemVisible(v => !v)}
        >
          {systemVisible ? 'Hide' : 'Show'} System Prompt
        </button>
      </div>

      {/* System prompt drawer */}
      {systemVisible && (
        <div className="system-drawer">
          <pre>{agentData.system_prompt}</pre>
        </div>
      )}

      {/* Messages */}
      <div className="messages-area">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">💬</div>
            <h3>Agent Ready</h3>
            <p>You are now talking to your <strong>{agentName}</strong>.<br />
            The system prompt has been set. Ask it anything.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message message-${msg.role}`}>
            <div className="message-label">
              {msg.role === 'user' ? 'You' : agentName}
            </div>
            <div className="message-content">
              {msg.content
                ? renderMarkdown(msg.content)
                : (streaming && i === messages.length - 1
                    ? <span className="cursor-blink">▋</span>
                    : ''
                  )
              }
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="input-bar">
        <textarea
          ref={inputRef}
          className="chat-input"
          rows={2}
          placeholder={streaming ? 'Agent is thinking…' : 'Type a message… (Enter to send, Shift+Enter for new line)'}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
        />
        <button
          className="btn btn-primary send-btn"
          onClick={sendMessage}
          disabled={streaming || !input.trim()}
        >
          {streaming ? <Spinner /> : 'Send'}
        </button>
      </div>
    </div>
  )
}

// ─── Tools screen ─────────────────────────────────────────────────────────────

function ToolsView() {
  const [groups, setGroups] = useState(null)
  const [error, setError] = useState('')
  const [connected, setConnected] = useState({})

  useEffect(() => {
    fetch('/api/tools')
      .then(r => r.json())
      .then(setGroups)
      .catch(() => setError('Could not load tools.'))
  }, [])

  const ecosystemColors = {
    google: 'blue',
    microsoft: 'purple',
    standalone: 'green',
    generated: 'orange',
  }

  function toggleConnect(ecosystem) {
    setConnected(prev => ({ ...prev, [ecosystem]: !prev[ecosystem] }))
  }

  if (error) return <div className="error-box">{error}</div>
  if (!groups) return <div className="empty-state"><Spinner /></div>

  return (
    <div className="tools-layout">
      <div className="panel-header" style={{ padding: '1.5rem 2rem 0' }}>
        <h2>Tool Marketplace</h2>
        <p className="panel-sub">Connect ecosystems and discover available tools</p>
      </div>
      {Object.entries(groups).map(([ecosystem, tools]) => (
        <div key={ecosystem} className="ecosystem-section">
          <div className="ecosystem-header">
            <h3 className="ecosystem-title">
              <Badge label={ecosystem.toUpperCase()} color={ecosystemColors[ecosystem] || 'accent'} />
              &nbsp; {ecosystem.charAt(0).toUpperCase() + ecosystem.slice(1)} Tools
            </h3>
            {ecosystem !== 'standalone' && ecosystem !== 'generated' && (
              <button
                className={`btn ${connected[ecosystem] ? 'btn-success' : 'btn-outline'}`}
                onClick={() => toggleConnect(ecosystem)}
              >
                {connected[ecosystem] ? '✓ Connected' : `Connect ${ecosystem.charAt(0).toUpperCase() + ecosystem.slice(1)}`}
              </button>
            )}
          </div>
          <div className="tools-grid">
            {(Array.isArray(tools) ? tools : Object.values(tools)).map(tool => (
              <div key={tool.id} className="tool-card">
                <div className="tool-card-header">
                  <strong>{tool.name}</strong>
                  {tool.requires_auth && (
                    <span className="tag tag-tool" style={{ marginLeft: 'auto' }}>🔐 auth</span>
                  )}
                </div>
                <p className="tool-description">{tool.description}</p>
                <div className="tool-footer">
                  <code className="tool-id">{tool.id}</code>
                  {tool.requires_auth && connected[ecosystem] && (
                    <span className="connected-badge">✓ ready</span>
                  )}
                  {!tool.requires_auth && (
                    <span className="connected-badge">✓ ready</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Agents screen ────────────────────────────────────────────────────────────

function AgentsView({ onChatWithAgent }) {
  const [agents, setAgents] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/agents')
      .then(r => r.json())
      .then(data => setAgents(data.agents || []))
      .catch(() => setError('Could not load agents.'))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!agents) return <div className="empty-state"><Spinner /></div>

  if (agents.length === 0) return (
    <div className="empty-state">
      <div className="empty-icon">🤖</div>
      <h3>No Agents Yet</h3>
      <p>Build your first agent in the <strong>Builder</strong> tab.</p>
    </div>
  )

  return (
    <div className="agents-layout">
      <div className="panel-header" style={{ padding: '1.5rem 2rem 0' }}>
        <h2>Agent Library</h2>
        <p className="panel-sub">{agents.length} scaffolded agent{agents.length !== 1 ? 's' : ''}</p>
      </div>
      <div className="agents-grid">
        {agents.map(agent => (
          <div key={agent.agent_id} className="agent-card">
            <div className="agent-card-header">
              <strong>{agent.agent_name || toTitle(agent.agent_id || '')}</strong>
              <Badge label={agent.agent_type?.replace('_', ' ') || 'agent'} color="blue" />
            </div>
            <p className="tool-description">
              Domain: <strong>{toTitle(agent.domain || 'general')}</strong>
            </p>
            <div className="tool-footer">
              <code className="tool-id">{agent.agent_id}</code>
              <button
                className="btn btn-primary"
                style={{ padding: '4px 12px', fontSize: '0.8rem' }}
                onClick={() => onChatWithAgent(agent)}
              >
                💬 Chat
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── App root ─────────────────────────────────────────────────────────────────

export default function App() {
  const [view, setView] = useState('builder')
  const [agentData, setAgentData] = useState(null)
  const [model, setModel] = useState('')

  function handleAgentReady(data, modelChoice) {
    setAgentData(data)
    const modelId = typeof modelChoice === 'string'
      ? modelChoice
      : (modelChoice?.model_id || 'gemma3:latest')
    setModel(modelId)
    setView('chat')
  }

  function handleChatWithAgent(agent) {
    // Build a minimal agentData from a scaffolded agent record
    setAgentData({
      agent_name: agent.agent_name || toTitle(agent.agent_id || ''),
      agent_type: agent.agent_type || 'conversational',
      system_prompt: agent.system_prompt || '',
    })
    setModel('gemma3:latest')
    setView('chat')
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-logo">🤖 Meta-Agent Builder</div>
        <nav className="header-nav">
          <button
            className={`nav-btn ${view === 'builder' ? 'active' : ''}`}
            onClick={() => setView('builder')}
          >
            Builder
          </button>
          <button
            className={`nav-btn ${view === 'tools' ? 'active' : ''}`}
            onClick={() => setView('tools')}
          >
            Tools
          </button>
          <button
            className={`nav-btn ${view === 'agents' ? 'active' : ''}`}
            onClick={() => setView('agents')}
          >
            Agents
          </button>
          <button
            className={`nav-btn ${view === 'chat' ? 'active' : ''}`}
            onClick={() => setView('chat')}
            disabled={!agentData}
          >
            Chat {agentData ? `(${(agentData.agent_type || 'agent').replace('_', ' ')})` : ''}
          </button>
        </nav>
      </header>

      <main className="app-main">
        {view === 'builder' && (
          <BuilderView onAgentReady={handleAgentReady} />
        )}
        {view === 'tools' && (
          <ToolsView />
        )}
        {view === 'agents' && (
          <AgentsView onChatWithAgent={handleChatWithAgent} />
        )}
        {view === 'chat' && agentData && (
          <ChatView
            agentData={agentData}
            model={model}
            onBack={() => setView('builder')}
          />
        )}
      </main>
    </div>
  )
}
