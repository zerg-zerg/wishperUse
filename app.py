# -*- coding: utf-8 -*-
import json
import os
import tempfile

import requests
from flask import Flask, request, render_template_string, send_from_directory
from joppy.server_api import ServerApi

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(BASE_DIR, "static", "icons")

WHISPER_URL = os.environ.get("WHISPER_URL", "http://whisper:9000/v1/audio/transcriptions")
WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY", "")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "ru")
JOPLIN_SERVER_URL = os.environ.get("JOPLIN_SERVER_URL", "")
JOPLIN_SERVER_USER = os.environ.get("JOPLIN_SERVER_USER", "")
JOPLIN_SERVER_PASSWORD = os.environ.get("JOPLIN_SERVER_PASSWORD", "")
NOTEBOOK_ID = os.environ.get("NOTEBOOK_ID", "")

# Публичный адрес приложения (например, https://dict.example.com).
# Нужен, потому что TLS может завершаться на роутере/прокси, и Flask видит внутренний http.
# Если не задан — используется текущий адрес запроса (удобно для локальной отладки).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

ALLOWED_SUFFIXES = {".webm", ".mp4", ".m4a", ".ogg", ".wav"}

SERVICE_WORKER_JS = """
const CACHE_NAME = 'voice-note-shell-v1';
const scopeUrl = self.registration.scope;
const SHELL = [
  scopeUrl,
  new URL('icons/icon-192.png', scopeUrl).href,
  new URL('icons/icon-512.png', scopeUrl).href,
  new URL('icons/icon-maskable-512.png', scopeUrl).href
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.replace(/\\/$/, '').endsWith('/upload')) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(scopeUrl, copy));
          return response;
        })
        .catch(() => caches.match(scopeUrl))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});
"""

