import React from 'react';
import { formatStreamingToolLabel } from '../utils/streaming.js';

function buildSummaryBits(detail) {
  const summary = detail && detail.result_summary ? detail.result_summary : {};
  const bits = [];
  const totalCount = summary.total_count;
  const itemsReturned = Number(summary.items_returned || 0);
  if (totalCount !== undefined && totalCount !== null && totalCount !== '' && totalCount !== 'N/A') {
    bits.push(`${totalCount} resultados`);
  }
  if (itemsReturned > 0) {
    bits.push(`${itemsReturned} itens visiveis`);
  }
  if (summary.has_error) {
    bits.push('com alertas');
  }
  return bits;
}

export default function ToolExecutionSummary({ details = [] }) {
  const rows = Array.isArray(details) ? details.filter(Boolean) : [];
  if (!rows.length) return null;

  return (
    <div
      style={{
        marginTop: 8,
        padding: '12px 14px',
        borderRadius: 14,
        background: 'rgba(16, 18, 23, 0.03)',
        border: '1px solid rgba(16, 18, 23, 0.06)',
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: '#6E7480',
          marginBottom: 10,
        }}
      >
        Contexto usado
      </div>

      <div style={{ display: 'grid', gap: 8 }}>
        {rows.slice(0, 5).map((detail, index) => {
          const bits = buildSummaryBits(detail);
          return (
            <div
              key={`${detail.tool || 'tool'}-${index}`}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: detail?.result_summary?.has_error ? '#A02222' : '#D1005D',
                  marginTop: 6,
                  flexShrink: 0,
                }}
              />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#14171D' }}>
                  {formatStreamingToolLabel(detail.tool)}
                </div>
                {bits.length ? (
                  <div style={{ marginTop: 2, fontSize: 11, color: '#6E7480', lineHeight: 1.45 }}>
                    {bits.join(' · ')}
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
