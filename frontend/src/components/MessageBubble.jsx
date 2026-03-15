import React from 'react';
import { renderMarkdown } from '../utils/markdown.js';
import { MILLENNIUM_LOGO_DARK_TILE_URI } from '../utils/constants.js';
import { getFileDownloads, getChartSpecs, messageHasExportableData } from '../utils/messageHelpers.js';
import ToolBadges from './ToolBadges.jsx';
import ToolExecutionSummary from './ToolExecutionSummary.jsx';
import ChartBlock from './ChartBlock.jsx';
import FeedbackWidget from './FeedbackWidget.jsx';
import QuickReplyBar from './QuickReplyBar.jsx';

export default function MessageBubble({
  message,
  isLastAssistant,
  conversationId,
  messageIndex,
  onFeedback,
  onExport,
  onExportBundle,
  onFileDownload,
  onQuickReply,
}) {
  const isUser = message.role === 'user';
  const content = typeof message.content === 'string' ? message.content : (message.text || '');
  const fileDownloads = getFileDownloads(message.tool_results);
  const tierLabels = { fast: 'Fast', standard: 'Thinking', pro: 'Pro' };
  const metaBits = [];
  if (message.model_tier) {
    metaBits.push(tierLabels[message.model_tier] || String(message.model_tier));
  }
  if (message.tokens_used && message.tokens_used.total_tokens) {
    metaBits.push(`${Number(message.tokens_used.total_tokens).toLocaleString('pt-PT')} tokens`);
  }
  if (message.total_time_ms) {
    metaBits.push(`${(message.total_time_ms / 1000).toFixed(1)}s`);
  }

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16, animation: 'fadeUp 0.3s ease' }}>
        <div>
          <div
            style={{
              background: '#1A1A1A',
              color: 'white',
              borderRadius: '18px 18px 4px 18px',
              padding: '14px 20px',
              maxWidth: 600,
              fontSize: 14,
              lineHeight: 1.6,
              wordBreak: 'break-word',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}
          >
            {content}
          </div>

          {message.images && message.images.length > 0 ? (
            <div style={{ display: 'flex', gap: 6, marginTop: 6, justifyContent: 'flex-end' }}>
              {message.images.map((img, i) => (
                <img
                  key={i}
                  src={img.url || img.dataUrl}
                  style={{ width: 60, height: 60, borderRadius: 10, objectFit: 'cover', border: '2px solid rgba(255,255,255,0.3)' }}
                />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16, animation: 'fadeUp 0.3s ease' }}>
      <img src={MILLENNIUM_LOGO_DARK_TILE_URI} alt="Millennium" style={{ width: 32, height: 32, borderRadius: 10, flexShrink: 0 }} />

      <div style={{ flex: 1, minWidth: 0, maxWidth: 900 }}>
        <ToolBadges tools={message.tools_used} details={message.tool_details} />
        <ToolExecutionSummary details={message.tool_details} />

        <div
          className="msg-content"
          style={{
            background: 'white',
            borderRadius: '4px 18px 18px 18px',
            padding: '16px 22px',
            boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
            fontSize: 14,
            lineHeight: 1.7,
            color: '#1a1a1a',
            wordBreak: 'break-word',
            border: '1px solid rgba(0,0,0,0.04)',
          }}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
        />

        {isLastAssistant && message.clarification_options && message.clarification_options.length > 0 ? (
          <QuickReplyBar
            options={message.clarification_options}
            onSelect={onQuickReply}
            disabled={!isLastAssistant}
          />
        ) : null}

        {getChartSpecs(message.tool_results).map((spec, ci) => (
          <ChartBlock key={`chart-${ci}`} chartSpec={spec} chartId={`chart-${messageIndex}-${ci}`} />
        ))}

        {fileDownloads.length > 0 ? (
          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
            {fileDownloads.map((fd, fi) => (
              <button
                key={`${fd.download_id || 'file'}-${fi}`}
                className="export-btn"
                onClick={() => onFileDownload(fd)}
                style={{
                  background: fd.primary ? '#1A1A1A' : 'rgba(0,0,0,0.03)',
                  border: fd.primary ? '1px solid #1A1A1A' : '1px solid rgba(0,0,0,0.08)',
                  borderRadius: 8,
                  padding: '5px 12px',
                  cursor: 'pointer',
                  fontSize: 11,
                  color: fd.primary ? '#fff' : '#666',
                  fontWeight: 600,
                  fontFamily: "'Montserrat', sans-serif",
                  transition: 'all 0.2s ease',
                }}
                title={fd.description || fd.filename || 'download'}
              >
                {fd.label ? fd.label : `Download ${String(fd.format || 'file').toUpperCase()}`}
              </button>
            ))}
          </div>
        ) : null}

        {messageHasExportableData(message) ? (
          <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
            {['csv', 'xlsx', 'pdf', 'html'].map((fmt) => (
              <button
                key={fmt}
                className="export-btn"
                onClick={() => onExport(fmt, message.tool_results, message.export_index, messageIndex)}
                style={{
                  background: 'rgba(0,0,0,0.03)',
                  border: '1px solid rgba(0,0,0,0.08)',
                  borderRadius: 8,
                  padding: '5px 12px',
                  cursor: 'pointer',
                  fontSize: 11,
                  color: '#666',
                  fontWeight: 600,
                  fontFamily: "'Montserrat', sans-serif",
                  transition: 'all 0.2s ease',
                }}
              >
                {fmt.toUpperCase()}
              </button>
            ))}
            <button
              key="bundle"
              className="export-btn"
              onClick={() => onExportBundle(message.tool_results, message.export_index, messageIndex)}
              style={{
                background: 'rgba(0,0,0,0.03)',
                border: '1px solid rgba(0,0,0,0.08)',
                borderRadius: 8,
                padding: '5px 12px',
                cursor: 'pointer',
                fontSize: 11,
                color: '#666',
                fontWeight: 600,
                fontFamily: "'Montserrat', sans-serif",
                transition: 'all 0.2s ease',
              }}
              >
              Bundle ZIP
            </button>
          </div>
        ) : null}

        {metaBits.length ? (
          <div style={{ fontSize: 10, color: '#ccc', marginTop: 6, paddingLeft: 2, fontWeight: 500 }}>
            {metaBits.join(' · ')}
          </div>
        ) : null}

        {isLastAssistant && conversationId ? (
          <FeedbackWidget conversationId={conversationId} messageIndex={messageIndex} onSubmit={onFeedback} />
        ) : null}
      </div>
    </div>
  );
}
