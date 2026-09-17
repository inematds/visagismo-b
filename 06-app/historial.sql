-- Estructura del historial de informes (Supabase self-hosted, eu-south).
-- Ya está aplicada; queda aquí para poder recrearla y para saber qué hay.
--
-- REPARTO DE CLAVES, que es lo importante:
--   · La demo escribe con la clave PÚBLICA (anon). Las políticas de abajo solo
--     le permiten INSERT. No puede leer los informes, ni otras tablas, ni
--     descargar del bucket, ni borrar.
--   · La clave de SERVICIO no debe llegar nunca a producción: salta RLS y daría
--     acceso a toda la base de datos desde una demo pública. Solo se usa en
--     local, para leer el historial y para purgar.

create table if not exists visagismo_informes (
  id              bigserial primary key,
  sesion          text not null unique,
  expediente      text not null,          -- MST-XXXX, va impreso en el informe
  creado          timestamptz not null default now(),
  resultado       text not null,          -- entregado | sin-cara | formato-no-admitido | foto-demasiado-grande | error-interno
  morfotipo       text,
  n_proporciones  int,
  n_fuera         int,                    -- cuántas de las 16 quedan fuera de canon
  titular         text,
  ratios          jsonb,                  -- las 16 proporciones medidas
  clasificacion   jsonb,
  receta          jsonb,
  respuestas      jsonb,                  -- SIN el nombre: dato personal que no aporta
  modelo_imagen   text,
  simulacion_ok   boolean,
  desviacion      numeric,                -- lo que dijo el verificador de identidad
  tuvo_perfil     boolean,
  segundos        numeric,
  coste_estimado  numeric,
  informe_ruta    text,                   -- ruta en Storage; null si ya caducó
  informe_caduca  date,
  fotos_ruta      jsonb,                  -- solo si GUARDAR_FOTOS=si
  nota            text,
  analisis_ia     boolean,                -- lo redactó el LLM o el motor de reglas
  modelo_ia       text,
  tokens_ia       jsonb,                  -- {entrada, salida, segundos}
  estilos_ia      jsonb                   -- [{nombre, encaje}] para ver si repite cortes
);

create index if not exists visagismo_informes_creado_idx    on visagismo_informes (creado desc);
create index if not exists visagismo_informes_resultado_idx on visagismo_informes (resultado);

alter table visagismo_informes enable row level security;

create policy visagismo_solo_insertar on visagismo_informes
  for insert to anon with check (true);

create policy visagismo_subir on storage.objects
  for insert to anon with check (bucket_id = 'visagismo-informes');

-- Panorama de un vistazo: una fila por dia.
create or replace view visagismo_por_dia as
select creado::date                                              as dia,
       count(*)                                                  as intentos,
       count(*) filter (where resultado = 'entregado')            as entregados,
       count(*) filter (where resultado = 'sin-cara')             as sin_cara,
       count(*) filter (where resultado <> 'entregado')           as fallos,
       count(*) filter (where simulacion_ok)                      as con_simulacion,
       round(avg(segundos) filter (where resultado = 'entregado'), 1) as seg_medio,
       round(sum(coste_estimado), 2)                              as coste_dia,
       round(avg(desviacion), 2)                                  as desviacion_media
from visagismo_informes
group by 1 order by 1 desc;

-- Que morfotipos esta detectando y con que reparto: si sale casi todo lo mismo,
-- las reglas de clasificacion estan mal calibradas.
create or replace view visagismo_morfotipos as
select coalesce(morfotipo, '(sin medir)')          as morfotipo,
       count(*)                                    as veces,
       round(100.0 * count(*) / sum(count(*)) over (), 1) as pct,
       round(avg(n_fuera), 1)                      as media_fuera_de_canon
from visagismo_informes
where resultado = 'entregado'
group by 1 order by veces desc;

-- Fiabilidad del motor: en cuantos NO encuentra cara. Es la cifra que dice si
-- el producto aguanta fotos de gente real o solo fotos de estudio.
create or replace view visagismo_fiabilidad as
select count(*)                                                        as intentos,
       count(*) filter (where resultado = 'entregado')                 as ok,
       count(*) filter (where resultado = 'sin-cara')                  as sin_cara,
       count(*) filter (where resultado = 'error-interno')             as errores,
       round(100.0 * count(*) filter (where resultado = 'sin-cara')
             / nullif(count(*), 0), 1)                                 as pct_sin_cara,
       count(*) filter (where resultado = 'entregado' and not simulacion_ok)
                                                                       as sin_simulacion
from visagismo_informes;

-- Uso del LLM: cuantos informes lo llevan, que gasta y si tarda demasiado.
create or replace view visagismo_uso_ia as
select count(*) filter (where resultado = 'entregado')            as informes,
       count(*) filter (where analisis_ia)                        as con_ia,
       max(modelo_ia)                                             as modelo,
       round(avg((tokens_ia->>'entrada')::numeric
                 + (tokens_ia->>'salida')::numeric))              as tokens_medios,
       round(avg((tokens_ia->>'segundos')::numeric), 1)           as segundos_medios
from visagismo_informes;
