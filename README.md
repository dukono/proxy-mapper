<img width="1481" height="837" alt="image" src="https://github.com/user-attachments/assets/2be23e3c-53ae-4852-856d-4000b8595f06" />
# Proxy Monitor

Herramienta de interceptación y manipulación de tráfico HTTP/HTTPS con interfaz web en tiempo real.

---

## Arquitectura general

```
Browser / App
     │
     ▼ puerto 8080 (mitmproxy)
┌────────────────┐
│  Proxy Monitor │──► Evalúa perfil activo
└────────────────┘
     │                        │
     ▼ WIRE                   ▼ DEFAULT
Redirige al                Responde con
WireMock externo           mock local
(service_url)              (body del mapping)
```

---

## D1 · Perfiles

El usuario define perfiles de trabajo. Cada perfil determina **qué tipo de mock** se aplica y **dónde están los mappings**.

| Campo | Descripción |
|---|---|
| `name` | Nombre del perfil |
| `root_path` | Directorio raíz donde se ubican los mappings |
| `mapping_type` | `Wire` o `default` |
| `service_url` | Solo para tipo `Wire`: URL del servicio WireMock externo |

Solo un perfil está **activo** a la vez. El perfil activo determina qué reglas se cargan y cómo se evalúan las requests.

---

## D2 · Mappings

Cada perfil tiene su propio conjunto de mappings en disco. El formato del JSON depende del tipo de perfil.

### C1 · Perfil tipo `Wire`

- Estructura de directorios WireMock estándar:
  ```
  root_path/
  ├── mappings/      ← archivos JSON de mappings
  └── __files/       ← archivos de respuesta (bodyFileName)
  ```
- Los JSONs siguen el formato nativo WireMock:
  ```json
  {
    "request": {
      "method": "GET",
      "urlPath": "/v1/api/resource",
      "queryParameters": {
        "id": { "equalTo": "42" }
      }
    },
    "response": {
      "status": 200,
      "bodyFileName": "response.json"
    }
  }
  ```
- Los paths **no incluyen host**, empiezan desde el contexto: `/v1/...`

#### Validación de la request — perfil `Wire`

La comparación se hace **solo sobre el path** (sin host, sin scheme), porque los mappings Wire no tienen host.
Todas las condiciones deben cumplirse simultáneamente (AND lógico).

WireMock define **3 modos de coincidencia de URL**, mutuamente excluyentes (se usa el primero que aparezca en el mapping):

---

##### Modo 1 · Coincidencia Total (`url`)

Compara path **y** query string en un único campo. No se usa `queryParameters`.

```json
"request": {
  "method": "GET",
  "url": "/micacstore/api/v1/users?page=1&size=10"
}
```

| Compara contra | Tipo |
|---|---|
| `path` de la request (sin query) | Igualdad exacta sobre la parte antes de `?` |

```
Mapping:  url=/micacstore/api/v1/users?page=1&size=10
Request:  GET http://localhost/micacstore/api/v1/users?page=1&size=10

  ✅ path  → /micacstore/api/v1/users == /micacstore/api/v1/users
  ✅ (los query params del mapping se ignoran aquí, url es exacta)
  → MATCH
```

> ⚠️ Con `url`, los query params forman parte de la cadena exacta. Si la request tiene parámetros en distinto orden o extras, no coincidirá. Usar `urlPath + queryParameters` es más flexible.

---

##### Modo 2 · Solo la Ruta (`urlPath` + `queryParameters`)

Separa la coincidencia de path y query params en campos independientes.
El path se evalúa por igualdad exacta y cada query param se evalúa por separado.

```json
"request": {
  "method": "GET",
  "urlPath": "/micacstore/api/v1/users",
  "queryParameters": {
    "page": { "equalTo": "1" }
  }
}
```

| Campo | Compara contra | Tipo |
|---|---|---|
| `urlPath` | `path` de la request (sin query) | Igualdad exacta |
| `queryParameters[n]` | Cada query param por separado | `equalTo` / `contains` / `matches` |

| Operador | Ejemplo | Comportamiento |
|---|---|---|
| `equalTo` | `{ "page": { "equalTo": "1" } }` | El parámetro debe ser exactamente `"1"` |
| `contains` | `{ "q": { "contains": "foo" } }` | El parámetro debe contener `"foo"` |
| `matches` | `{ "token": { "matches": "[A-Z]+" } }` | El parámetro debe cumplir la regex |

