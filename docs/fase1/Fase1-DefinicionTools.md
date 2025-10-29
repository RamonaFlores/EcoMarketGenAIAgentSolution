# Fase 1: Definición de Tools para el AI Agent de Devoluciones

## 🎯 Objetivo del Proyecto

El objetivo de nuestro agent es **automatizar el proceso de devolución de productos**:
- Entender la solicitud del cliente
- Verificar la elegibilidad de devolución
- Generar una etiqueta de devolución

Todas estas acciones están fundamentadas por las políticas e información de la compañía recuperadas por el **RAG (Retrieval-Augmented Generation)** implementado en Pinecone.

## 📋 Metodología de Diseño

Lo primero que haremos será darle una **definición más formal** a las tools que necesitaremos para que nuestro agent pueda realizar su labor correctamente.

### Principios Fundamentales

Es importante que las tools tengan:
- ✅ **Contratos claros** - Especificaciones precisas de entrada y salida
- ✅ **Validaciones robustas** - Manejo de casos edge y errores
- ✅ **Errores esperables** - Códigos de error bien definidos
- ✅ **Idempotencia** - Comportamiento predecible en llamadas repetidas
- ✅ **Ejemplos prácticos** - Casos de uso reales documentados

### 💡 Filosofía de Diseño: "Pensar como un Robot"

En estos días vi un video de Anthropic que hablaba de un error muy común que cometemos como ingenieros al desarrollar AI agents: **PENSAR COMO HUMANO** 

Suena raro, ¿no? Pero tiene mucho sentido. Imagínate que eres un robot y tu contexto se limita a 4 renglones que te entregaron mal escritos en un papel, y aparte te dieron un baúl con un montón de herramientas cuyas instrucciones se limitan a decir "úsame".

Para crear agents que funcionen de verdad necesitamos **pensar como uno**, ser conscientes de qué necesitaríamos para cumplir una tarea. Si a ti no se te hace suficiente, para el agente tampoco lo será.

---

## 🛠️ Definición de Tools

### 1. 🔍 `rag_search` - Búsqueda de Información Corporativa

**Propósito:** Traer fragmentos relevantes (texto + metadatos) desde nuestra base de datos vectorial para que el agente cite evidencia propia de la compañía y no alucine.

#### 📥 Input Schema
```json
{
  "query": "string (obligatorio)",
  "k": "integer (1..12, default=5)",
  "doc_type_filter": "string|null (ej: 'policy' o 'faq')"
}
```

#### 📤 Output Schema
```json
{
  "query": "string",
  "k": "integer",
  "snippets": [
    {
      "text": "string (≤ ~1600 chars)",
      "doc_type": "policy|faq|inventory|other",
      "source": "string (ej: 'devoluciones.pdf')",
      "last_updated": "YYYY-MM-DD|null",
      "score": "float (similitud)"
    }
  ]
}
```

#### ⚠️ Validaciones y Errores Esperables
- **Query vacío** → `error: "empty_query"`
- **Índice/namespace inválidos** → `error: "index_unavailable"`
- **Sin matches** → `snippets: []` (el agent debe pedir datos o escalarlo a un especialista)

#### 🔄 Idempotencia / Efectos
- **Sin efectos secundarios** - Puro retrieval
- **Operación de solo lectura**

#### 💡 Ejemplo de Uso

**Request:**
```json
{
  "query": "devoluciones 30 días productos defectuosos",
  "k": 6,
  "doc_type_filter": "policy"
}
```

**Response:**
```json
{
  "query": "devoluciones 30 días productos defectuosos",
  "k": 6,
  "snippets": [
    {
      "text": "POLÍTICA ... 30 días ... garantía 1 año ...",
      "doc_type": "policy",
      "source": "devoluciones.pdf",
      "last_updated": "2025-10-10",
      "score": 0.81
    },
    {
      "text": "P: ¿Puedo cancelar mi pedido? R: ...",
      "doc_type": "faq",
      "source": "faqs.json",
      "last_updated": "2025-10-12",
      "score": 0.63
    }
  ]
}
```


### 2. 📦 `get_order_info` - Obtener Información del Pedido

**Propósito:** Obtener datos del pedido (fecha, ítems, estado) y tener evidencia transaccional para la verificación:
- Fecha de compra (para verificar la ventana de tiempo)
- Categoría y SKU del producto
- Estado actual del pedido

#### 📥 Input Schema
```json
{
  "order_id": "string (obligatorio)"
}
```

#### 📤 Output Schema
```json
{
  "found": "boolean",
  "customer_name": "string",
  "purchase_date": "YYYY-MM-DD",
  "status": "delivered|shipped|preparing|cancelled|other",
  "items": [
    {
      "sku": "string",
      "name": "string",
      "category": "string"
    }
  ],
  "error": "string|null"
}
```

#### ⚠️ Validaciones y Errores Esperables
- **Order_id inválido o no encontrado** → `found: false, error: "order_not_found"`
- **Pedido sin ítems** → `found: true` pero `items: []` (el agente debe pedir producto específico)

#### 🔄 Idempotencia / Efectos
- **Sin efectos secundarios** (read-only)
- **Operación de solo lectura**

#### 💡 Ejemplo de Uso

**Request:**
```json
{
  "order_id": "EC-1001"
}
```

**Response:**
```json
{
  "found": true,
  "customer_name": "Laura",
  "purchase_date": "2025-10-02",
  "status": "delivered",
  "items": [
    {
      "sku": "ECO-SOAP-500",
      "name": "Jabón biodegradable 500 ml",
      "category": "higiene"
    }
  ],
  "error": null
}
```

### 3. ✅ `check_eligibility` - Verificar Elegibilidad de Devolución

