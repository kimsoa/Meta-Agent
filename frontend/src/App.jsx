import { useState, useEffect, useRef } from 'react'
import './App.css'

// ─── Small helpers ────────────────────────────────────────────────────────────

function Badge({ label, color = 'accent' }) {
  return <span className={`badge badge-${color}`}>{label}</span>
}

function Spinner() {
  return <span className="spinner" aria-label="loading" />
}

// ─── Builder screen ───────────────────────────────────────────────────────────

function BuilderView({ onAgentReady }) {
  const [jd, setJd] = useState(
    'We need an AI agent to handle customer service for our e-commerce platform.\n' +
    'It should answer questions, check order status via our database, send emails,\n' +
    'remember conversation history, and escalate to human agents when needed.\n' +
    'The agent must be reliable and secure since it deals with customer data.'
  )
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/models')
      .then(r => r.json())
      .then(data => {
        // Filter out embedding models
        const chat = (data.models || []).filter(
          m => !m.includes('embed') && !m.includes('bert')
        )
        setModels(chat)
        setSelectedModel(data.default || chat[0] || '')
      })
      .catch(() => setError('Could not reach API. Make sure the backend is running.'))
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
        body: JSON.stringify({ job_description: jd, model: selectedModel, scaffold: true }),
      })
      if (!resp.ok) throw new Error(await resp.text())
      const data = await resp.json()
      setResult(data)
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

        <textarea
          className="jd-textarea"
          value={jd}
          onChange={e => setJd(e.target.value)}
          placeholder="Describe the agent's role, responsibilities, tools it needs…"
          rows={12}
        />

        {models.length > 0 && (
          <div className="model-select-wrapper">
            <label>LLM Model</label>
            <select
              className="model-select"
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
            >
              {models.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        )}

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
            onClick={() => onAgentReady(result, selectedModel)}
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
              {msg.content || (streaming && i === messages.length - 1
                ? <span className="cursor-blink">▋</span>
                : ''
              )}
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
            {Object.entries(tools).map(([toolId, tool]) => (
              <div key={toolId} className="tool-card">
                <div className="tool-card-header">
                  <strong>{tool.name}</strong>
                  {tool.requires_auth && (
                    <span className="tag tag-tool" style={{ marginLeft: 'auto' }}>🔐 auth</span>
                  )}
                </div>
                <p className="tool-description">{tool.description}</p>
                <div className="tool-footer">
                  <code className="tool-id">{toolId}</code>
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
          <div key={agent.id} className="agent-card">
            <div className="agent-card-header">
              <strong>{agent.name || agent.id}</strong>
              <Badge label={agent.agent_type?.replace('_', ' ') || 'agent'} color="blue" />
            </div>
            <p className="tool-description">
              Domain: <strong>{(agent.domain || 'general').replace('_', ' ')}</strong>
            </p>
            <div className="tool-footer">
              <code className="tool-id">{agent.id}</code>
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

  function handleAgentReady(data, selectedModel) {
    setAgentData(data)
    setModel(selectedModel || 'gemma3:latest')
    setView('chat')
  }

  function handleChatWithAgent(agent) {
    // Build a minimal agentData from a scaffolded agent record
    setAgentData({
      agent_name: agent.name || agent.id,
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
