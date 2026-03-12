import React from 'react';
import { MILLENNIUM_SYMBOL_DATA_URI } from '../utils/constants.js';
import { RefreshIcon } from './AppIcons.jsx';

export default function ChatEmptyState({ suggestions, onSuggestionClick, onRefreshSuggestions }) {
  return (
    <div className="app-empty-state">
      <img
        src={MILLENNIUM_SYMBOL_DATA_URI}
        alt="Millennium"
        style={{ width: 74, height: 74, margin: '0 auto 24px', display: 'block' }}
      />
      <div className="app-empty-title">Assistente AI DBDE</div>
      <div className="app-empty-subtitle">
        Pesquisa, análise e geração de artefactos com contexto operacional.
      </div>
      <div className="app-suggestion-grid">
        {suggestions.map((question) => (
          <button
            key={question}
            type="button"
            className="suggestion-btn"
            onClick={() => onSuggestionClick(question)}
          >
            {question}
          </button>
        ))}
      </div>
      <button type="button" className="app-ghost-btn" style={{ marginTop: 18 }} onClick={onRefreshSuggestions}>
        <RefreshIcon size={15} />
        Outras sugestões
      </button>
    </div>
  );
}
