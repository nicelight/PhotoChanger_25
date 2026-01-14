# Провайдер Turbotext (фото-API)

> Источник: [Официальная документация Turbotext Photo AI](https://www.turbotext.ru/photo_ai/docs/info) (раздел «Фото - методы»).

## Аутентификация и базовый протокол

- **Хост**: `https://www.turbotext.ru`.
- **Тип запросов**: `POST` с `Content-Type: application/x-www-form-urlencoded`.
- **Авторизация**: заголовок `Authorization: Bearer {APIKEY}` обязателен для всех вызовов.
- **Шаг 1 — создание очереди**: передать `do=create_queue` и параметры операции. Успешный ответ `{"success":true,"queueid":<ID>}`.
- **Шаг 2 — опрос результата**: запрос с `do=get_result` и `queueid`. Пока генерация не готова, сервис возвращает `{"action":"reconnect"}`; после завершения — JSON с `success=true`, блоком `data` и ссылкой `uploaded_image` на готовый файл.
- **Ожидание результата**: платформа хранит `queueid` и повторяет polling только в пределах `T_sync_response`; по истечении окна задача завершается.
- **Передача файлов**: в PhotoChanger мы НЕ используем механизм публичных URL Turbotext. Изображение передаётся в `create_queue` как загруженный файл (`multipart/form-data`, поле `file`). Провайдер возвращает `uploaded_image`, но ссылка используется лишь для мгновенной загрузки и сохранения в локальное хранилище; публичный доступ мы не предоставляем.

## Операции

### Обработка фото (`/api_ai/generate_image2image`)

| Параметр | Тип | Обязательность | Описание |
| --- | --- | --- | --- |
| `url` | string (URL) | required | Ссылка на исходное изображение (форматы: JPG/PNG/WEBP). |
| `content` | string | required | Текстовый промпт, описывающий желаемые изменения. |
| `strength` | integer | optional (`0–80`, default `40`) | Степень изменения исходной картинки. |
| `seed` | integer | optional (`1–10^10`, default random) | Фиксирует детерминированность результата. |
| `scale` | float | optional (`0.1–20`, default `7.5`) | Guidance scale. |
| `negative_prompt` | string | optional | Что нужно исключить (до ~80 слов). |
| `original_language` | string | optional (default `ru`) | Язык исходного промпта. |
| `user_id` | integer | optional (default `1`) | Служебный идентификатор аккаунта Turbotext. |

**Ответ**: после `do=get_result` Turbotext возвращает `data.image` (массив путей, например `"image/generate_image2image_id12_0.png"`), промпт и параметры генерации. Поле `uploaded_image` используется драйвером для одноразового скачивания результата. PhotoChanger перед выдачей результата сохраняет файл локально, а временные ссылки `/public/provider-media/{media_id}` предоставляются только на время обработки.


#### API
1. Запрос на создании очереди
```
/api_ai/generate_image2image HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:create_queue
user_id: int `# default: 1`
url: string - required `# url with image (format: jpg, png, jpeg)`
content: string - required ` # prompt for image2image`
strength: int ` # degree of image change, 0 to 80, default: 40`
seed: int `# min: 1, max: 10**10, default: random`
scale: float `# min: 0.1, max: 20, default: 7.5`
negative_prompt: string `# what to remove on image (max: 80 words), default: bad anatomy params`
original_language: string `# default: ru` 
```
2. Ответ с данными очереди в формате JSON
`{"success":true,"queueid":{QUEUEID}}`
{QUEUEID} - Номер вашей очереди, далее обращаемся за получением результата использую этот массив данных.
3.  Делаем запрос на получение результата
```
/api_ai/generate_image2image HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:get_result
queueid:{QUEUEID}  
```
4. Ответ с данными генерации в формате JSON
Если генерация завершена вы получите success=true, если вы получили action=reconnect отправляем запрос заново, после получения success=true получаем данные генерации
```
{
"success": true,
"error": "",
"data": {
"user_id": 12,
"image": [
"image/generate_image2image_id12_0.png"
],
"prompt": "девушка в костюме супермена",
"width": 768,
"height": 768,
"scale": 7.5,
"seed": 5443937701,
"strength": 50,
"original_language": "ru"
}
} 
```







#### API
1. Запрос на создании очереди
```
/api_ai/generate_image2image HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:create_queue
user_id: int `# default: 1`
url: string - required `# url with image (format: jpg, png, jpeg)`
content: string - required ` # prompt for image2image`
strength: int ` # degree of image change, 0 to 80, default: 40`
seed: int `# min: 1, max: 10**10, default: random`
scale: float `# min: 0.1, max: 20, default: 7.5`
negative_prompt: string `# what to remove on image (max: 80 words), default: bad anatomy params`
original_language: string `# default: ru` 
```
2. Ответ с данными очереди в формате JSON
`{"success":true,"queueid":{QUEUEID}}`
{QUEUEID} - Номер вашей очереди, далее обращаемся за получением результата использую этот массив данных.
3.  Делаем запрос на получение результата
```
/api_ai/generate_image2image HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:get_result
queueid:{QUEUEID}  
```
4. Ответ с данными генерации в формате JSON
Если генерация завершена вы получите success=true, если вы получили action=reconnect отправляем запрос заново, после получения success=true получаем данные генерации
```
{
"success": true,
"error": "",
"data": {
"user_id": 12,
"image": [
"image/generate_image2image_id12_0.png"
],
"prompt": "девушка в костюме супермена",
"width": 768,
"height": 768,
"scale": 7.5,
"seed": 5443937701,
"strength": 50,
"original_language": "ru"
}
} 
```






### Метод «Микс-фото» (`/api_ai/mix_images`)

| Параметр | Тип | Обязательность | Описание |
| --- | --- | --- | --- |
| `url_image_target` | string (URL) | required | Фото, в которое переносится стиль/сочетается изображение. |
| `url` | string (URL) | required | Фото-источник стиля. |
| `content` | string | optional | Дополнительное текстовое описание эффекта. |

**Ответ**: блок `data` содержит сведения о ширине/высоте, `prompt`, `strength`, `pattern_prompt`; `uploaded_image` скачивается драйвером и сразу сохраняется локально без дальнейшего публичного доступа.

#### API
1. Запрос на создании очереди
```
/api_ai/mix_images HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:create_queue
content - описание для усиления эффекта
url_image_target - фото на урл которое нужно обработать
url - фото на урл откуда используем стиль 
```
2. Ответ с данными очереди в формате JSON
`{"success":true,"queueid":{QUEUEID}}`
{QUEUEID} - Номер вашей очереди, далее обращаемся за получением результата использую этот массив данных.
3.  Делаем запрос на получение результата
```
/api_ai/mix_images HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:get_result
queueid:{QUEUEID} 
```
4. Ответ с данными генерации в формате JSON
Если генерация завершена вы получите success=true, если вы получили action=reconnect отправляем запрос заново, после получения success=true получаем данные генерации
```
{"success":true,"error":"","data":{"prompt":"В стиле дисней"],"width":768,"height":576,"seed":9147962925,"strength":50,"pattern_prompt":false},"uploaded_image":"https://www.turbotext.ru/download.php?f=..........png"} 
```








### Замена лица (`/api_ai/deepfake_photo`)

| Параметр | Тип | Обязательность | Описание |
| --- | --- | --- | --- |
| `url` | string (URL) | required | Фото человека, которому требуется заменить лицо. |
| `url_image_target` | string (URL) | required | Фото с лицом, которое нужно перенести. |
| `face_restore` | boolean (`True/False`) | optional | Включает дообработку лица после подстановки. |

**Ответ**: `data.image` содержит массив ссылок на результат (обычно одно изображение) с признаками `width`, `height`, `face_restore`. Ссылка `uploaded_image` используется только внутри адаптера для загрузки файла; наружу не выдаётся.

#### API
1. Запрос на создании очереди
```
/api_ai/deepfake_photo HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:create_queue
url - урл с фото человека кому будем менять лицо
url_image_target - урл с лицом на которое нужно заменить
face_restore - True/False 
```
2. Ответ с данными очереди в формате JSON
`{"success":true,"queueid":{QUEUEID}}`
{QUEUEID} - Номер вашей очереди, далее обращаемся за получением результата использую этот массив данных.
3.  Делаем запрос на получение результата
```
/api_ai/deepfake_photo HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0