HTML_PAGE = """
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="color-scheme" content="dark">
    <title>Голосовая заметка</title>
    <meta name="description" content="Запись голоса с телефона и сохранение расшифровки в Joplin.">
    <meta name="theme-color" content="#0b0b0f">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Заметка">
    <link rel="manifest" href="{{ base }}/manifest.webmanifest">
    <link rel="icon" type="image/png" sizes="192x192" href="{{ base }}/icons/icon-192.png">
    <link rel="apple-touch-icon" href="{{ base }}/icons/icon-192.png">
    <style>
        :root {
            --surface-base: #0b0b0f;
            --surface-raised: #14141a;
            --surface-overlay: #1c1c24;
            --text-primary: #f4f4f6;
            --text-secondary: #a3a3b0;
            --text-tertiary: #74748a;
            --border-subtle: #23232c;
            --border-strong: #34343f;
            --accent: #ff5a4d;
            --accent-hi: #ff8577;
            --accent-deep: #d8412f;
            --accent-wash: rgba(255, 90, 77, 0.12);
            --accent-glow: rgba(255, 90, 77, 0.38);
            --success: #4ade80;
            --success-text: #c9f7d9;
            --error: #ff6b6b;
            --error-text: #ffd4d4;
            --radius-sm: 10px;
            --radius-md: 16px;
            --radius-lg: 22px;
            --radius-xl: 28px;
            --radius-pill: 999px;
            --space-1: 4px;
            --space-2: 8px;
            --space-3: 12px;
            --space-4: 16px;
            --space-5: 20px;
            --space-6: 24px;
            --space-8: 32px;
            --space-10: 40px;
            --dur-micro: 140ms;
            --dur-standard: 240ms;
            --ease-out: cubic-bezier(0.2, 0.8, 0.2, 1);
            --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            --font-mono: ui-monospace, "SF Mono", "Cascadia Mono", "Roboto Mono", Menlo, monospace;
            color-scheme: dark;
        }

        *, *::before, *::after { box-sizing: border-box; }
        html, body { margin: 0; padding: 0; }
        html { -webkit-text-size-adjust: 100%; }

        body {
            min-height: 100dvh;
            color: var(--text-primary);
            font-family: var(--font-sans);
            background:
                radial-gradient(120% 55% at 50% -12%, rgba(255, 90, 77, 0.10), transparent 62%),
                radial-gradient(90% 45% at 50% 112%, rgba(255, 138, 90, 0.05), transparent 68%),
                var(--surface-base);
            -webkit-font-smoothing: antialiased;
            -webkit-tap-highlight-color: transparent;
            overscroll-behavior-y: none;
        }

        .grain {
            position: fixed;
            inset: 0;
            z-index: 1;
            pointer-events: none;
            opacity: 0.035;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E");
        }

        .app {
            position: relative;
            z-index: 2;
            display: flex;
            flex-direction: column;
            gap: var(--space-5);
            width: 100%;
            max-width: 480px;
            min-height: 100dvh;
            margin: 0 auto;
            padding:
                max(var(--space-6), env(safe-area-inset-top))
                max(var(--space-5), env(safe-area-inset-right))
                max(var(--space-5), env(safe-area-inset-bottom))
                max(var(--space-5), env(safe-area-inset-left));
        }

        .app__head {
            display: flex;
            flex-direction: column;
            gap: var(--space-1);
            padding-top: var(--space-2);
        }

        .eyebrow {
            margin: 0;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--text-tertiary);
        }

        .title {
            margin: 0;
            font-size: 24px;
            font-weight: 650;
            line-height: 1.2;
            letter-spacing: -0.02em;
        }

        .recorder {
            flex: 1 1 auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: var(--space-5);
            padding: var(--space-8) var(--space-4);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-xl);
            background:
                radial-gradient(90% 60% at 50% 0%, rgba(255, 255, 255, 0.03), transparent 60%),
                var(--surface-raised);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
            transition: border-color var(--dur-standard) var(--ease-out), background-color var(--dur-standard) var(--ease-out);
        }

        .recorder.is-recording {
            border-color: rgba(255, 90, 77, 0.32);
            background-color: var(--accent-wash);
        }

        .pad {
            position: relative;
            display: grid;
            place-items: center;
            width: clamp(150px, 46vw, 184px);
            aspect-ratio: 1;
        }

        .pad__halo {
            position: absolute;
            inset: 8%;
            border: 1px solid var(--accent);
            border-radius: var(--radius-pill);
            opacity: 0;
            transform: scale(0.92);
            pointer-events: none;
            transition: opacity var(--dur-standard) var(--ease-out), transform var(--dur-standard) var(--ease-out);
        }

        .pad__halo.is-on {
            opacity: 0.4;
            animation: haloPulse 2.4s var(--ease-out) infinite;
        }

        @keyframes haloPulse {
            0% { transform: scale(0.88); opacity: 0.45; }
            70% { transform: scale(1.14); opacity: 0; }
            100% { transform: scale(1.14); opacity: 0; }
        }

        .pad__btn {
            position: relative;
            z-index: 1;
            display: grid;
            place-items: center;
            width: clamp(88px, 27vw, 104px);
            aspect-ratio: 1;
            padding: 0;
            border: 0;
            border-radius: var(--radius-pill);
            color: #fff;
            cursor: pointer;
            touch-action: manipulation;
            background: radial-gradient(130% 130% at 30% 18%, var(--accent-hi) 0%, var(--accent) 46%, var(--accent-deep) 100%);
            box-shadow:
                0 16px 40px -18px var(--accent-glow),
                0 0 0 1px rgba(255, 255, 255, 0.06),
                inset 0 2px 0 rgba(255, 255, 255, 0.22),
                inset 0 -10px 20px rgba(0, 0, 0, 0.22);
            transition: transform var(--dur-micro) var(--ease-out), filter var(--dur-standard) var(--ease-out), box-shadow var(--dur-standard) var(--ease-out);
        }

        .pad__btn:active { transform: scale(0.96); }

        .pad__btn:focus-visible {
            outline: 2px solid var(--accent-hi);
            outline-offset: 4px;
        }

        .pad__btn.is-recording {
            box-shadow:
                0 22px 52px -16px var(--accent-glow),
                0 0 0 1px rgba(255, 255, 255, 0.08),
                inset 0 2px 0 rgba(255, 255, 255, 0.26),
                inset 0 -10px 20px rgba(0, 0, 0, 0.22);
        }

        .pad__btn:disabled {
            cursor: progress;
            filter: saturate(0.55) brightness(0.82);
            transform: none;
        }

        .icon {
            display: block;
            width: 42px;
            height: 42px;
        }

        .icon--stop { display: none; }

        .spinner {
            display: none;
            width: 34px;
            height: 34px;
            border: 3px solid rgba(255, 255, 255, 0.28);
            border-top-color: #fff;
            border-radius: var(--radius-pill);
            animation: spin 0.9s linear infinite;
        }

        .pad__btn.is-recording .icon--mic { display: none; }
        .pad__btn.is-recording .icon--stop { display: block; }
        .pad__btn.is-processing .icon--mic,
        .pad__btn.is-processing .icon--stop { display: none; }
        .pad__btn.is-processing .spinner { display: block; }

        @keyframes spin { to { transform: rotate(360deg); } }

        .readout {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: var(--space-2);
            width: 100%;
        }

        .timer {
            font-family: var(--font-mono);
            font-size: 34px;
            font-weight: 500;
            line-height: 1;
            letter-spacing: 0.04em;
            font-variant-numeric: tabular-nums;
            color: var(--text-tertiary);
            transition: color var(--dur-standard) var(--ease-out);
        }

        .timer.is-live { color: var(--text-primary); }

        .wave {
            display: block;
            width: 100%;
            height: 72px;
            opacity: 0.6;
            transition: opacity var(--dur-standard) var(--ease-out);
        }

        .wave.is-live { opacity: 1; }

        .hint {
            margin: 0;
            font-size: 14px;
            line-height: 1.4;
            text-align: center;
            color: var(--text-secondary);
        }

        .status {
            display: flex;
            align-items: flex-start;
            gap: var(--space-3);
            padding: var(--space-4);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            background: var(--surface-raised);
            font-size: 15px;
            line-height: 1.45;
            color: var(--text-secondary);
            transition: border-color var(--dur-standard) var(--ease-out), color var(--dur-standard) var(--ease-out), background-color var(--dur-standard) var(--ease-out);
        }

        .status__dot {
            flex: none;
            width: 8px;
            height: 8px;
            margin-top: 6px;
            border-radius: var(--radius-pill);
            background: var(--text-tertiary);
            transition: background-color var(--dur-standard) var(--ease-out);
        }

        .status__text {
            min-width: 0;
            overflow-wrap: anywhere;
        }

        .status[data-tone="busy"] { color: var(--text-primary); }
        .status[data-tone="busy"] .status__dot {
            background: var(--accent);
            animation: dotPulse 1.6s var(--ease-out) infinite;
        }

        .status[data-tone="success"] {
            border-color: rgba(74, 222, 128, 0.32);
            color: var(--success-text);
        }
        .status[data-tone="success"] .status__dot { background: var(--success); }

        .status[data-tone="error"] {
            border-color: rgba(255, 107, 107, 0.36);
            color: var(--error-text);
        }
        .status[data-tone="error"] .status__dot { background: var(--error); }

        @keyframes dotPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.35; }
        }

        .install {
            width: 100%;
            min-height: 52px;
            padding: 0 var(--space-5);
            border: 1px solid var(--border-strong);
            border-radius: var(--radius-md);
            background: var(--surface-overlay);
            color: var(--text-primary);
            font: inherit;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform var(--dur-micro) var(--ease-out), background-color var(--dur-standard) var(--ease-out);
        }

        .install:active { transform: scale(0.98); }

        .install:focus-visible {
            outline: 2px solid var(--accent-hi);
            outline-offset: 3px;
        }

        .install[hidden] { display: none; }

        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }

        .noscript {
            position: relative;
            z-index: 2;
            max-width: 480px;
            margin: 0 auto var(--space-5);
            padding: var(--space-4);
            font-size: 15px;
            text-align: center;
            color: var(--error-text);
        }

        @media (max-height: 620px) {
            .recorder { gap: var(--space-4); padding: var(--space-5) var(--space-4); }
            .pad { width: clamp(120px, 36vh, 150px); }
            .pad__btn { width: clamp(76px, 22vh, 88px); }
            .icon { width: 34px; height: 34px; }
            .timer { font-size: 28px; }
            .wave { height: 56px; }
        }

        @media (min-width: 768px) {
            .app {
                padding-top: var(--space-10);
                padding-bottom: var(--space-10);
            }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.001ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.001ms !important;
            }
        }
    </style>
</head>
<body>
    <div class="grain" aria-hidden="true"></div>

    <main class="app">
        <header class="app__head">
            <p class="eyebrow">Whisper · Joplin</p>
            <h1 class="title">Голосовая заметка</h1>
        </header>

        <section class="recorder" aria-labelledby="recorder-title">
            <h2 class="sr-only" id="recorder-title">Запись голоса</h2>

            <div class="pad">
                <span class="pad__halo" id="halo" aria-hidden="true"></span>
                <button
                    class="pad__btn"
                    id="record"
                    type="button"
                    aria-pressed="false"
                    aria-label="Начать запись"
                    aria-describedby="hint"
                >
                    <svg class="icon icon--mic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="9" y="2.5" width="6" height="11.5" rx="3"></rect>
                        <path d="M5 11.5a7 7 0 0 0 14 0"></path>
                        <path d="M12 18.5v3"></path>
                    </svg>
                    <svg class="icon icon--stop" viewBox="0 0 24 24" aria-hidden="true">
                        <rect x="6.5" y="6.5" width="11" height="11" rx="2.5" fill="currentColor"></rect>
                    </svg>
                    <span class="spinner" aria-hidden="true"></span>
                </button>
            </div>

            <div class="readout">
                <div class="timer" id="timer" aria-hidden="true">00:00</div>
                <canvas class="wave" id="wave" aria-hidden="true"></canvas>
            </div>

            <p class="hint" id="hint">Нажмите, чтобы начать запись</p>
        </section>

        <div class="status" id="status" role="status" aria-live="polite" data-tone="neutral">
            <span class="status__dot" aria-hidden="true"></span>
            <span class="status__text" id="statusText">Готово к записи</span>
        </div>

        <button class="install" id="install" type="button" hidden>Установить приложение</button>
    </main>

    <noscript><p class="noscript">Для записи нужен JavaScript.</p></noscript>

    <script>
        (function () {
            'use strict';

            const BASE = {{ base|tojson }};
            const BARS = 44;

            const recordBtn = document.getElementById('record');
            const recorderCard = document.querySelector('.recorder');
            const halo = document.getElementById('halo');
            const timerEl = document.getElementById('timer');
            const canvas = document.getElementById('wave');
            const hintEl = document.getElementById('hint');
            const statusEl = document.getElementById('status');
            const statusText = document.getElementById('statusText');
            const installBtn = document.getElementById('install');
            const ctx2d = canvas.getContext('2d');

            let state = 'idle';
            let recorder = null;
            let stream = null;
            let chunks = [];
            let audioCtx = null;
            let analyser = null;
            let freqData = null;
            let rafId = null;
            let timerId = null;
            let startedAt = 0;
            let dpr = Math.min(window.devicePixelRatio || 1, 3);
            let wakeLock = null;
            let deferredPrompt = null;

            function setStatus(tone, message) {
                statusEl.dataset.tone = tone;
                statusText.textContent = message;
            }

            function setState(next, message) {
                state = next;

                const recording = next === 'recording';
                const processing = next === 'processing';

                recordBtn.classList.toggle('is-recording', recording);
                recordBtn.classList.toggle('is-processing', processing);
                recordBtn.disabled = processing;
                recordBtn.setAttribute('aria-pressed', recording ? 'true' : 'false');
                recordBtn.setAttribute('aria-label', recording ? 'Остановить запись' : 'Начать запись');

                recorderCard.classList.toggle('is-recording', recording);
                halo.classList.toggle('is-on', recording);
                canvas.classList.toggle('is-live', recording);

                hintEl.textContent = recording
                    ? 'Нажмите, чтобы остановить'
                    : processing
                        ? 'Подождите, идёт распознавание'
                        : 'Нажмите, чтобы начать запись';

                if (next === 'idle' || next === 'success' || next === 'error') {
                    timerEl.textContent = '00:00';
                }

                if (message) {
                    setStatus(next === 'success' ? 'success' : next === 'error' ? 'error' : 'neutral', message);
                } else if (recording) {
                    setStatus('busy', 'Идёт запись');
                } else if (processing) {
                    setStatus('busy', 'Отправка на распознавание…');
                } else if (next === 'idle') {
                    setStatus('neutral', 'Готово к записи');
                }
            }

            function pickMimeType() {
                if (typeof MediaRecorder.isTypeSupported !== 'function') return '';
                const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
                return candidates.filter(function (type) {
                    return MediaRecorder.isTypeSupported(type);
                })[0] || '';
            }

            function formatTime(ms) {
                const total = Math.floor(ms / 1000);
                const minutes = String(Math.floor(total / 60)).padStart(2, '0');
                const seconds = String(total % 60).padStart(2, '0');
                return minutes + ':' + seconds;
            }

            function startTimer() {
                stopTimer();
                startedAt = Date.now();
                timerEl.textContent = '00:00';
                timerEl.classList.add('is-live');
                timerId = window.setInterval(function () {
                    timerEl.textContent = formatTime(Date.now() - startedAt);
                }, 250);
            }

            function stopTimer() {
                if (timerId !== null) {
                    window.clearInterval(timerId);
                    timerId = null;
                }
                timerEl.classList.remove('is-live');
            }

            function roundRect(x, y, width, height, radius) {
                const r = Math.min(radius, height / 2, width / 2);
                ctx2d.beginPath();
                if (typeof ctx2d.roundRect === 'function') {
                    ctx2d.roundRect(x, y, width, height, r);
                    return;
                }
                ctx2d.moveTo(x + r, y);
                ctx2d.arcTo(x + width, y, x + width, y + height, r);
                ctx2d.arcTo(x + width, y + height, x, y + height, r);
                ctx2d.arcTo(x, y + height, x, y, r);
                ctx2d.arcTo(x, y, x + width, y, r);
                ctx2d.closePath();
            }

            function barGeometry() {
                const gap = 4 * dpr;
                const barWidth = Math.max(2 * dpr, (canvas.width - gap * (BARS - 1)) / BARS);
                return { gap: gap, barWidth: barWidth };
            }

            function drawIdle() {
                const width = canvas.width;
                const height = canvas.height;
                if (!width || !height) return;

                ctx2d.clearRect(0, 0, width, height);
                const geometry = barGeometry();
                const barHeight = 3 * dpr;

                ctx2d.fillStyle = 'rgba(163, 163, 176, 0.28)';
                for (let i = 0; i < BARS; i += 1) {
                    const x = i * (geometry.barWidth + geometry.gap);
                    roundRect(x, (height - barHeight) / 2, geometry.barWidth, barHeight, barHeight / 2);
                    ctx2d.fill();
                }
            }

            function drawLive() {
                if (!analyser || !freqData) return;

                analyser.getByteFrequencyData(freqData);

                const width = canvas.width;
                const height = canvas.height;
                if (!width || !height) return;

                ctx2d.clearRect(0, 0, width, height);

                const geometry = barGeometry();
                const usable = Math.floor(freqData.length * 0.6);
                const step = Math.max(1, Math.floor(usable / BARS));
                const minHeight = 3 * dpr;

                const gradient = ctx2d.createLinearGradient(0, 0, 0, height);
                gradient.addColorStop(0, '#ff8577');
                gradient.addColorStop(1, '#ff5a4d');
                ctx2d.fillStyle = gradient;

                for (let i = 0; i < BARS; i += 1) {
                    let sum = 0;
                    for (let j = 0; j < step; j += 1) {
                        sum += freqData[i * step + j] || 0;
                    }
                    const energy = sum / step / 255;
                    const barHeight = Math.max(minHeight, Math.pow(energy, 1.35) * height * 0.92);
                    const x = i * (geometry.barWidth + geometry.gap);
                    roundRect(x, (height - barHeight) / 2, geometry.barWidth, barHeight, Math.min(geometry.barWidth / 2, barHeight / 2));
                    ctx2d.fill();
                }
            }

            function sizeCanvas() {
                dpr = Math.min(window.devicePixelRatio || 1, 3);
                const rect = canvas.getBoundingClientRect();
                if (!rect.width || !rect.height) return;
                canvas.width = Math.round(rect.width * dpr);
                canvas.height = Math.round(rect.height * dpr);
                if (state === 'recording') {
                    drawLive();
                } else {
                    drawIdle();
                }
            }

            function startWaveform(sourceStream) {
                const AudioCtor = window.AudioContext || window.webkitAudioContext;
                if (!AudioCtor) return;

                audioCtx = new AudioCtor();
                const source = audioCtx.createMediaStreamSource(sourceStream);
                analyser = audioCtx.createAnalyser();
                analyser.fftSize = 512;
                analyser.smoothingTimeConstant = 0.78;
                source.connect(analyser);
                freqData = new Uint8Array(analyser.frequencyBinCount);

                if (audioCtx.state === 'suspended') {
                    audioCtx.resume().catch(function () {});
                }

                loopWaveform();
            }

            function loopWaveform() {
                if (!analyser || state !== 'recording') return;
                drawLive();
                rafId = window.requestAnimationFrame(loopWaveform);
            }

            function stopWaveform() {
                if (rafId !== null) {
                    window.cancelAnimationFrame(rafId);
                    rafId = null;
                }
                if (audioCtx) {
                    audioCtx.close().catch(function () {});
                    audioCtx = null;
                }
                analyser = null;
                freqData = null;
                drawIdle();
            }

            async function acquireWakeLock() {
                if (!('wakeLock' in navigator) || wakeLock) return;
                try {
                    wakeLock = await navigator.wakeLock.request('screen');
                    wakeLock.addEventListener('release', function () {
                        wakeLock = null;
                    });
                } catch (err) {
                    wakeLock = null;
                }
            }

            function releaseWakeLock() {
                if (!wakeLock) return;
                wakeLock.release().catch(function () {});
                wakeLock = null;
            }

            function teardownCapture() {
                stopWaveform();
                releaseWakeLock();
                if (stream) {
                    stream.getTracks().forEach(function (track) { track.stop(); });
                    stream = null;
                }
                recorder = null;
            }

            async function startRecording() {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
                    setState('error', 'Браузер не поддерживает запись с микрофона. Откройте страницу в Chrome.');
                    return;
                }

                try {
                    stream = await navigator.mediaDevices.getUserMedia({
                        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
                    });
                } catch (err) {
                    stream = null;
                    setState('error', 'Нет доступа к микрофону. Разрешите запись в настройках браузера.');
                    return;
                }

                chunks = [];
                const mimeType = pickMimeType();

                try {
                    recorder = mimeType ? new MediaRecorder(stream, { mimeType: mimeType }) : new MediaRecorder(stream);
                } catch (err) {
                    teardownCapture();
                    setState('error', 'Не удалось запустить запись. Попробуйте ещё раз.');
                    return;
                }

                recorder.addEventListener('dataavailable', function (event) {
                    if (event.data && event.data.size > 0) chunks.push(event.data);
                });
                recorder.addEventListener('stop', handleRecorderStop);
                recorder.addEventListener('error', function () {
                    teardownCapture();
                    setState('error', 'Сбой записи. Попробуйте ещё раз.');
                });

                try {
                    recorder.start(1000);
                } catch (err) {
                    teardownCapture();
                    setState('error', 'Не удалось запустить запись. Попробуйте ещё раз.');
                    return;
                }

                setState('recording');
                startTimer();
                startWaveform(stream);
                acquireWakeLock();
            }

            function stopRecording() {
                if (!recorder || recorder.state === 'inactive') return;
                stopTimer();
                setState('processing');
                try {
                    recorder.stop();
                } catch (err) {
                    teardownCapture();
                    setState('error', 'Не удалось остановить запись. Попробуйте ещё раз.');
                }
            }

            async function handleRecorderStop() {
                const type = (recorder && recorder.mimeType) || 'audio/webm';
                const blob = new Blob(chunks, { type: type });
                chunks = [];
                teardownCapture();

                if (blob.size < 1200) {
                    setState('error', 'Запись слишком короткая. Попробуйте ещё раз.');
                    return;
                }

                const extension = type.indexOf('mp4') !== -1 ? 'mp4' : type.indexOf('ogg') !== -1 ? 'ogg' : 'webm';
                const formData = new FormData();
                formData.append('audio', blob, 'recording.' + extension);

                try {
                    const response = await fetch(BASE + '/upload', { method: 'POST', body: formData });
                    let result = null;
                    try {
                        result = await response.json();
                    } catch (err) {
                        result = null;
                    }

                    if (response.ok && result && result.title) {
                        setState('success', 'Готово. Заметка создана: ' + result.title);
                    } else {
                        const message = result && result.error ? result.error : 'Не удалось сохранить заметку.';
                        setState('error', 'Ошибка: ' + message);
                    }
                } catch (err) {
                    setState('error', 'Ошибка соединения. Проверьте сеть и повторите.');
                }
            }

            recordBtn.addEventListener('click', function () {
                if (state === 'recording') {
                    stopRecording();
                    return;
                }
                if (state === 'processing') return;
                startRecording();
            });

            document.addEventListener('visibilitychange', function () {
                if (document.visibilityState === 'visible' && state === 'recording') {
                    acquireWakeLock();
                }
            });

            window.addEventListener('pagehide', releaseWakeLock);
            window.addEventListener('resize', sizeCanvas);

            if (window.ResizeObserver) {
                new ResizeObserver(sizeCanvas).observe(canvas);
            }

            function isStandalone() {
                return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
            }

            window.addEventListener('beforeinstallprompt', function (event) {
                event.preventDefault();
                deferredPrompt = event;
                if (!isStandalone()) installBtn.hidden = false;
            });

            installBtn.addEventListener('click', async function () {
                if (!deferredPrompt) return;
                deferredPrompt.prompt();
                try {
                    await deferredPrompt.userChoice;
                } catch (err) {
                    // пользователь закрыл системный диалог
                }
                deferredPrompt = null;
                installBtn.hidden = true;
            });

            window.addEventListener('appinstalled', function () {
                deferredPrompt = null;
                installBtn.hidden = true;
                setState('success', 'Приложение установлено.');
            });

            const secureOrigin = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';

            if ('serviceWorker' in navigator && secureOrigin) {
                window.addEventListener('load', function () {
                    navigator.serviceWorker.register(BASE + '/sw.js', { scope: BASE + '/' }).catch(function () {});
                });
            }

            if (isStandalone()) installBtn.hidden = true;

            sizeCanvas();
            drawIdle();
        })();
    </script>
</body>
</html>
"""


