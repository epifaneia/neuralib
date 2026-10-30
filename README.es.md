# Neuralib · una biblioteca con bibliotecario

*Read this in [English](README.md).*

**En vivo: [neuralib-m8q6.onrender.com](https://neuralib-m8q6.onrender.com)** (plan gratuito: la primera visita tras un rato sin uso tarda cerca de un minuto en despertar).

Un catálogo de 300 libros de dominio público (Project Gutenberg, en español y en inglés), y uno que no lo es, con búsqueda por significado y un bibliotecario que recomienda en lenguaje natural. El bibliotecario contesta dos veces, y solo con libros del catálogo: una desde los resúmenes, citando la línea que respalda cada recomendación (el código comprueba que la cita existe), y otra desde lo que el modelo sabe de esos libros, marcada como tal. Es un proyecto de bootcamp de 2023, rescatado y reescrito en 2026; la historia del repositorio cuenta cómo.

> La IA tiene riesgos. El código los acota. La norma responde de lo que queda.

[Filosofía de diseño](#filosofía-de-diseño) · [Dónde aporta valor la IA](#dónde-aporta-valor-la-ia) · [Los cinco pasos](#los-cinco-pasos-en-este-proyecto) · [Medido](#medido) · [Probarlo](#probarlo-en-local) · [Limitaciones](#limitaciones) · [Seguridad y regulación](#seguridad-y-regulación)

---

## Filosofía de diseño

Cualquier aplicación con IA tiene cinco pasos. Solo uno decide con un modelo; los demás son código: reproducibles, testeables, sin red. El paso 5 nunca corrige: marca y descarta. Texto completo en [epifaneia.dev](https://epifaneia.dev).

```
 1 LIMPIEZA      2 CONTEXTO      3 GUARDARRAÍL IN    4 PROCESO        5 GUARDARRAÍL OUT
 ■ código        ■ código + ▲    ■ código            ▲ modelo         ■ código
```

Aquí hay dos modelos y conviene decir dónde. En el paso 2, un modelo de vectores (`gemini-embedding-001`) solo ordena el catálogo por cercanía de significado; no escribe nada. En el paso 4, un modelo de lenguaje (`gemini-3.5-flash-lite`) elige y explica, y todo lo que dice pasa por el paso 5.

## Dónde aporta valor la IA

Un lector no busca "título contiene X": pide "algo para reírme", "una historia de amor que acabe bien", "algo corto para leer de una sentada". Ninguna búsqueda por palabras responde a eso, y ningún resumen dice cuánto dura un libro o cómo acaba. El modelo aporta dos cosas distintas, y por eso hay dos pasadas: leer (relacionar la pregunta con lo que dicen los resúmenes) y saber (conocer las tramas, los autores y la fama de libros que lleva siglos leyendo el mundo). El código se queda con todo lo demás: qué libros existen, qué cita es real, qué se enseña y qué se descarta.

---

## Los cinco pasos en este proyecto

★ marca dónde está la mejora en este proyecto: el **guardarraíl de entrada** y el **de salida**.

| Paso | Qué hace aquí | |
|---|---|---|
| 1 · Limpieza | `import_gutenberg` trae los libros más descargados por idioma desde la API pública Gutendex: descarta los que aún tienen derechos, los que no son texto y los que no tienen resumen; limpia títulos con restos de catalogación (`$b`, `::`); marca los resúmenes generados automáticamente. Repetirlo actualiza, no duplica. | |
| 2 · Contexto | Cada libro tiene un vector de 768 dimensiones (título, autor, categoría, materias y resumen) en Postgres con pgvector e índice HNSW; `embed_books` solo rehace los que cambiaron. Para cada pregunta: los 12 más cercanos, con resumen, para la pasada de resúmenes; los 40 más cercanos, solo título y autor, para la de conocimiento. | |
| 3 · Guardarraíl de entrada | Cada pasada pide JSON con un schema cuyo `book_id` es un enum de los libros listados: nombrar un libro de fuera de la lista es estructuralmente imposible. La pasada de resúmenes exige además una `quote` literal. Las preguntas van limitadas a 500 caracteres y a lectores con sesión. | ★ |
| 4 · Proceso | Dos llamadas por pregunta. Resúmenes: "solo con lo que dicen los resúmenes; si el resumen no dice por qué encaja, déjalo fuera". Conocimiento: "con lo que sabes de estos libros; deja fuera los que no conozcas". | |
| 5 · Guardarraíl de salida | `librarian.check_summary_picks` y `check_knowledge_picks` descartan: id no listado, motivo vacío, repetido, más de tres, y en la primera pasada una cita que no está literalmente en el resumen de ese libro (mayúsculas, espacios, comillas y puntos aparte; mínimo 20 caracteres). La página dice cuántas se descartaron. Lo que dice la segunda pasada se enseña como conocimiento del modelo, sin comprobar. | ★ |

## Medido

Dos sets de preguntas redactadas para esta medición (no por el modelo que se evalúa), con los libros que deberían salir, por id de Gutenberg: [`eval/questions.json`](eval/questions.json) y [`eval/questions_hard.json`](eval/questions_hard.json). `python manage.py evaluate` reproduce las tablas y guarda las respuestas en bruto en [`eval/results/`](eval/results/). Medido el 28-10-2026 con la cuota gratuita de Gemini, sobre los 300 libros de Gutenberg.

**Set base, 36 preguntas** que describen la trama sin el título; preguntas en español para libros que solo están en inglés y al revés; 2 sin respuesta en el catálogo.

| Qué | Resultado |
|---|---|
| Búsqueda: el libro esperado entre los 5 primeros | 34 / 34 (MRR 0,971) |
| Pasada de resúmenes: lo recomienda | 32 / 34 |
| Pasada de conocimiento: lo recomienda | 34 / 34 |
| Sin respuesta en el catálogo: no recomienda nada | 2 / 2 en las dos pasadas |
| Citas que pasan la comprobación | 36 / 37 |

**Set difícil, 18 preguntas** de tres tipos: *conocimiento* (la respuesta pide un dato que ningún resumen tiene: Lepanto, El cuervo, Colliure), *ánimo* (varias respuestas válidas, cuestión de gusto) y *trampa* (negaciones, palabras engañosas, nada en el catálogo).

| Tipo | Búsqueda: entre los 5 primeros | Resúmenes | Conocimiento | Solo lo encontró el conocimiento | Silencio cuando nada encaja |
|---|---|---|---|---|---|
| Conocimiento (7) | 7 / 7 | 7 / 7 | 7 / 7 | 0 | — |
| Ánimo (5) | 2 / 5 | 3 / 5 | **5 / 5** | **2** | — |
| Trampa (6) | 4 / 4 | 4 / 4 | 4 / 4 | 0 | 2 / 2 |

De esas tablas salen tres cosas. El set base es fácil y sirve para ver que la tubería funciona de punta a punta, no para comparar. La segunda pasada se gana el sitio en las preguntas de ánimo: con "una historia de amor que acabe bien" los resúmenes no sacan nada, porque ninguno cuenta el final, y el conocimiento saca *Pride and Prejudice*, *The Blue Castle* y *The Enchanted April*; "algo corto para leer de una sentada" solo lo resuelve el conocimiento, porque ningún resumen dice cuánto dura un libro. Y la búsqueda ordena mal esas preguntas (el libro corto esperado salía en el puesto 26): por eso la pasada de conocimiento mira 40 libros y no 12.

La cita rechazada es de verdad un fallo del modelo: copió *"Edmond Dants"* donde el resumen dice *"Dantès"*. El libro era el correcto; la pasada de conocimiento lo recomendó igual. La comprobación no se relaja: o la cita es literal o no pasa.

## Probarlo en local

Hace falta Postgres con pgvector: el plan gratuito de [Neon](https://neon.com) sirve (usa la conexión directa, no la agrupada). La clave de Gemini es opcional; mejor de un proyecto sin facturación, para que nada se pueda cobrar.

```bash
python -m venv .venv && .venv/Scripts/activate    # en Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                              # DATABASE_URL y, si quieres, GEMINI_API_KEY
python manage.py migrate
python manage.py import_gutenberg                 # 150 libros en español y 150 en inglés
python manage.py add_nogum                        # el que no es de dominio público
python manage.py embed_books                      # 6 llamadas de 50 libros
python manage.py runserver
python manage.py test                             # 81 pruebas, sin llamar a Gemini ni a Gutenberg
python manage.py evaluate --questions eval/questions_hard.json
```

Sin `GEMINI_API_KEY` el catálogo funciona igual, por palabras. El bibliotecario entonces pide a cada lector su propia clave (página "AI key"): se guarda en su navegador y es su navegador quien habla con Google.

**Heroku.** `Procfile` con `release: migrate` y gunicorn; WhiteNoise sirve los estáticos. Basta con `DATABASE_URL`, `SECRET_KEY` y, si se quiere que el sitio conteste con su propia clave, `GEMINI_API_KEY` como config vars. En producción el sitio exige HTTPS, cookies seguras y HSTS, y no arranca sin `SECRET_KEY`.

**Render.** `render.yaml` es un blueprint para un servicio web gratuito: instala, recoge los estáticos, migra y arranca gunicorn, y genera `SECRET_KEY`. Pega `DATABASE_URL` (Neon) y, si quieres, `GEMINI_API_KEY` cuando lo pida. El plan gratuito se duerme tras un rato sin visitas, así que la primera petición después tarda cerca de un minuto.

## Limitaciones

- **Una cita comprobada no es un motivo comprobado.** El código garantiza que la cita existe en el resumen de ese libro, no que diga lo que dice el motivo. Ejemplo real: *"Poemas del poeta sevillano que murió en Colliure huyendo de la guerra"* → *Páginas escogidas*, motivo *"…Antonio Machado, quien residió en Sevilla y falleció en Colliure"*, cita *"Páginas escogidas by Antonio Machado is a collection of poems"*: Sevilla y Colliure los pone el modelo, no la cita. Desde que se le pide que el motivo diga solo lo que dice su cita, pasa en 2 de las 7 preguntas de conocimiento, no en todas. Comprobarlo exigiría otro modelo de juez, y eso ya no es código comprobando.
- La segunda pasada no se puede comprobar: lo que el modelo sabe de un libro se enseña como suyo, con la etiqueta, y puede equivocarse.
- Los resúmenes los genera automáticamente Project Gutenberg (285 de 300) y están en inglés; la web lo dice en cada ficha. Las citas, por tanto, salen en inglés aunque la pregunta sea en español.
- Los sets son pequeños (54 preguntas) y las preguntas de ánimo tienen respuestas de gusto: léelos como prueba de humo, no como benchmark. En el set base, que no distingue, todo sale cerca del 100 %.
- La búsqueda también "sabe": "el autor de El cuervo" pone a Poe primero aunque ningún resumen nombre El cuervo, porque el vector del libro incluye al autor y el modelo de vectores asocia uno con otro.
- Los topes diarios viven en la caché local del proceso: con un solo dyno basta; con varios, cada uno contaría por su lado.
- Hay copias repetidas del mismo libro en los dos idiomas (*Treasure Island* y *La isla del tesoro*); el bibliotecario puede recomendar las dos.

---

## Seguridad y regulación

Los mismos cuatro epígrafes en todos los repositorios. Las filas **hoy** son lo que hace el código. Este repositorio no trae los tres cables de integración (identidad, eventos, firma) de [toolkit](https://github.com/epifaneia/toolkit): es una demo pública sobre libros de dominio público, sin datos confidenciales que custodiar.

| | | |
|---|---|---|
| **Confidencialidad** | La clave del sitio vive solo en `.env` o en las config vars, nunca en git, y viaja a Google en una cabecera, nunca en la URL. La clave de un lector vive solo en su navegador (se olvida al cerrar la pestaña salvo que pida recordarla) y nunca llega al servidor. A Google van la pregunta y los títulos o resúmenes de los libros candidatos; la página lo dice. En el EEE, Suiza y Reino Unido, los términos de Gemini aplican a la cuota gratuita las condiciones de pago: no usan lo enviado para mejorar sus productos. | **hoy** |
| **Trazabilidad** | Cada respuesta del bibliotecario queda en `LibrarianAnswer`: pregunta, libros de cada pasada, descartes, si la segunda falló, modelo y de quién era la clave. Sin el lector. Solo lectura en el admin. Las mediciones guardan las respuestas en bruto del modelo. | **hoy** |
| **Prevención de fugas** | El modelo no tiene credenciales ni acceso a la base de datos: solo ve la lista que se le da para esa pregunta, y solo puede contestar con ids de esa lista. Con la clave del lector, el servidor nunca hace la llamada: prepara la lista, comprueba la respuesta en bruto con un token de un solo uso ligado a ese lector, y nada más. | **hoy** |
| **Humano en el bucle** | El bibliotecario recomienda; el lector decide. Cada recomendación separa lo que viene del resumen, con su cita, de lo que viene del conocimiento del modelo, y la página dice cuántas sugerencias se descartaron y por qué. Si nada encaja, lo dice. | **hoy** |

Marco: EU AI Act (2024/1689) · RGPD.

---

## Estructura

```
library/     models · views · librarian (las dos pasadas y sus comprobaciones) · search · embeddings · gemini
             gutenberg (importación) · evaluation · management/commands/ (import_gutenberg · add_nogum · embed_books · evaluate)
             templates/ · static/library/librarian.js (la clave del lector, solo en el navegador) · tests/ (81 pruebas)
eval/        questions.json · questions_hard.json · results/ (cada medición, con las respuestas en bruto)
django_library/  settings (local y Heroku en un fichero) · urls
.github/workflows/tests.yml   las pruebas contra Postgres 17 con pgvector en cada push
```

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
