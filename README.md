# Обёртка над Keitaro (тестовое Adrobot)

FastAPI + SQLAlchemy-обёртка над Admin API трекера Keitaro.
Две функции: **создание кампаний** (гео-поток на Google + поток на оффер)
и **редактор офферов** существующей кампании (добавление/удаление с
перерасчётом долей).

## Что внутри

- `app/keitaro/client.py` — обёртка над Admin API (campaigns, streams, offers, группы, домены, источники);
- `app/services.py` — сборка потоков, добавление/удаление офферов, перерасчёт долей;
- `app/routers/` — REST-эндпоинты обёртки;
- `app/static/` — фронт (HTML + vanilla JS, без сборки);
- `alembic/` — миграции;
- `app/models.py` — локальный журнал операций обёртки.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # и вставьте свой KEITARO_API_KEY из админки стенда

# миграции
alembic upgrade head

# запуск
uvicorn app.main:app --reload
```

Интерфейс: http://127.0.0.1:8000/ , API-доки: http://127.0.0.1:8000/docs

## Как это работает

### Создание кампании

`POST /api/campaigns` с телом `{"name", "geo_code", "offer_id"}`:

1. проверяется, что оффер существует (`GET /offers/{id}`);
2. `POST /campaigns` — кампания с доменом, группой и источником
   (берутся из API по названию FORTESTS, иначе — дефолтные id из настроек);
3. `POST /streams` — поток 1: `type: regular, schema: redirect`,
   фильтр `country` в режиме accept по введённому гео-коду, редирект на Google;
4. `POST /streams` — поток 2: `type: default, schema: landings`
   с единственным оффером, доля 100.

Гео-код валидируется на две заглавные латинские буквы. В страну
подставляется ровно то, что ввёл пользователь, — никакого переопределения.

### Редактор офферов

- `GET /api/campaigns/{id}/offers` — состав offers-потока (веса + проценты);
- `POST /api/campaigns/{id}/offers` — добавить оффер. Так как поле `offers`
  заменяет состав потока целиком, обёртка читает текущий состав, дописывает
  оффер и отправляет список обратно через `PUT /streams/{id}`;
- `DELETE /api/campaigns/{id}/offers/{offer_id}` — удалить оффер: он
  действительно исключается из потока, его доля перераспределяется между
  оставшимися пропорционально весам. Если удалён последний оффер — поток
  выключается (`POST /streams/{id}/disable`).

### Заметки

- Ссылка на кампанию в админке стенда: `https://keitaro-for-tests.etolegko.com/admin/#!/campaign.editor/<id>`.
- Каждый вызов обёртки к API пишется в локальную таблицу `operation_logs` (плюс есть журнал на стенде).
- Офферы, группы, домены и источники — read-only: обёртка их только читает.