do:get_result
queueid:{QUEUEID} 
```
4. Ответ с данными генерации в формате JSON
Если генерация завершена вы получите success=true, если вы получили action=reconnect отправляем запрос заново, после получения success=true получаем данные генерации
```
{
"success":true,
"error":"",
"data":{"image":["https://...png"],
"width":980,"height":1472,"forbidden_content":false,"face_restore":"False"},
"uploaded_image":"Ссылка на фото с результатом генерации"
} 
```

#### 

## Особенности интеграции

- Все методы работают через очередь: платформа хранит `queueid` и сопоставляет его с задачей в своей очереди.
- Поле `action="reconnect"` при опросе означает, что нужно повторить `do=get_result` через интервал (например, 2–3 секунды).
- После выдачи ingest 504 задача немедленно финализируется: воркер прекращает polling, очищает временные ресурсы и помечает `failure_reason = 'timeout'`.
- Turbotext считает каждую операцию «Фото попыткой», поэтому биллинг и квоты должны учитывать количество обращений к API.
- Входные файлы передаются напрямую в `create_queue` (multipart). Требуемый MIME — JPEG/PNG/WEBP; остальные форматы отклоняются ещё до обращения к API.

## Ссылки

1. [Основы работы с API Turbotext — Фото методы](https://www.turbotext.ru/photo_ai/docs/info)

## Деградации и ретраи
> Ретраи выполняются на уровне драйвера; ingest не повторяет вызовы.
> Для единообразия действует общий лимит: `retry_policy.max_attempts` ≤ 3 и `backoff_seconds` default 2s для transient ошибок.
> Для Turbotext ретраи относятся к `create_queue`; polling `get_result` считается частью одного вызова драйвера.

### Очередь зависла (`action="reconnect"` > `T_sync_response`)
- Если при polling значение `action="reconnect"` повторяется, но окно SLA ещё не истекло, продолжайте опрос каждые 2–3 с.
- Как только до конца SLA остаётся < 5 с, прекращайте опрос, возвращайте 504 (`provider_timeout`), очищайте временные ссылки.
- При повторении ситуации ≥ 3 раз за 15 минут переведите слот в «degraded» и уведомите админа.

### Ошибки `success=false`
- Код `error="LIMIT"` → верните ingest 429 или 503 (`provider_error`), пометьте слот как деградирующий, запросите у заказчика увеличение квоты.
- Ошибки вида `url_error`, `params_error` означают проблему с конфигурацией: задача завершается `provider_error`, добавляется запись в журнал, слот требует проверки настроек.
- Ошибки `face_not_detected`/`quality_limit` логируются в `job_history`; повторная отправка допускается только по ручному запросу администратора, чтобы не списывать лишние попытки.

### Недоступность сервиса (`HTTP 500/502/503`)
- Делайте до двух повторов `create_queue` с экспоненциальным backoff (2 с, затем 5 с), если остаётся ≥ 10 с. После второй неудачи — `provider_error`.
- Сообщайте админу, если HTTP 503 повторяется более 5 раз в течение 10 минут.

### Потеря результата
- Если `uploaded_image` возвращает 404/410 при скачивании, пробуйте ещё раз, пока SLA позволяет (обычно результат доступен повторно 1–2 раза).
- При повторных 404 итоговый статус — `provider_error`, адаптер логирует предупреждение и отправляет админам уведомление, что провайдер потерял файл.

## Логирование (KISS)
- Драйвер пишет подробные логи провайдера, ingest — итоговый статус (success/timeout/provider_error).
- Минимальные поля: `slot_id`, `job_id`, `provider`, `model`, `http_status`, `error_message` (усечённая до 300 символов).
- Запрещено логировать payload и большие response body.
