---
title: Initial Deploy — Alma Linux + Docker Compose
updated: 2025-12-03
owner: ops
---

# Цель
Развернуть PhotoChanger на новом сервере Alma Linux с Docker Compose, отдельным пользователем и базовыми проверками.

# Предпосылки
- Свежая Alma/RHEL-система с доступом root (sudo).
- Открыт порт 8000 (или свой) для HTTP.
- Готовы боевые значения для `.env` и `secrets/runtime_credentials.json` (не хранить в git).

# Шаги
0)  Обновы
   ```bash
   sudo dnf update -y
   sudo dnf upgrade -y
   sudo dnf install -y dnf-utils

   needs-restarting -r
   если надо то
   sudo reboot

   ```
1) Создать сервисного пользователя и базовую директорию (под root):
   ```bash
   sudo useradd -r -m -d /opt/photochanger -s /bin/bash photochanger
   sudo chown -R photochanger:photochanger /opt/photochanger
   ```
   Если нужен обычный логин по паролю/SSH — задайте пароль: `sudo passwd photochanger` или создайте без `-r`.

2) Установить Docker + compose plugin (под root):
   ```bash
   sudo dnf -y install dnf-plugins-core
   sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
   sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
   sudo systemctl enable --now docker
   docker version
   docker compose version
   ```

3) Добавить пользователя в группу docker и перелогиниться:
   ```bash
   sudo usermod -aG docker photochanger
   # затем выйти из сессии root и войти как photochanger:
   su - photochanger
   ```

4) Получить проект и подготовить секреты (под photochanger) — предполагаем, что `/opt/photochanger` пустой (если нет, очистить вручную):
   ```bash
   cd /opt/photochanger
   git clone https://github.com/nicelight/PhotoChanger_25.git .
   # заполните переменные в .env.local (приложение читает его по умолчанию)
   mkdir -p secrets
   скопировать содержимое папки secrets и .env.local на сервер
   # на видне в PowerShell:
   `scp C:\Users\Acer\Documents\python_lessons\PhotoChanger_25\secrets\runtime_credentials.json \
    root@45.8.146.32:/opt/photochanger/secrets/`
   `
   `scp C:\Users\Acer\Documents\python_lessons\PhotoChanger_25\.env.local `
    root@45.8.146.32:/opt/photochanger/.env.local`
    # на сервере  поправить владельца и права:
   `su -`

   `chown -R photochanger:photochanger /opt/photochanger/secrets`
   `chmod 600 /opt/photochanger/secrets/runtime_credentials.json`
   `chown photochanger:photochanger /opt/photochanger/.env.local`
   `chmod 600 /opt/photochanger/.env.local`
   `su - photochanger`
   

   Проверьте `.env`: `DATABASE_URL=postgresql://...@postgres:5432/...`, `MEDIA_ROOT=/app/media`, `ADMIN_CREDENTIALS_PATH=/app/secrets/runtime_credentials.json`, корректный `PUBLIC_MEDIA_BASE_URL` (без двойной схемы).s

5) Запустить сервисы:
   ```bash
   cd /opt/photochanger
   docker compose up -d --build
   docker compose exec app alembic upgrade head
   ```

6) Смоук-проверки (под photochanger):
   ```bash
   # healthz пока не реализован; используем /metrics как smoke
   curl -f http://localhost:8000/metrics | head
   ```
  Главная страница http://108.181.252.78:8000/ui/static/admin/dashboard.html


7) Настроить cron cleanup (под root; каждые 15 минут):
   ```bash
   (crontab -l 2>/dev/null; echo "*/15 * * * * docker exec photochanger-app python scripts/cleanup_media.py >> /var/log/photochanger-cleanup.log 2>&1") | crontab -
   ```
   При желании указать пользователя: `sudo -u photochanger docker exec ...`.

8) Если нужен внешний домен/TLS — поставить реверс-прокси (nginx/Caddy) и пробросить на `http://localhost:8000`; `PUBLIC_MEDIA_BASE_URL` должен указывать на публичный базовый URL.

# Проверка после деплоя
- `docker ps` показывает `photochanger-app` и `photochanger-pg`.
- `/healthz` → 200, `/metrics` отдают текст.
- Cron пишет логи и возвращает код 0 (`cleanup done ...`).




---




# Эксплуатационные заметки и обновление PROD
- Не коммитить `.env` и `secrets/` в git; права 600, владелец `photochanger`.
- При обновлении: `git pull` → `docker compose build` → `docker compose up -d` → `docker compose exec app alembic upgrade head` → смоук `/healthz`/`/metrics`.


## Ручное обновление prod (rolling через compose)
> Выполнять под `photochanger`, в корне `/opt/photochanger`. При ошибках не откатывать БД вручную — сначала сверить миграции.

1) Подготовка:
   ```bash
   su - photochanger
   cd /opt/photochanger
   git pull
   ```
   При необходимости подтянуть secrets/.env (scp/rsync) перед сборкой.

2) Сборка нового образа:
   ```bash
   docker compose build app
   ```

3) Миграции БД (на свежем образе, без запуска нового сервиса):
   ```bash
   docker compose run --rm app alembic upgrade head
   ```

4) Переключение приложения на новый образ:
   ```bash
   docker compose up -d app
   ```

5) Смоук-проверка:
   ```bash
   docker compose ps
   docker compose exec app curl -f http://localhost:8000/metrics | head
   ```
   В UI: зайти на `/ui/static/admin/dashboard.html` и убедиться, что загружается.

6) (Опционально) проверить тайминги последних job:
   ```bash
   docker compose exec postgres psql -U phchadmin -d photochanger -c \
     "select job_id,started_at,completed_at,extract(epoch from (completed_at-started_at)) as seconds from job_history order by started_at desc limit 3;"
   ```

7) Перезапуск при необходимости:
   ```bash
   docker compose restart app
   ```

9) перезапуск приложения 
cd /opt/photochanger
docker compose restart app

11) Тесты 
посмотреть тайминги джобов 
```
docker compose exec postgres psql -U phchadmin -d photochanger -c "select job_id,started_at,completed_at,extract(epoch from (completed_at-started_at)) as seconds from job_history order by started_at desc limit 3;"
```
