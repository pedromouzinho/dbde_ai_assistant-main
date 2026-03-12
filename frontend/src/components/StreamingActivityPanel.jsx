import React from 'react';
import {
  ConversationIcon,
  RefreshIcon,
  SearchIcon,
  ThinkingIcon,
  WarningIcon,
} from './AppIcons.jsx';

const PHASE_CONFIG = {
  thinking: { icon: ThinkingIcon, badge: 'Em curso' },
  tools: { icon: SearchIcon, badge: 'Contexto' },
  writing: { icon: ConversationIcon, badge: 'Resposta' },
  done: { icon: RefreshIcon, badge: 'Concluido' },
  error: { icon: WarningIcon, badge: 'Erro' },
  idle: { icon: ThinkingIcon, badge: 'A preparar' },
};

function normalizeLabel(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

export default function StreamingActivityPanel({ trace, statusText }) {
  const rawEvents = Array.isArray(trace && trace.events) ? trace.events.slice(-5) : [];
  const phase = trace && trace.phase ? trace.phase : 'idle';
  const phaseLabel = statusText || (trace && trace.label) || 'A preparar resposta';
  const phaseConfig = PHASE_CONFIG[phase] || PHASE_CONFIG.idle;
  const PhaseIcon = phaseConfig.icon;
  const normalizedPhaseLabel = normalizeLabel(phaseLabel);

  const events = rawEvents.filter((event) => {
    if (!event) return false;
    if (phase === 'thinking' && event.kind === 'system') return false;

    const title = normalizeLabel(event.title);
    const detail = normalizeLabel(event.detail);
    if (title && title === normalizedPhaseLabel) return false;
    if (detail && detail === normalizedPhaseLabel) return false;
    return true;
  });

  if (!phaseLabel && events.length === 0) {
    return null;
  }

  return (
    <div className="stream-panel">
      <div className="stream-panel-header">
        <div className={`stream-phase-pill is-${phase}`}>
          <PhaseIcon size={14} />
          <span>{phaseConfig.badge}</span>
        </div>
        <div className="stream-panel-status">{phaseLabel}</div>
      </div>

      {events.length ? (
        <div className="stream-panel-list">
          {events.map((event) => (
            <div key={event.id} className="stream-event-row">
              <span className={`stream-event-dot is-${event.status}`} />
              <div className="stream-event-copy">
                <div className="stream-event-title">{event.title}</div>
                {event.detail ? <div className="stream-event-detail">{event.detail}</div> : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
