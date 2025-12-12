---

title: Initial Deploy — Alma Linux 9 + Docker Compose
updated: 2025-12-12
owner: ops
----------

# Цель

Развернуть **PhotoChanger** на новом сервере **AlmaLinux 9** с **Docker Compose**, используя отдельного сервисного пользователя и **выделенную директорию приложения** `/opt/photochanger/app`.

# Предпосылки

* Свежая AlmaLinux 9 с доступом root (sudo).
* Открыт внешний порт (8000 или через реверс-прокси 80/443).
* Подготовлены боевые значения `.env.local` и `secrets/runtime_credentials.json` (не хранить в git).

---

## 0) Обновление системы

```bash
sudo dnf upgrade -y
sudo dnf install -y dnf-utils
needs-restarting -r || true
```

Если требуется перезагрузка:

```bash
sudo reboot
```

---

## 1) Сервисный пользователь и директории

Создаём сервисного пользователя и **структуру каталогов**:

```bash
sudo useradd -r -m -d /opt/photochanger -s /bin/bash photochanger
sudo mkdir -p /opt/photochanger/app
sudo chown -R photochanger:photochanger /opt/photochanger
```

Если нужен интерактивный логин:

```bash
sudo passwd photochanger
```

Итоговая структура:

```text
/opt/photochanger
├── app        # код приложения и docker-compose
├── .bashrc
├── .bash_profile
└── ...
```

---

## 2) Установка Docker и Compose plugin

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

Проверка:

```bash
docker version
docker compose version
```

---

## 3) Доступ к Docker без sudo

```bash
sudo usermod -aG docker photochanger
```

Перелогиниться:

```bash
su - photochanger
```

Проверка:

```bash
docker ps
```

---

## 4) Получить проект и подготовить секреты

Под пользователем **photochanger**:

```bash
cd /opt/photochanger/app
git clone https://github.com/nicelight/PhotoChanger_25.git .
mkdir -p secrets
```

### Копирование секретов с Windows (PowerShell)

```powershell
scp C:\Users\Acer\Documents\python_lessons\PhotoChanger_25\secrets\runtime_credentials.json root@108.181.252.78:/opt/photochanger/app/secrets/runtime_credentials.json
```

```powershell
scp C:\Users\Acer\Documents\python_lessons\PhotoChanger_25\.env.local root@108.181.252.78:/opt/photochanger/app/.env.local
```

### Права на сервере (под root)

```bash
su -
sudo chown -R photochanger:photochanger /opt/photochanger/app/secrets
sudo chmod 600 /opt/photochanger/app/secrets/runtime_credentials.json
sudo chown photochanger:photochanger /opt/photochanger/app/.env.local
sudo chmod 600 /opt/photochanger/app/.env.local
su photochanger
```

### Исправить `.env.local` и проверить ключевые переменные
`cd /opt/photochanger/app`
`nano .env.local`
коментим локальные 3 строки, раскоментим 3 продовские 

* `DATABASE_URL=postgresql://...@postgres:5432/...`
* `MEDIA_ROOT=/app/media`
* `ADMIN_CREDENTIALS_PATH=/app/secrets/runtime_credentials.json`
* `PUBLIC_MEDIA_BASE_URL` — без двойной схемы (`https://https://`)

---

## 5) Запуск сервисов ( первый раз)

Под **photochanger**:

```bash
cd /opt/photochanger/app
docker compose up -d --build
```
на счет миграций возникли трудности, следующая команда давала ошибки
`docker compose exec app alembic upgrade head`
поэтому делаем:
```bash
docker compose down
su -
cd /opt/photochanger/app/
sudo chown -R photochanger:photochanger /opt/photochanger
sudo find /opt/photochanger -type d -exec chmod 750 {} \;
sudo find /opt/photochanger -type f -exec chmod 640 {} \;
su photochanger
rm -rf /opt/photochanger/app/pgdata
cd /opt/photochanger/app/
docker compose up -d --build

docker compose exec postgres psql -U phchadmin -d photochanger -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec app alembic upgrade head
docker compose exec postgres psql -U phchadmin -d photochanger -c "\d slot"
docker compose exec postgres psql -U phchadmin -d photochanger -c "select * from alembic_version;"

curl -f http://localhost:8000/metrics | head
```

Открываем порт
```bash
sudo systemctl status firewalld
sudo systemctl enable --now firewalld
sudo firewall-cmd --get-active-zones
```
если отобразится активная зона не `public` исправить команды ниже
```bash
sudo firewall-cmd --zone=public --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
sudo firewall-cmd --zone=public --list-ports
```

---

## 6) Smoke-проверки

```bash
curl -f http://localhost:8000/metrics | head
```

UI:

* `http://108.181.252.78:8000/ui/static/admin/dashboard.html`
* `http://108.181.252.78:8000/ui/static/admin/dashboard.html`

---

## 7) Cron cleanup (каждые 15 минут)

Под root:

```bash
(crontab -l 2>/dev/null; echo "*/15 * * * * cd /opt/photochanger/app && docker compose exec -T app python scripts/cleanup_media.py >> /var/log/photochanger-cleanup.log 2>&1") | crontab -
```

---

# Проверка после деплоя

* `docker ps` показывает `photochanger-app` и `photochanger-pg`.
* `/metrics` возвращает текст.
* Cron пишет `/var/log/photochanger-cleanup.log`.

---

# Эксплуатация и обновление PROD

## Ручное обновление (rolling через compose)

Под **photochanger**:

```bash
cd /opt/photochanger/app
git pull
docker compose build app
docker compose run --rm app alembic upgrade head
docker compose up -d app
docker compose exec app curl -f http://localhost:8000/metrics | head
```

### Проверка таймингов job

```bash
docker compose exec postgres psql -U phchadmin -d photochanger -c "select job_id,started_at,completed_at,extract(epoch from (completed_at-started_at)) as seconds from job_history order by started_at desc limit 3;"
```

### Перезапуск приложения при необходимости

```bash
cd /opt/photochanger/app
docker compose restart app
```
