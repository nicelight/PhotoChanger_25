## Саммари расследования

- За последние 10 часов зафиксированы 502 на `/api/ingest/*` (см. `trobleshooting/08.01.26/incident.md`).
- В БД `job_history` все ошибки — `status=failed`, `failure_reason=provider_error`, без таймаутов.
- По логам `gemini.response.body` при ошибках приходит `finishReason: "NO_IMAGE"` и **нет `content.parts`**.
- Ответы Gemini имеют `HTTP 200 OK`; проблема — в содержимом ответа (NO_IMAGE), а не в сетевом/HTTP слое.
- По `usageMetadata.promptTokensDetails` присутствует `modality: IMAGE`, значит **входное изображение получено провайдером**.
- Переход на `responseModalities=["IMAGE"]` выполнен; проблема `NO_IMAGE` остаётся интермиттентной.

## Текущее состояние

- Инцидент продолжается: периодически Gemini возвращает `NO_IMAGE`, из-за чего API отдаёт 502.
- Дополнительных признаков safety/finishMessage нет (в ответах только `NO_IMAGE`).
- Логи текущего уровня достаточны для фиксации `responseId` и `finishReason`.
- Среднее время ответа провайдера для проблемных запросов `NO_IMAGE` составляет ~1.22 с (диапазон примерно 1.03–1.73 с).

## Проблемные responseId (NO_IMAGE)

3IVfaf_oKtvQz7IPlJbBSQ  
4oFfabnJI9bRz7IP98qTkAw  
5HhfaZvMA-Osz7IPvI3K0QY  
AXRfaanzHZaDz7IPvYXJqQI  
AZFfafWoNoLrz7IPwNT0sAs  
f4FfaYj7G5Prz7IPzavk0QE  
JW1faaLAO5biz7IP5fi64A0  
JY9fae6GBaDqz7IPudTm0Qo  
LJBfaYW8GIbOz7IPyJnhqAY  
mpFfafH8CKHUz7IP6KLN-Qs  
nJRfafL-PKDUz7IP4-yksQU  
nZNfafeTNuOsz7IPvI3K0QY  
OI9fadimI_fQz7IPjq6ngAg  
onBfaZKOArnUz7IPw7fbuAU  
QZBfabyBG9bRz7IP98qTkAw  
rHRfae3KNrrUz7IPx8LPsAo  
SGpfaf_vJbrUz7IPx8LPsAo  
uGNfaZHlL43jz7IPk4iY-AY  
VZBfabrzFYjmz7IPu4TLqA8  
WoRfaeapEvjVz7IP2c7I0Qo  
Xnhfaa7ZDZbiz7IP5fi64A0  
YIhfabDrDMHQz7IP54XFiQg

## Рекомендации/следующие шаги

- Собрать список `responseId` с `NO_IMAGE` и эскалировать в поддержку Gemini при необходимости.
- Продолжить мониторинг доли `NO_IMAGE` по времени/слотам.