```
Mapping:  urlPath=/micacstore/api/v1/users  queryParameters: {page: {equalTo:"1"}}  method=GET
Request:  GET http://localhost/micacstore/api/v1/users?page=1&size=10

  ✅ path   → /micacstore/api/v1/users == /micacstore/api/v1/users
  ✅ param  → page="1" == "1"   (size=10 se ignora, no está en el mapping)
  ✅ method → GET == GET
  → MATCH → redirige a service_url preservando path+query originales
```

```
Mapping:  urlPath=/micacstore/api/v1/users  method=GET
Request:  POST http://localhost/micacstore/api/v1/users

  ✅ path   → /micacstore/api/v1/users == /micacstore/api/v1/users
  ❌ method → POST != GET
  → NO MATCH → request sigue su destino original
```

> ✅ Los query params no definidos en `queryParameters` se **ignoran**: la request puede tener más parámetros y seguirá coincidiendo.

---

##### Modo 3 · Patrón (`urlPattern` / `urlPathPattern`)

Usa una **expresión regular** para evaluar la URL. Útil para paths dinámicos (IDs, slugs, etc.).

| Campo | Compara contra | Tipo |
|---|---|---|
| `urlPathPattern` | `path` de la request (sin query) | Regex completa |
| `urlPattern` | `path` de la request (sin query) | Regex (se elimina la parte `\?.*` del patrón antes de comparar) |

```json
"request": {
  "method": "GET",
  "urlPathPattern": "/micacstore/api/v1/users/[0-9]+"
}
```

```
Mapping:  urlPathPattern=/micacstore/api/v1/users/[0-9]+  method=GET
Request:  GET http://localhost/micacstore/api/v1/users/42

  ✅ path   → /micacstore/api/v1/users/42  cumple regex [0-9]+
  ✅ method → GET == GET
  → MATCH → redirige a service_url
```

```
Mapping:  urlPathPattern=/micacstore/api/v1/users/[0-9]+
Request:  GET http://localhost/micacstore/api/v1/users/abc

  ❌ path  → /micacstore/api/v1/users/abc  no cumple [0-9]+
  → NO MATCH
```

> `urlPathPattern` y `urlPattern` pueden combinarse con `queryParameters` igual que `urlPath`.

---

**3. Método HTTP** (`method`) — aplica en los 3 modos. Si no es `ANY`, la request debe coincidir:

```json
"method": "POST"   →   la request debe ser POST
```

---

### C2 · Perfil tipo `default`

- No tiene estructura de directorios fija (solo carpeta `mappings/`)
- Los JSONs usan un formato propio con `matchValue` y `matchType`:
  ```json
  {
    "request": {
      "method": "GET",
      "matchType": "contains",
      "matchValue": "https://api.northflank.com/v1/resource"
    },
    "response": {
      "status": 200,
      "body": "{\"key\": \"value\"}"
    }
  }
  ```
- El `matchValue` **incluye el host completo**: `https://api.northflank.com/v1/...`

#### Validación de la request — perfil `default`

La comparación se hace contra la **URL completa** de la request (scheme + host + path + query).
Todas las condiciones deben cumplirse simultáneamente (AND lógico).

**1. Campo de URL** — definido por `matchType` + `matchValue`:

| `matchType` | Comportamiento | Ejemplo de `matchValue` |
|---|---|---|
| `contains` | La URL contiene el valor | `northflank.com/v1/resource` |
| `equal` | Igualdad exacta con la URL completa | `https://api.northflank.com/v1/resource` |
| `regexp` | Expresión regular sobre la URL completa | `https://api\.northflank\.com/v1/.*` |
| `wildcard` | Patrón con `*` (cualquier secuencia) y `?` (un carácter) | `https://api.northflank.com/v1/*` |
| `startsWith` | La URL empieza con el valor | `https://api.northflank.com` |
| `endsWith` | La URL termina con el valor | `/resource` |

**2. Método HTTP** (`method`) — si está definido y no es `ANY`:

```json
"method": "POST"   →   la request debe ser POST
```

**3. Body** (`bodyMatch`, `bodyMatchType`, `bodyMatchValue`) — opcional, para POST/PUT:

| `bodyMatchType` | Comportamiento |
|---|---|
| `contains` | El body contiene el valor |
| `equal` | El body es exactamente el valor |
| `regexp` | El body cumple la expresión regular |

