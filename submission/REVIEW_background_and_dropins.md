# Revisión del paquete de submission — refuerzo del background

**Qué revisé:** `DEMO_SCRIPT_3min.md`, `NARRATION_wordforword.md`, `SUMMARY_100-200w.md`,
`one_pager.html`, `README.md`, y los resultados Task A/B/C. **Veredicto:** el material comunica
el *método* de forma excelente (el argumento de "sesgo eliminado" + convergencia de 3 métodos es
un gancho de primer nivel). Lo que le falta es el **por qué** — el contexto que hace que un juez
que no conoce OPLAH entienda por qué esto importa en los primeros 20 segundos.

---

## Los 5 huecos de background (en orden de impacto)

### 1. No se menciona la enfermedad. (el hueco más grave)
La palabra "insuficiencia cardíaca" / "heart failure" no aparece en NINGÚN archivo del submission.
OPLAH se presenta como "una enzima humana activada por AMP" — abstracto, sin apuestas.

**El contexto real (publicado):**
- OPLAH (5-oxoprolinasa) es parte del ciclo γ-glutamil (glutatión); convierte 5-oxoprolina en glutamato.
- Tras daño cardíaco, OPLAH se reprime → se acumula 5-oxoprolina → aumenta el estrés oxidativo (ROS).
- La ablación de OPLAH lleva a acumulación de 5-oxoprolina, estrés oxidativo, fibrosis y presiones
  de llenado elevadas — descrito como un modelo murino de HFpEF (insuficiencia cardíaca con fracción
  de eyección preservada). OPLAH tiene, por tanto, un efecto protector, y **potenciar su actividad es
  una estrategia terapéutica** para condiciones de estrés oxidativo.

Fuentes (verificar cita exacta antes de publicar): "Accumulation of 5-oxoproline in myocardial
dysfunction and the protective effects of OPLAH" (*Sci Transl Med* 2017, aam8574); "OPLAH ablation
leads to accumulation of 5-oxoproline, oxidative stress, fibrosis and elevated filling pressures: a
murine model for HFpEF" (*Cardiovasc Res* 2018); "Heart failure and the glutathione cycle" (*Biochem
J*); y tu artículo de referencia (*Adv Ther* 2025, 10.1002/adtp.202500263).
**Nota:** confirma nombres de autor y números de acceso directamente en cada paper — no los des por
buenos de esta nota.

### 2. No se explica de dónde salió 5-AMP ni por qué es interesante.
5-AMP no es un ligando cualquiera: es el hallazgo del trabajo previo del equipo. Fue identificado
como **activador de OPLAH** (no inhibidor) cribando una **librería de fármacos aprobados por la FDA**,
confirmado por thermal shift assay y activación dosis-dependiente por LC-MS/MS. Un *activador*
enzimático es farmacológicamente raro y valioso — y explica por qué solo se conoce UN modulador,
que es justo la premisa del pipeline. Añadir esto convierte "un compuesto misterioso" en "un lead
validado con una historia".

### 3. No se vende la generalización — el objetivo declarado del proyecto.
Meta del proyecto: *"una forma estándar de avanzar cuando la cristalografía/estructura 3D no está
resuelta y solo conoces al menos una molécula pequeña que modula el target."* Eso es una
**plataforma reutilizable**, no un estudio de OPLAH. El submission dice "modular structure-to-screen
pipeline" pero no lo enmarca como el producto. OPLAH debe presentarse como el **caso de prueba**
de un método que aplica a cualquier target huérfano-de-estructura con un modulador conocido.

### 4. Falta el "por qué ahora / por qué IA".
El cuello de botella clásico: sin estructura cristalográfica, el diseño racional se detiene. Lo que
lo destraba ahora es AlphaFold (estructura predicha de longitud completa) + detección de pockets +
docking, orquestado end-to-end por Claude Code. Enmarcar esto da la narrativa "IA que desbloquea
un target intratable".

### 5. La pregunta 6 (activador vs inhibidor) se descarta como "fuera de alcance".
Dado que el hallazgo original es que 5-AMP *activa*, reformúlala como **trabajo futuro dirigido**
(ensayo funcional / cinética enzimática), no como un hueco. Suena a hoja de ruta, no a limitación.

---

## Texto listo para pegar

