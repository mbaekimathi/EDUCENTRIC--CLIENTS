"""
Django WSGI entry for cPanel.

In Setup Python App set:
  Application startup file = django_wsgi.py
  Application Entry point  = application

Do NOT set the startup file to passenger_wsgi.py — cPanel wraps that
file and will recurse forever if it points at itself.
"""

import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application
from django.conf import settings

application = get_wsgi_application()
# Visible in cPanel stderr after restart — confirms Passenger loaded .env
sys.stderr.write(
    f"[EDUCENTRIC-CLIENTS] ALLOWED_HOSTS={settings.ALLOWED_HOSTS!r} "
    f"DEBUG={settings.DEBUG} LOCAL={getattr(settings, 'LOCAL', '?')}\n"
)
sys.stderr.flush()
