# -*- coding: utf-8 -*-
import os
import tempfile
from flask import Flask, request, render_template_string
import requests
from joppy.server_api import ServerApi

app = Flask(__name__)

WHISPER_URL = os.environ.get("WHISPER_URL", "http://whisper:9000/v1/audio/transcriptions")
WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY", "")
JOPLIN_SERVER_URL = os.environ.get("JOPLIN_SERVER_URL", "")
JOPLIN_SERVER_USER = os.environ.get("JOPLIN_SERVER_USER", "")
JOPLIN_SERVER_PASSWORD = os.environ.get("JOPLIN_SERVER_PASSWORD", "")
NOTEBOOK_ID = os.environ.get("NOTEBOOK_ID", "")

HTML_FORM = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Note</title>
    <style>
        body { font-family: system-ui, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; }
        button { padding: 15px 30px; font-size: 18px; margin: 10px 5px; border-radius: 8px; border: none; cursor: pointer; }
        #record { background: #e74c3c; color: white; }
        #stop { background: #3498db; color: white; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        #status { margin-top: 20px; padding: 15px; border-radius: 8px; background: #f0f0f0; }
        .success { background: #d4edda !important; color: #155724; }
        .error { background: #f8d7da !important; color: #721c24; }
    </style>
</head>
<body>
    <h1>🎙️ Голосовая заметка</h1>
    <p>Нажмите «Записать», говорите, затем «Стоп».</p>
    <div>
        <button id="record">Записать</button>
        <button id="stop" disabled>Стоп</button>
    </div>
    <p id="status">Готово к записи</p>

    <script>
    let mediaRecorder;
    let audioChunks = [];
    const recordButton = document.getElementById('record');
    const stopButton = document.getElementById('stop');
    const status = document.getElementById('status');

    recordButton.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const formData = new FormData();
                formData.append('audio', audioBlob, 'recording.webm');

                status.textContent = '⏳ Отправка на распознавание...';
                status.className = '';

                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const result = await response.json();
                    if (response.ok) {
                        status.textContent = '✅ Готово! Заметка создана: ' + result.title;
                        status.className = 'success';
                    } else {
                        status.textContent = '❌ Ошибка: ' + result.error;
                        status.className = 'error';
                    }
                } catch (err) {
                    status.textContent = '❌ Ошибка соединения: ' + err.message;
                    status.className = 'error';
                }

                audioChunks = [];
                recordButton.disabled = false;
                stopButton.disabled = true;
            };

            mediaRecorder.start();
            recordButton.disabled = true;
            stopButton.disabled = false;
            status.textContent = '🔴 Идет запись...';
            status.className = '';
        } catch (err) {
            status.textContent = '❌ Не удалось получить доступ к микрофону: ' + err.message;
            status.className = 'error';
        }
    });

    stopButton.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            status.textContent = '⏳ Обработка...';
            status.className = '';
        }
    });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_FORM)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio' not in request.files:
        return {"error": "Аудиофайл не найден"}, 400

    audio_file = request.files['audio']

    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # 1. Распознавание речи через Whisper
        headers = {}
        if WHISPER_API_KEY:
            headers["Authorization"] = f"Bearer {WHISPER_API_KEY}"

        with open(tmp_path, 'rb') as f:
            whisper_response = requests.post(
                WHISPER_URL,
                files={'file': f},
                data={'model': 'base', 'language': 'ru'},
                headers=headers,
                timeout=120
            )
        whisper_response.raise_for_status()
        transcription = whisper_response.json().get('text', '').strip()

        if not transcription:
            return {"error": "Не удалось распознать речь"}, 500

        # 2. Создание заметки в Joplin Server через ServerApi
        api = ServerApi(
            user=JOPLIN_SERVER_USER,
            password=JOPLIN_SERVER_PASSWORD,
            url=JOPLIN_SERVER_URL
        )

        title = transcription[:50] + ('...' if len(transcription) > 50 else '')

        # ServerApi требует блокировку синхронизации для операций записи
        with api.sync_lock():
            note_id = api.add_note(
                title=title if title else "Голосовая заметка",
                body=transcription,
                parent_id=NOTEBOOK_ID if NOTEBOOK_ID else None
            )

        return {"title": title, "note_id": note_id}, 200

    except requests.exceptions.RequestException as e:
        return {"error": f"Ошибка при обращении к Whisper: {str(e)}"}, 500
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        os.unlink(tmp_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
