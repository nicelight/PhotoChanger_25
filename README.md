# PhotoChanger_25
AI платформа для генерации вкусных фотографий.

uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000

http://127.0.0.1:8000/ui/static/admin/dashboard.html

## Deployment

### HTTP Support

You can deploy this application on a server without HTTPS (plain HTTP). It is fully supported.
However, when using the **Turbotext** provider, you must ensure the `PUBLIC_MEDIA_BASE_URL` environment variable is set to your server's public HTTP URL (e.g., `http://your-server-ip:8000`).

Example:
```bash
export PUBLIC_MEDIA_BASE_URL="http://your-server-ip:8000"
```

If you are using **Gemini**, this variable is not strictly required but recommended for consistency.

Note: Some browser features (like clipboard access) might behave differently on non-secure contexts, but the dashboard includes fallbacks to ensure functionality.
