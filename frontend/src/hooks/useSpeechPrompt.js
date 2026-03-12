import { useEffect, useRef, useState } from 'react';
import {
  createSpeechRecognition,
  isSpeechRecognitionSupported,
  normalizeSpeechPrompt,
} from '../utils/speech.js';

export default function useSpeechPrompt({
  authFetchFn,
  apiUrl,
  agentMode,
  conversationId,
  inputRef,
  onApplyPrompt,
}) {
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speechListening, setSpeechListening] = useState(false);
  const [speechProcessing, setSpeechProcessing] = useState(false);
  const [speechInterimText, setSpeechInterimText] = useState('');
  const [speechNotice, setSpeechNotice] = useState('');

  const speechRecognitionRef = useRef(null);
  const speechTranscriptRef = useRef('');
  const speechStoppingRef = useRef(false);

  useEffect(() => {
    setSpeechSupported(isSpeechRecognitionSupported());
    return () => {
      if (speechRecognitionRef.current) {
        try {
          speechRecognitionRef.current.abort();
        } catch (_) {
          // ignore cleanup failures
        }
        speechRecognitionRef.current = null;
      }
    };
  }, []);

  function resizeComposerInput() {
    if (!inputRef?.current) return;
    inputRef.current.style.height = 'auto';
    inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
  }

  function clearSpeechNotice() {
    setSpeechNotice('');
  }

  function resetSpeechPrompt() {
    if (speechRecognitionRef.current) {
      try {
        speechRecognitionRef.current.abort();
      } catch (_) {
        // ignore abort failures during reset
      }
      speechRecognitionRef.current = null;
    }
    speechTranscriptRef.current = '';
    speechStoppingRef.current = false;
    setSpeechListening(false);
    setSpeechProcessing(false);
    setSpeechInterimText('');
    setSpeechNotice('');
  }

  function applyNormalizedSpeechPrompt(nextPrompt, notice = '') {
    onApplyPrompt(nextPrompt);
    setSpeechInterimText('');
    setSpeechNotice(notice);
    window.setTimeout(() => {
      if (inputRef?.current) {
        inputRef.current.focus();
        resizeComposerInput();
      }
    }, 0);
  }

  async function finalizeSpeechPrompt(rawTranscript) {
    const transcript = String(rawTranscript || '').trim();
    if (!transcript) {
      setSpeechProcessing(false);
      setSpeechInterimText('');
      setSpeechNotice('Não apanhei texto suficiente. Tenta novamente.');
      return;
    }

    setSpeechProcessing(true);
    setSpeechInterimText(transcript);
    setSpeechNotice('');

    try {
      const normalized = await normalizeSpeechPrompt(authFetchFn, apiUrl, {
        transcript,
        mode: agentMode,
        conversation_id: conversationId || null,
        language: 'pt-PT',
      });

      const finalPrompt = String(normalized?.normalized_prompt || transcript).trim() || transcript;
      const inferredMode = String(normalized?.inferred_mode || agentMode).trim().toLowerCase();
      const confidence = String(normalized?.confidence || 'medium').trim().toLowerCase();
      const notes = Array.isArray(normalized?.notes)
        ? normalized.notes.filter(Boolean).map(item => String(item).trim()).filter(Boolean)
        : [];

      const noticeParts = [];
      if (confidence === 'high') {
        noticeParts.push('Pedido por voz pronto a rever.');
      } else if (confidence === 'low') {
        noticeParts.push('Interpretação com baixa confiança. Revê o texto antes de enviar.');
      } else {
        noticeParts.push('Pedido por voz interpretado. Revê antes de enviar.');
      }
      if (inferredMode && inferredMode !== agentMode) {
        noticeParts.push(inferredMode === 'userstory' ? 'Parece um pedido de User Stories.' : 'Parece um pedido do modo geral.');
      }
      if (notes.length > 0) {
        noticeParts.push(notes[0]);
      }

      applyNormalizedSpeechPrompt(finalPrompt, noticeParts.join(' '));
    } catch (error) {
      setSpeechNotice(error?.message || 'Falha ao interpretar o pedido por voz.');
    } finally {
      setSpeechProcessing(false);
      setSpeechInterimText('');
    }
  }

  function toggleSpeech() {
    if (!speechSupported) {
      setSpeechNotice('O browser atual não suporta reconhecimento de voz.');
      return;
    }

    if (speechListening && speechRecognitionRef.current) {
      speechStoppingRef.current = true;
      try {
        speechRecognitionRef.current.stop();
      } catch (_) {
        try {
          speechRecognitionRef.current.abort();
        } catch (_) {
          // ignore stop/abort race
        }
      }
      setSpeechListening(false);
      setSpeechNotice('A terminar a captação de voz...');
      return;
    }

    speechTranscriptRef.current = '';
    speechStoppingRef.current = false;
    setSpeechNotice('');
    setSpeechInterimText('');
    setSpeechProcessing(false);

    try {
      const recognition = createSpeechRecognition({
        language: 'pt-PT',
        onResult: ({ finalTranscript, combinedTranscript }) => {
          const transcript = String(finalTranscript || combinedTranscript || '').trim();
          speechTranscriptRef.current = transcript;
          setSpeechInterimText(String(combinedTranscript || transcript || '').trim());
        },
        onError: (errorCode) => {
          const code = String(errorCode || '').trim();
          const friendlyMessage =
            code === 'not-allowed' || code === 'service-not-allowed'
              ? 'A permissão do microfone foi negada neste browser.'
              : code === 'no-speech'
                ? 'Não apanhei fala suficiente. Tenta novamente.'
                : 'O reconhecimento de voz falhou. Tenta novamente.';
          speechRecognitionRef.current = null;
          setSpeechListening(false);
          setSpeechProcessing(false);
          setSpeechInterimText('');
          if (!speechTranscriptRef.current.trim()) {
            setSpeechNotice(friendlyMessage);
          }
        },
        onEnd: () => {
          const transcript = speechTranscriptRef.current;
          speechRecognitionRef.current = null;
          setSpeechListening(false);
          const wasStopping = speechStoppingRef.current;
          speechStoppingRef.current = false;
          if (transcript.trim()) {
            finalizeSpeechPrompt(transcript);
            return;
          }
          if (wasStopping) {
            setSpeechNotice('Captação de voz terminada sem texto suficiente.');
          }
        },
      });

      speechRecognitionRef.current = recognition;
      recognition.start();
      setSpeechListening(true);
      setSpeechNotice('');
    } catch (error) {
      speechRecognitionRef.current = null;
      setSpeechListening(false);
      setSpeechProcessing(false);
      setSpeechInterimText('');
      setSpeechNotice(error?.message || 'Não foi possível iniciar a captação de voz.');
    }
  }

  return {
    speechSupported,
    speechListening,
    speechProcessing,
    speechInterimText,
    speechNotice,
    clearSpeechNotice,
    resetSpeechPrompt,
    toggleSpeech,
  };
}