def public_base() -> str:
    """Публичный базовый URL без завершающего слэша."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    return request.url_root.rstrip("/")


@app.route("/")
def index():
    return render_template_string(HTML_PAGE, base=public_base())


@app.route("/manifest.webmanifest")
def manifest():
    base = public_base()
    data = {
        "id": base + "/",
        "name": "Голосовая заметка",
        "short_name": "Заметка",
        "description": "Запись голоса с телефона и сохранение расшифровки в Joplin.",
        "lang": "ru",
        "dir": "ltr",
        "start_url": base + "/",
        "scope": base + "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0b0b0f",
        "theme_color": "#0b0b0f",
        "prefer_related_applications": False,
        "icons": [
            {
                "src": base + "/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": base + "/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": base + "/icons/icon-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return app.response_class(
        json.dumps(data, ensure_ascii=False),
        mimetype="application/manifest+json",
    )


@app.route("/sw.js")
def service_worker():
    response = app.response_class(SERVICE_WORKER_JS, mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/icons/<path:filename>")
def icon(filename):
    return send_from_directory(ICONS_DIR, filename, max_age=604800)


@app.route("/upload", methods=["POST"])
def upload_audio():
    if "audio" not in request.files:
        return {"error": "Аудиофайл не найден"}, 400

    audio_file = request.files["audio"]

    suffix = os.path.splitext(audio_file.filename or "")[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        suffix = ".webm"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # 1. Распознавание речи через Whisper
        headers = {}
        if WHISPER_API_KEY:
            headers["Authorization"] = f"Bearer {WHISPER_API_KEY}"

        with open(tmp_path, "rb") as f:
            whisper_response = requests.post(
                WHISPER_URL,
                files={"file": f},
                data={"model": WHISPER_MODEL, "language": WHISPER_LANGUAGE},
                headers=headers,
                timeout=120,
            )
        whisper_response.raise_for_status()
        transcription = whisper_response.json().get("text", "").strip()

        if not transcription:
            return {"error": "Не удалось распознать речь"}, 500

        # 2. Создание заметки в Joplin Server через ServerApi
        api = ServerApi(
            user=JOPLIN_SERVER_USER,
            password=JOPLIN_SERVER_PASSWORD,
            url=JOPLIN_SERVER_URL,
        )

        title = transcription[:50] + ("..." if len(transcription) > 50 else "")

        # ServerApi требует блокировку синхронизации для операций записи
        with api.sync_lock():
            note_id = api.add_note(
                title=title if title else "Голосовая заметка",
                body=transcription,
                parent_id=NOTEBOOK_ID if NOTEBOOK_ID else None,
            )

        return {"title": title, "note_id": note_id}, 200

    except requests.exceptions.RequestException as e:
        return {"error": f"Ошибка при обращении к Whisper: {str(e)}"}, 500
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
