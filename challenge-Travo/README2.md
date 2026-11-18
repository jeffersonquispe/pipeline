Viewed README2.md



---

### 1. ¿Por qué diseñar los nodos como CLIs independientes en lugar de clases/funciones dentro del orquestador?
Para asilamiento de errores y poder reutilizar en otro orquestador. No depende de un solo codigo unificado y puedo escalarlo como arquitectura de microservicios o hexagonal

---

### 2. ¿Cómo decidiste manejar el estado entre nodos? ¿Qué alternativas consideraste?
* **Decisión adoptada:** El estado viaja a través de contratos inmutables de JSON que fluyen por `stdin/stdout`. El orquestador se encarga de recibir el resultado de un nodo y inyectarlo como entrada al siguiente. El estado global del pipeline se consolida en un `PipelineStore` en memoria protegido con bloqueos de concurrencia.
* **Alternativas consideradas y descartadas:**
  1. Con ase de datos relacional tradicional ya que es excelente para persistencia a largo plazo, pero añade sobrecarga y latencia para un prototipo enfocado en evaluar la arquitectura en tiempo real.
  2. Usar langgraph Descartado porque introduce riesgos de carreras de datos, es limitdo para otro tipo de arquitectura y acopla fuertemente el estado de los nodos con el del orquestador.

---

### 3. ¿Dónde pusiste el semáforo y por qué ahí específicamente?
El semáforo global (`MAX_LLM_CALLS = 10`) se colocó en **`worker.py`**, protegiendo exclusivamente a los nodos que hacen llamadas a las APIs de IA (`planner`, `codegen`, `reviewer`). ya que protege la API a nivel de llamada unitaria de LLM en lugar de bloquear todo el pipeline. Si un pipeline está en la fase local de `validator` o `delivery` (que no consumen tokens), libera su ranura de semáforo inmediatamente.


---

### 4. Si el loop de auto-corrección falla 3 veces seguidas con el mismo tipo de error, ¿qué le agregarías al sistema?
Le agregaría una estrategia de escalamiento con Intervención Humana. Si tras el tercer reintento el tipo de error es idéntico, se pausa el pipeline temporalmente cambiándolo al estado y se dispara un webhook a Slack/Discord con el contexto. Un desarrollador humano puede corregir la línea.
---

### 5. ¿Qué cambiarías si esto tuviera que escalar a 500 pipelines concurrentes?
Para pasar de una arquitectura monolítica local a escala empresarial masiva, cambiaría los siguientes componentes clave como desacoplar el orquestador de la ejecución. El orquestador solo recibe la petición HTTP y la encola. Los trabajadores independientes (en pods de K8s escalables o imagenes Docker como microservicios) procesan las tareas consumiendo de la cola distribuida.
Tambíen podría reemplazar el semáforo en memoria por un semáforo centralizado distribuido en **Redis** para asegurar que el límite de rate-limiting se cumpla a lo largo de todo el cluster de servidores.