### A) Nueva Escena 1 de la narración (reemplaza el "Title" actual)
> "La insuficiencia cardíaca reprime una enzima protectora llamada **OPLAH**. Cuando OPLAH cae, se
> acumula 5-oxoprolina, se dispara el estrés oxidativo, y los pacientes empeoran. Así que
> potenciar OPLAH es una estrategia terapéutica real — y ya existe una pista: la molécula **5-AMP**,
> descubierta en un cribado de fármacos aprobados, la **activa**. El problema: OPLAH no tiene
> estructura resuelta, y nadie sabe **dónde** se une AMP. Nos propusimos encontrar ese sitio —
> **sin hacer trampa**."

*(~70 palabras / ~35 s. Si necesitas mantener 2:48, recorta la Escena 3 en una frase — el gancho
clínico vale más que un segundo detalle de convergencia.)*

### B) Nueva Escena 2 — añade la frase de generalización al final
> "…entonces quitamos la suposición: detectar **todos** los pockets en toda la proteína, y dejar
> que AMP elija su propio sitio. Y como el método no asume nada del target, **sirve para cualquier
> proteína sin estructura de la que solo conozcas un modulador** — OPLAH es solo nuestro primer caso."

### C) Nuevo primer párrafo del SUMMARY (reemplaza el arranque)
> La insuficiencia cardíaca reprime la 5-oxoprolinasa (OPLAH), una enzima del ciclo del glutatión;
> su caída acumula 5-oxoprolina y estrés oxidativo (un modelo murino de HFpEF). Potenciar OPLAH
> es, por tanto, una diana terapéutica — y un cribado previo de
> fármacos aprobados identificó a la **5-AMP como activador** de OPLAH. Pero OPLAH no tiene
> estructura resuelta ni sitio de unión conocido: el diseño racional se detiene aquí. Construimos
> un pipeline modular "structure-to-screen" con Claude Code que convierte *cualquier* target sin
> estructura + un modulador conocido en una lista corta de cribado — y elimina un sesgo oculto…
> [continúa con el texto actual desde "The naive approach transplants…"]

### D) One-pager — nueva banda de contexto (insertar ANTES de la banda "The bias we removed")
Añadir una tarjeta/banda breve titulada **"Why OPLAH"**:
> **Por qué OPLAH.** La insuficiencia cardíaca reprime OPLAH → se acumula 5-oxoprolina → estrés
> oxidativo (modelo murino de HFpEF). Un cribado de fármacos
> aprobados halló que **5-AMP activa OPLAH**. Pero no hay estructura ni sitio conocido — así que
> no se puede optimizar el lead. Ahí empieza este pipeline.

### E) README — nuevo bloque "Why this target" (tras el blockquote "The question")
Añadir 3 frases de contexto clínico + la procedencia de 5-AMP (activador de un cribado FDA) antes
de saltar a la metodología. Reutilizar el texto de (C)/(D).

---

## Retoques menores (rápidos, alto retorno)
- **Título del proyecto:** el actual ("finding where a modulator binds…") es sobre método. Considera
  un subtítulo que nombre la enfermedad: *"…un pipeline de IA para targets sin estructura — caso:
  OPLAH e insuficiencia cardíaca."*
- **Scoreboard de 5 preguntas:** añade una 6ª fila "activador vs inhibidor → **trabajo futuro:
  ensayo funcional**" en gris, para que se lea como hoja de ruta, no como omisión.
- **Consistencia de una cifra:** el README dice modelo AlphaFold "full 1288 aa" en un sitio y
  "1,288-residue" y el SUMMARY dice "1,288-residue"; Task A menciona residuos hasta 1288. OK. Pero
  el SUMMARY dice "full 1,288-residue AlphaFold model" mientras la narración dice detección sobre
  "the whole protein" — alinear a "1288 aa" en todas partes para que la cifra quede grabada.
- **Menciona "activador" explícitamente** al hablar de 5-AMP (no solo "activated by / enhances"):
  es un diferenciador farmacológico.

## Chequeo de precisión (no sobrevender)
- 5-AMP como activador y su origen en cribado FDA: correcto según el paper de referencia.
- Vínculo OPLAH–insuficiencia cardíaca / acumulación de 5-oxoprolina: publicado (STM 2017, Cardiovasc Res 2018) — confirma la cita exacta en el paper.
- Mantén el marco de "hipótesis, no afinidades" del docking que ya está en Task C — es honesto y suma credibilidad.
