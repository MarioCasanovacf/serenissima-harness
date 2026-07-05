# Prompt para el Claude del portafolio de Mario

> Copia todo lo que sigue y pégalo en una sesión de Claude Code abierta en la carpeta del
> portafolio. Ese Claude conoce el tono de Mario; este documento le da el material técnico.

---

Hola. Trabajas en mi portafolio y conoces mi voz. Necesito que produzcas la documentación
de publicación del **Universal Agent Harness**, un proyecto que construí en
`~/Documents/Universal Harness` y que voy a subir a GitHub y Hugging Face para devolverle
algo a la comunidad de Claude Code.

**Material fuente (léelo en este orden):**
1. `~/Documents/Universal Harness/docs/README-publication-draft.md` — la base técnica en
   inglés, escrita por el coordinador que construyó el harness. Los HECHOS de ahí son
   verificados y no deben cambiarse; la VOZ es tuya.
2. `~/Documents/Universal Harness/USAGE.md` — la guía de operador (así se usa de verdad).
3. `~/Documents/Universal Harness/docs/harness-explainer.html` — el explicador de
   componentes en español (así se explica a un humano).
4. `~/Documents/Universal Harness/ORCHESTRATION.md` — el contrato de topología (la
   filosofía de diseño).

**Entregables:**
1. **README.md final para GitHub** (inglés): parte del draft, re-escríbelo en mi tono —
   directo, honesto, sin hype, con humor seco donde quepa. Conserva TODAS las afirmaciones
   verificables tal cual (números de tests, generaciones, el registro de dogfood) — nada
   de inflar. La sección de licencia: pregúntame antes de elegir.
2. **Model/Dataset card para Hugging Face** (inglés): formato card estándar; el harness no
   es un modelo, así que va como espacio/dataset de recursos — enfócala en "qué descargas
   y qué haces con ello en 10 minutos".
3. **Post de anuncio corto** (uno en inglés, uno en español) para redes: 3-5 párrafos,
   mi voz, terminando con el link al repo. La historia es: "le pedí a Claude que
   construyera un sistema para coordinar Claudes; se construyó, se auditó y se corrigió a
   sí mismo cuatro generaciones; esto es lo que salió y lo puedes usar hoy".

**Reglas:**
- Nada se publica desde tu sesión: entregas archivos en `docs/publicacion/` dentro del
  portafolio y Mario los revisa y los mueve.
- Si un hecho técnico del draft te parece dudoso, NO lo suavices ni lo corrijas: márcalo
  con `[VERIFICAR: ...]` y sigue. El harness tiene su propio ciclo de verificación.
- El crédito de inspiración a Thariq Shihipar (framework de unknowns) se queda.
- Menciona honestamente lo que NO hace: no es un framework de agentes ni reemplaza a
  Claude Code; es un sustrato de coordinación encima de él. La sesión headless multi-LLM
  quedó fuera del alcance probado (está documentado el porqué).
