# Neuralib · una biblioteca con bibliotecario

*Read this in [English](README.md).*

**En vivo: [neuralib-m8q6.onrender.com](https://neuralib-m8q6.onrender.com)** (plan gratuito: la primera visita tras un rato sin uso tarda cerca de un minuto en despertar).

Un catálogo de 300 libros de dominio público (Project Gutenberg, en español y en inglés), y uno que no lo es, con un buscador por palabras y un bibliotecario que recomienda en lenguaje natural. El bibliotecario lee el catálogo entero y solo contesta con libros que están en él: cuando el resumen de un libro dice por qué encaja, cita la línea, y el código comprueba que la cita existe; cuando encaja por lo que el modelo sabe del libro más allá de su resumen, la respuesta lo dice. Es un proyecto de bootcamp de 2023, rescatado y reescrito en 2026; la historia del repositorio cuenta cómo.

> La IA tiene riesgos. El código los acota. La norma responde de lo que queda.

[Filosofía de diseño](#filosofía-de-diseño) · [Dónde aporta valor la IA](#dónde-aporta-valor-la-ia) · [El catálogo entero, no una búsqueda](#el-catálogo-entero-no-una-búsqueda) · [Los cinco pasos](#los-cinco-pasos-en-este-proyecto) · [Medido](#medido) · [Probarlo](#probarlo-en-local) · [Limitaciones](#limitaciones) · [Seguridad y regulación](#seguridad-y-regulación)

---

## Filosofía de diseño

Cualquier aplicación con IA tiene cinco pasos. Solo uno decide con un modelo; los demás son código: reproducibles, testeables, sin red. El paso 5 nunca corrige: marca y descarta. Texto completo en [epifaneia.dev](https://epifaneia.dev).

```
 1 LIMPIEZA      2 CONTEXTO      3 GUARDARRAÍL IN    4 PROCESO        5 GUARDARRAÍL OUT
 ■ código        ■ código        ■ código            ▲ modelo         ■ código
```

Aquí hay un modelo, en el paso 4: un modelo de lenguaje (`gemini-3.5-flash-lite`) que elige y explica. Todo lo que dice pasa por el paso 5.

## Dónde aporta valor la IA

Un lector no busca "título contiene X": pide "algo para reírme", "una historia de amor que acabe bien", "algo corto para leer de una sentada". Ninguna búsqueda por palabras responde a eso, y por eso el buscador del catálogo sigue siendo por palabras: el significado es cosa del bibliotecario. El modelo aporta dos cosas distintas: leer (relacionar la pregunta con lo que dicen los resúmenes) y saber (conocer las tramas, los autores y la fama de libros que lleva siglos leyendo el mundo). Las dos van en la misma respuesta, y cada recomendación dice cuál es: una cita de su resumen, comprobada, o el conocimiento del modelo, con su etiqueta. El código se queda con todo lo demás: qué libros existen, qué cita es real, qué se enseña y qué se descarta.

## El catálogo entero, no una búsqueda

Hasta el 3 de noviembre el bibliotecario funcionaba como un RAG de manual: un modelo de vectores ordenaba el catálogo por cercanía de significado, pgvector guardaba los vectores, y dos llamadas leían los 12 y los 40 libros más cercanos. Después volvió a la primera idea, la más sencilla: darle al modelo el catálogo entero. 301 libros con sus resúmenes recortados a 600 caracteres son unos 53.000 tokens, que un modelo actual lee en una llamada. Es la misma regla que en [ctsm](https://github.com/epifaneia/ctsm) y [toolkit](https://github.com/epifaneia/toolkit): el corpus entero cuando cabe, una búsqueda solo cuando no. La versión con vectores sigue en la historia, y [Medido](#medido) compara las dos.

---

## Los cinco pasos en este proyecto

★ marca dónde está la mejora en este proyecto: el **guardarraíl de entrada** y el **de salida**.

| Paso | Qué hace aquí | |
|---|---|---|
| 1 · Limpieza | `import_gutenberg` trae los libros más descargados por idioma desde la API pública Gutendex: descarta los que aún tienen derechos, los que no son texto y los que no tienen resumen; limpia títulos con restos de catalogación (`$b`, `::`); marca los resúmenes generados automáticamente. Repetirlo actualiza, no duplica. | |
| 2 · Contexto | El catálogo entero en cada pregunta, siempre en el mismo orden: id, título, autor, categoría, materias y el resumen recortado a 600 caracteres, unos 53.000 tokens. No se recupera nada: con 301 libros no hay nada que dejar fuera. Si el catálogo dejara de caber en el contexto del modelo, aquí es donde volvería una búsqueda. El buscador es por palabras: título, autor, resumen, materia, categoría, idioma o ISBN. | |
| 3 · Guardarraíl de entrada | La respuesta es JSON con un schema cuyo `book_id` es un enum de los ids del catálogo: nombrar un libro de fuera es estructuralmente imposible. Cada recomendación lleva una `quote`, literal de su resumen, o vacía cuando el motivo es el conocimiento del modelo. Las preguntas van limitadas a 500 caracteres y a lectores con sesión. | ★ |
| 4 · Proceso | Una llamada por pregunta: "si el resumen dice por qué encaja, copia el fragmento que lo dice (una frase o parte de ella, nunca solo el título); si encaja por lo que sabes más allá del resumen, deja la cita vacía y di lo que sabes; deja fuera los libros que no conozcas". | |
| 5 · Guardarraíl de salida | `librarian.check_picks` descarta: id que no está en el catálogo, motivo vacío, repetido, más de tres, y una cita que no está literalmente en el resumen de ese libro (mayúsculas, espacios, comillas y puntos aparte; mínimo 20 caracteres). La página dice cuántas se descartaron. Una recomendación sin cita se enseña como conocimiento del modelo, sin comprobar. | ★ |

## Medido

Dos sets de preguntas redactadas para esta medición (no por el modelo que se evalúa), con los libros que deberían salir, por id de Gutenberg: [`eval/questions.json`](eval/questions.json) y [`eval/questions_hard.json`](eval/questions_hard.json). `python manage.py evaluate` reproduce las tablas y guarda las respuestas en bruto en [`eval/results/`](eval/results/). Medido el 3-11-2026 sobre los 301 libros.

**Set base, 36 preguntas** que describen la trama sin el título; preguntas en español para libros que solo están en inglés y al revés; 2 sin respuesta en el catálogo.

| Qué | Resultado |
|---|---|
| Recomienda el libro esperado | 34 / 34 |
| … con una cita comprobada de su resumen | 34 / 34 |
| Sin respuesta en el catálogo: no recomienda nada | 2 / 2 |
| Citas que pasan la comprobación | 41 / 42 |
| Tokens por pregunta | unos 53.000 |

**Set difícil, 18 preguntas** de tres tipos: *conocimiento* (la respuesta pide un dato que ningún resumen tiene: Lepanto, El cuervo, Colliure), *ánimo* (varias respuestas válidas, cuestión de gusto) y *trampa* (negaciones, palabras engañosas, nada en el catálogo).

| Tipo | Lo recomienda | Con cita comprobada | Solo por conocimiento | Silencio cuando nada encaja |
|---|---|---|---|---|
| Conocimiento (7) | 7 / 7 | 4 / 7 | 3 | — |
| Ánimo (5) | 4 / 5 | 4 / 5 | 0 | — |
| Trampa (6) | 3 / 4 | 2 / 4 | 1 | 2 / 2 |

**Frente a la versión con vectores**, las mismas 54 preguntas:

| | Búsqueda por vectores y dos pasadas (28-10-2026) | Catálogo entero, una llamada (3-11-2026) |
|---|---|---|
| Llamadas por pregunta | 3: un embedding y dos generaciones | 1 |
| Tokens por pregunta | unos 3.500 (estimado; las mediciones de octubre no los contaban) | unos 53.000 |
| Recomienda el libro esperado (50 preguntas) | 50 / 50 | 48 / 50 |
| Preguntas de ánimo con cita comprobada | 3 / 5 | 4 / 5 |
| Silencio cuando nada encaja | 4 / 4 | 4 / 4 |
| Citas que pasan la comprobación | 64 / 65 | 56 / 63 |

De esas tablas sale lo siguiente. La llamada única encuentra el libro esperado en 48 de 50, y cuáles son los dos que falla cambia de una medición a otra: una primera, antes de dos arreglos (las comillas ya no cuentan en la comprobación; la instrucción pide un fragmento, no el título), falló *Lazarillo* y la poesía latinoamericana; esta falla "algo corto" (propuso *Jekyll*, también corto, pero no está en la lista) y "un libro sobre el mar que no sea una novela de aventuras". Con sets tan pequeños eso es ruido, no una diferencia. Lo que sí cambia: las preguntas de ánimo, que la búsqueda ordenaba mal (el libro corto esperado salía en el puesto 26), ahora salen casi siempre con una cita comprobada, porque el modelo ve todos los libros. Y el modelo cita peor con 301 libros delante: a veces copia una materia (*Saint Petersburg (Russia) -- Fiction*), un título a secas o una frase que ha traducido al idioma de la pregunta. La comprobación las descarta todas, y ninguna llega al lector. El precio es el contexto: unas 15 veces más tokens por pregunta, que con la cuota gratuita de Gemini no cuesta nada.

## Probarlo en local

Hace falta Postgres con la extensión pgvector disponible, porque una migración antigua, de la versión con vectores, todavía la crea: el plan gratuito de [Neon](https://neon.com) la tiene (usa la conexión directa, no la agrupada). La clave de Gemini es opcional; mejor de un proyecto sin facturación, para que nada se pueda cobrar.

```bash
python -m venv .venv && .venv/Scripts/activate    # en Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                              # DATABASE_URL y, si quieres, GEMINI_API_KEY
python manage.py migrate
python manage.py import_gutenberg                 # 150 libros en español y 150 en inglés
python manage.py add_nogum                        # el que no es de dominio público
python manage.py runserver
python manage.py test                             # 72 pruebas, sin llamar a Gemini ni a Gutenberg
python manage.py evaluate --questions eval/questions_hard.json
```

El catálogo no necesita clave: su búsqueda es por palabras. Sin `GEMINI_API_KEY`, el bibliotecario pide a cada lector su propia clave (página "AI key"): se guarda en su navegador y es su navegador quien habla con Google.

**Heroku.** `Procfile` con `release: migrate` y gunicorn; WhiteNoise sirve los estáticos. Basta con `DATABASE_URL`, `SECRET_KEY` y, si se quiere que el sitio conteste con su propia clave, `GEMINI_API_KEY` como config vars. En producción el sitio exige HTTPS, cookies seguras y HSTS, y no arranca sin `SECRET_KEY`.

**Render.** `render.yaml` es un blueprint para un servicio web gratuito: instala, recoge los estáticos, migra y arranca gunicorn, y genera `SECRET_KEY`. Pega `DATABASE_URL` (Neon) y, si quieres, `GEMINI_API_KEY` cuando lo pida. El plan gratuito se duerme tras un rato sin visitas, así que la primera petición después tarda cerca de un minuto.

## Limitaciones

- **Una cita comprobada no es un motivo comprobado.** El código garantiza que la cita existe en el resumen de ese libro, no que diga lo que dice el motivo: un motivo puede añadir a una cita real lo que sabe el modelo (dónde vivió un autor, dónde murió). Comprobarlo exigiría otro modelo de juez, y eso ya no es código comprobando.
- Una recomendación sin cita no se puede comprobar: lo que el modelo sabe de un libro se enseña como suyo, con la etiqueta, y puede equivocarse.
- Los resúmenes los genera automáticamente Project Gutenberg (285 de 300) y están en inglés; la web lo dice en cada ficha. Las citas, por tanto, salen en inglés aunque la pregunta sea en español, y cuando el modelo traduce una, la comprobación la descarta.
- El catálogo entero va en cada pregunta. Hoy cabe; con unos miles de libros no cabría, y una búsqueda tendría que elegir qué lee el modelo.
- Los sets son pequeños (54 preguntas) y las preguntas de ánimo tienen respuestas de gusto: léelos como prueba de humo, no como benchmark. En el set base, que no distingue, todo sale cerca del 100 %.
- Los topes diarios viven en la caché local del proceso: con un solo dyno basta; con varios, cada uno contaría por su lado.
- Hay copias repetidas del mismo libro en los dos idiomas (*Treasure Island* y *La isla del tesoro*); el bibliotecario puede recomendar las dos.

---

## Seguridad y regulación

Los mismos cuatro epígrafes en todos los repositorios. Las filas **hoy** son lo que hace el código. Este repositorio no trae los tres cables de integración (identidad, eventos, firma) de [toolkit](https://github.com/epifaneia/toolkit): es una demo pública sobre libros de dominio público, sin datos confidenciales que custodiar.

| | | |
|---|---|---|
| **Confidencialidad** | La clave del sitio vive solo en `.env` o en las config vars, nunca en git, y viaja a Google en una cabecera, nunca en la URL. La clave de un lector vive solo en su navegador (se olvida al cerrar la pestaña salvo que pida recordarla) y nunca llega al servidor. A Google van la pregunta y el catálogo (títulos, autores y resúmenes de libros de dominio público); la página lo dice. En el EEE, Suiza y Reino Unido, los términos de Gemini aplican a la cuota gratuita las condiciones de pago: no usan lo enviado para mejorar sus productos. | **hoy** |
| **Trazabilidad** | Cada respuesta del bibliotecario queda en `LibrarianAnswer`: pregunta, libros recomendados con cita comprobada y los que vienen del conocimiento del modelo, descartes, modelo y de quién era la clave. Sin el lector. Solo lectura en el admin. Las mediciones guardan las respuestas en bruto del modelo. | **hoy** |
| **Prevención de fugas** | El modelo no tiene credenciales ni acceso a la base de datos: solo ve el catálogo que se le da, y solo puede contestar con sus ids. Con la clave del lector, el servidor nunca hace la llamada: prepara la petición, comprueba la respuesta en bruto con un token de un solo uso ligado a ese lector, y nada más. | **hoy** |
| **Humano en el bucle** | El bibliotecario recomienda; el lector decide. Cada recomendación dice si viene del resumen, con su cita, o del conocimiento del modelo, y la página dice cuántas sugerencias se descartaron y por qué. Si nada encaja, lo dice. | **hoy** |

Marco: EU AI Act (2024/1689) · RGPD.

---

## Estructura

```
library/     models · views · librarian (la petición con el catálogo entero, y sus comprobaciones) · quota · gemini
             gutenberg (importación) · evaluation · management/commands/ (import_gutenberg · add_nogum · evaluate)
             templates/ · static/library/librarian.js (la clave del lector, solo en el navegador) · tests/ (72 pruebas)
eval/        questions.json · questions_hard.json · results/ (cada medición, con las respuestas en bruto)
django_library/  settings (local y Heroku en un fichero) · urls
.github/workflows/tests.yml   las pruebas contra Postgres 17 con pgvector en cada push
```

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
