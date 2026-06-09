import json

from nicegui import ui


FIREBASE_WEB_CONFIG = {
    'apiKey': 'AIzaSyDgkl4pYfaJCRQ9ploX3L3CsLx0hP0B-3k',
    'authDomain': 'p1g4-radar-solar-dev.firebaseapp.com',
    'projectId': 'p1g4-radar-solar-dev',
    'storageBucket': 'p1g4-radar-solar-dev.firebasestorage.app',
    'messagingSenderId': '125328174538',
    'appId': '1:125328174538:web:156a0f6329ff1082eaf333',
}


def inject_public_styles() -> None:
    ui.add_head_html('<link rel="stylesheet" href="/assets/public.css">')


def inject_firebase_auth() -> None:
    config_json = json.dumps(FIREBASE_WEB_CONFIG)
    ui.add_body_html(f'''
    <script>window.radarSolarFirebaseConfig = {config_json};</script>
    <script type="module" src="/assets/firebase-auth.js"></script>
    ''')
