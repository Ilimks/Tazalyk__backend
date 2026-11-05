-- Отдельный пользователь базы для приложения, без прав суперпользователя.
-- Если приложение взломают, суперпользователь дал бы доступ ко всему серверу базы,
-- а этот пользователь работает только с таблицами сайта.
--
-- Запуск на сервере, пароль в команде подставьте свой:
--   docker exec -i tazalyk_db psql -U postgres -d tazalyk -v ON_ERROR_STOP=1 \
--     -v app_password='НОВЫЙ_ПАРОЛЬ' < backend/deploy/create_app_role.sql
--
-- Затем в .env рядом с docker-compose.prod.yml:
--   DB_APP_USER=tazalyk_app
--   DB_APP_PASSWORD=НОВЫЙ_ПАРОЛЬ
-- и пересоздайте контейнер бэкенда.

CREATE ROLE tazalyk_app LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

ALTER DATABASE tazalyk OWNER TO tazalyk_app;
ALTER SCHEMA public OWNER TO tazalyk_app;

-- Django выполняет миграции от этого же пользователя, поэтому таблицы должны быть его
DO $$
DECLARE
    item record;
BEGIN
    FOR item IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I OWNER TO tazalyk_app', item.tablename);
    END LOOP;
    FOR item IN
        SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER SEQUENCE public.%I OWNER TO tazalyk_app', item.sequencename);
    END LOOP;
END $$;
