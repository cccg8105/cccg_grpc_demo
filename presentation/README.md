# Presentación gRPC — rpc_demo

Presentación didáctica en **Quarto + reveal.js** con navegación vertical: hilo principal (→) y profundizaciones (↓).

**Autor:** César Cárdenas  
**Título:** *Cuando los datos deben fluir entre servicios* — De cubetas a cañería, con demo en vivo

## Narrativa

Metáfora central: un **flujo de datos** (líquido) que atraviesa **estaciones** de procesamiento.

| Enfoque | Metáfora | En la demo |
|---------|----------|------------|
| Tradicional | **Cubeta** — todo de una vez | Carga completa en memoria |
| REST | **Envases** — porciones coordinadas | Browser: lotes `GET` + `POST` |
| gRPC | **Cañería** — flujo continuo | Stream Ingest → Transform |

## Requisitos

- [Quarto](https://quarto.org/docs/get-started/) 1.4+
- Python 3.11+ con Playwright (verificación visual)

```bash
pip install playwright
playwright install chromium
```

## Renderizar

```bash
quarto render presentation/grpc-intro.qmd
python scripts/patch_presentation_html.py
# o
make presentation
```

Salida: [`grpc-intro.html`](grpc-intro.html)

## Navegación en vivo

| Tecla | Acción |
|-------|--------|
| **→ / ←** | Hilo principal |
| **↓ / ↑** | Profundizaciones |
| **F** | Pantalla completa |
| **S** | Vista del presentador |

## Verificación visual

```bash
make presentation-verify
# o
python scripts/capture_presentation_slides.py --iter 1
```

## Estructura

| Hilo principal | Ramas ↓ |
|----------------|---------|
| Flujo por estaciones, gRPC, REST vs gRPC | RPC técnico, plano `.proto` |
| Beneficios, cuándo usar, demo | Medidor vs tubería, secuencia, envases vs cañería |
| Demo en vivo, takeaways | Glosario, recursos |

## Fuentes

- [`docs/GUIA_DIDACTICA.md`](../docs/GUIA_DIDACTICA.md)
- [`README.md`](../README.md)