**Propósito:** Aplicar reglas del negocio usando evidencia recuperada con el RAG + los datos del pedido:

- **Ventana de tiempo** (30 días o la que digan las políticas vigentes recuperadas)
- **Categorías no retornables** (perecederos, higiene personal abiertos, personalizados, plantas vivas después de 48 horas, etc.)
- **Excepción por defecto de fábrica** (permitir garantía devolución)

#### 📥 Input Schema

```json
{
  "purchase_date": "YYYY-MM-DD (obligatorio)",
  "product_category": "string (obligatorio)",
  "product_condition": "sealed|opened|defective (obligatorio)",
  "policy_snippets": ["string", "..."]  // textos recuperados por rag_search
}
```

#### 📤 Output Schema
```json
{
  "eligible": "boolean",
  "reason": "string (explica por qué sí/no)",
  "days_elapsed": "integer",
  "window_days": "integer",
  "policy_refs": ["string", "..."]  // opc: nombres de fuentes
}
```

#### ⚠️ Validaciones y Errores Esperables
- **Fecha inválida** → `error: "bad_purchase_date"`
- **Product_category faltante** → `error: "missing_product_category"`
- **Policy_snippets vacío** → se asume ventana por defecto (30 días)

#### 🔄 Idempotencia / Efectos
- **Solo cálculos** - No hay efectos persistentes
- **Operación de procesamiento puro**

#### 💡 Ejemplos de Uso
**Caso 1: Producto defectuoso, dentro de ventana**

**Request:**
```json
{
  "purchase_date": "2025-10-05",
  "product_category": "higiene",
  "product_condition": "defective",
  "policy_snippets": ["POLÍTICA: devoluciones 30 días ... garantía 1 año ..."]
}
```

**Response:**
```json
{
  "eligible": true,
  "reason": "cumple políticas",
  "days_elapsed": 12,
  "window_days": 30,
  "policy_refs": ["devoluciones.pdf (2025-10-10)"]
}
```



**Caso 2: Producto abierto, higiene personal, no defectuoso**

**Request:**
```json
{
  "purchase_date": "2025-09-20",
  "product_category": "higiene",
  "product_condition": "opened",
  "policy_snippets": ["No se aceptan devoluciones de higiene personal abiertos ..."]
}
```

**Response:**
```json
{
  "eligible": false,
  "reason": "categoría no retornable: higiene personal abiertos",
  "days_elapsed": 38,
  "window_days": 30,
  "policy_refs": ["devoluciones.pdf (2025-10-10)"]
}
```

### 4. 🏷️ `generate_return_label` - Generar Etiqueta de Devolución

**Propósito:** Emitir RMA/Label con URL y plazo de entrega, para que el cliente complete la devolución

#### 📥 Input Schema
```json
{
  "order_id": "string (obligatorio)",
  "product_sku": "string (obligatorio)"
}
```

#### 📤 Output Schema
```json
{
  "label_id": "string (RMA)",
  "label_url": "string (http/https)",
  "order_id": "string",
  "product_sku": "string",
  "deadline_days": 7,
  "dropoff_locator": "https://ecomarket.com/puntos",
  "created_at": "ISO-8601 UTC"
}
```

#### ⚠️ Validaciones y Errores Esperables
- **Pedido no elegible o faltan datos** → `error: "not_eligible_or_missing_data"`
- **Product_sku no pertenece al pedido** → `error: "sku_mismatch"` (si implementamos la verificación)

#### 🔄 Idempotencia / Efectos
- **Debe ser idempotente** por `(order_id, product_sku)`: si ya existe etiqueta activa para ese par, devuelve la misma
- **Implementa un lookup previo** o una clave de idempotencia para evitar múltiples etiquetas

#### 💡 Ejemplo de Uso

**Request:**
```json
{
  "order_id": "EC-1001",
  "product_sku": "ECO-SOAP-500"
}
```

**Response:**
```json
{
  "label_id": "RLB-8F2C1D9A55",
  "label_url": "https://ecomarket.com/return/label/RLB-8F2C1D9A55",
  "order_id": "EC-1001",
  "product_sku": "ECO-SOAP-500",
  "deadline_days": 7,
  "dropoff_locator": "https://ecomarket.com/puntos",
  "created_at": "2025-10-28T23:10:05Z"
}
```




---

## 🔄 Flujo de Trabajo del AI Agent

### Proceso Paso a Paso

1. **🔍 Detección de Intención**
   - El LLM detecta intención de devolución del cliente
   - Llama a `rag_search(query, doc_type_filter="policy")` → obtiene fragmentos (ventana, exclusiones, garantías)

2. **📦 Verificación del Pedido**
   - Llama a `get_order_info(order_id)` → obtiene `purchase_date`, `items[0].category/sku`

3. **✅ Evaluación de Elegibilidad**
   - Llama a `check_eligibility(purchase_date, product_category, product_condition, policy_snippets)`
   - Si `eligible=false` → el LLM responde empático + alternativas + citas (de `rag_search`)

4. **🏷️ Generación de Etiqueta (si procede)**
   - Llama a `generate_return_label(order_id, product_sku)` → devuelve URL + RMA + plazo

5. **💬 Respuesta Final del Agente**
   - Redacta pasos claros y cita fuentes (`source` + `last_updated`) provenientes de `rag_search`

### 🎯 Beneficios del Diseño

- **Trazabilidad completa**: Cada decisión está respaldada por evidencia corporativa
- **Consistencia**: Mismas reglas aplicadas a todos los casos
- **Transparencia**: Cliente puede ver las fuentes de las políticas
- **Escalabilidad**: Fácil agregar nuevas reglas o herramientas
- **Mantenibilidad**: Cambios en políticas se reflejan automáticamente