**Ejemplo completo de validación default:**
```
Mapping:   matchType=contains  matchValue=northflank.com/v1/projects  method=GET
Request:   GET https://api.northflank.com/v1/projects?page=1

  ✅ url    → "https://api.northflank.com/v1/projects?page=1" contiene "northflank.com/v1/projects"
  ✅ method → GET == GET
  → MATCH → responde localmente con el body del mapping
```

```
Mapping:   matchType=equal  matchValue=https://api.northflank.com/v1/projects  method=GET
Request:   GET https://api.northflank.com/v1/projects?page=1

  ❌ url    → "https://api.northflank.com/v1/projects?page=1" != "https://api.northflank.com/v1/projects"
  → NO MATCH → request sigue su destino original
```

---

## D3 · Cómo se aplica el mapping a la request

Cuando llega una request al proxy, se comprueba si corresponde a algún mapping del **perfil activo**.

### Perfil `Wire` — comparación sobre el PATH (sin host)

Los mappings Wire no tienen host, por lo que la comparación se hace **solo sobre el path**:

| Campo en el mapping | Tipo de match |
|---|---|
| `urlPath` | Igualdad exacta sobre el path |
| `urlPathPattern` | Regex sobre el path |
| `urlPattern` | Regex sobre el path (sin query string) |
| `url` | Igualdad exacta sobre el path (sin query string) |
| `queryParameters` | Verificación por cada parámetro (`equalTo`, `contains`, `matches`) |
| `method` | Igualdad exacta sobre el método HTTP |

> ✅ Ejemplo: request a `http://localhost/micacstore/api/v1/users`
> → se compara solo `/micacstore/api/v1/users` contra `urlPath`

### Perfil `default` — comparación sobre la URL completa (con host)

Los mappings default incluyen el host, por lo que la comparación se hace contra la **URL completa**:

| `matchType` | Comportamiento |
|---|---|
| `contains` | La URL contiene el valor |
| `equal` | Igualdad exacta con la URL completa |
| `regexp` | Expresión regular |
| `wildcard` | Patrón con `*` y `?` |
| `startsWith` | La URL empieza con el valor |
| `endsWith` | La URL termina con el valor |

> ✅ Ejemplo: request a `https://api.northflank.com/v1/users`
> → se compara la URL completa contra `matchValue: "https://api.northflank.com/v1/users"`

---

## D4 · Qué ocurre si el mapping coincide

### F1 · Perfil `Wire` + mapping coincide → **REDIRECT**

La request se **redirige** al servicio WireMock externo (`service_url`), preservando el path y query string originales:

```
Request original:  GET http://localhost/v1/api/resource?id=1
         ↓ match
Redirigida a:      GET http://localhost:31310/v1/api/resource?id=1
                   (WireMock externo evalúa y responde)
```

Si **no coincide** con ningún mapping → la request se reenvía a su **destino original**.

### F2 · Perfil `default` + mapping coincide → **MOCK local**

El proxy responde directamente con el body y status definidos en el mapping, **sin llegar al servidor real**:

```
Request:  GET https://api.northflank.com/v1/resource
         ↓ match
Response: 200 {"key": "value"}   ← respondido por el proxy localmente
```

Si **no coincide** con ningún mapping → la request se reenvía a su **destino original**.

---

## Inicio rápido

### 1. Dependencias del sistema (Linux)

Requeridas para que la ventana nativa funcione con Qt:

```bash
sudo apt-get install -y libxcb-cursor0
```

> **Nota:** El módulo Python `gi` (GTK) no es necesario — la app usa el backend Qt.

### 2. Dependencias Python

```bash
cd proxy_app
pip install -r requirements.txt
```

### 3. Arrancar

```bash
python main.py
```

La aplicación se abre como **ventana de escritorio nativa** (sin necesidad de navegador).

- **Proxy**: `localhost:8080` — configura tu app o sistema para usarlo
- **UI**: `http://localhost:8081` — también accesible desde el navegador si se prefiere

---

## Dependencias

### Python

| Librería | Uso |
|---|---|
| `mitmproxy` | Motor de interceptación HTTP/HTTPS |
| `nicegui` | Interfaz web en tiempo real |
| `pydantic` | Modelos de datos |
| `pywebview` | Ventana de escritorio nativa |
| `PyQt6` | Backend Qt para pywebview |
| `PyQt6-WebEngine` | Motor de renderizado web Qt (requerido por pywebview) |
| `qtpy` | Capa de abstracción Qt |

### Sistema (Linux/Ubuntu)

| Paquete | Motivo |
|---|---|
| `libxcb-cursor0` | Plugin de plataforma Qt xcb (requerido desde Qt 6.5) |
