export function isSpeechRecognitionSupported() {
  if (typeof window === "undefined") return false;
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function createSpeechRecognition({ language = "pt-PT", onResult, onError, onEnd } = {}) {
  if (!isSpeechRecognitionSupported()) {
    throw new Error("O browser não suporta reconhecimento de voz.");
  }

  const RecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new RecognitionCtor();
  recognition.lang = language;
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => {
    let finalTranscript = "";
    let interimTranscript = "";
    for (let i = 0; i < event.results.length; i += 1) {
      const text = String(event.results[i][0]?.transcript || "");
      if (event.results[i].isFinal) {
        finalTranscript += `${text} `;
      } else {
        interimTranscript += `${text} `;
      }
    }
    onResult?.({
      finalTranscript: finalTranscript.trim(),
      interimTranscript: interimTranscript.trim(),
      combinedTranscript: `${finalTranscript} ${interimTranscript}`.trim(),
    });
  };

  recognition.onerror = (event) => {
    onError?.(String(event?.error || "Erro de reconhecimento de voz"));
  };

  recognition.onend = () => {
    onEnd?.();
  };

  return recognition;
}

export async function normalizeSpeechPrompt(authFetchFn, apiUrl, payload) {
  const response = await authFetchFn(apiUrl + "/api/speech/prompt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(String(data?.detail || "Falha ao interpretar o pedido por voz."));
  }
  return data;
}
