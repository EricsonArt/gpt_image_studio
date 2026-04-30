# GPT Image Studio

Higgsfield-style generator obrazów oparty na **OpenAI gpt-image-2**.

## Funkcje

- 🎨 **Quality**: low / medium / high
- 📐 **Rozdzielczość**: 1K / 2K / **4K** (przez Real-ESRGAN AI upscale)
- 🖼️ **Aspect ratio**: 1:1, 16:9, 9:16, 4:3, 3:4
- 🔢 **Batch size**: 1–10 obrazów na 1 klik
- 🖼️ **Obrazy referencyjne** (Higgsfield-style multi-image input)
- ✏️ **Edit / Inpainting** istniejących obrazów
- 📚 **Historia** wszystkich generacji + reuse promptów
- 💰 **Live cost preview** przed generacją
- 📝 **Metadane JSON** zapisywane obok każdego obrazu

## Setup

1. **Wirtualne środowisko (zalecane):**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Zależności:**
   ```cmd
   pip install -r requirements.txt
   ```

3. **Klucze API:**
   ```cmd
   copy .env.example .env
   ```
   Otwórz `.env` i wpisz:
   - `OPENAI_API_KEY` — wymagane
   - `REPLICATE_API_TOKEN` — opcjonalne (potrzebne do prawdziwego AI 4K; bez niego 4K idzie przez Pillow Lanczos)

4. **Uruchom:**
   ```cmd
   start.bat
   ```
   lub:
   ```cmd
   streamlit run app.py
   ```

## Jak to działa

- **1K / 2K** — generujemy natywnie przez `gpt-image-2`
- **4K** — generujemy 2K natywnie, potem upscale 2× przez Real-ESRGAN (Replicate)
- **Reference images** — używamy endpointu `/v1/images/edits` z multi-image input
- **Inpainting** — `/v1/images/edits` z opcjonalną maską PNG (przezroczyste obszary = przemalować)

## Outputy

Każda generacja ląduje w `outputs/<timestamp>_<prompt>_<hash>/`:
- `image_1.png`, `image_2.png`, ...
- `image_1.json`, `image_2.json`, ... — metadane (prompt, params, koszt, czas)

## Cennik (przybliżony)

| Quality | 1K (1024²) | 2K (2048²) |
|---------|-----------|-----------|
| low     | ~$0.011   | ~$0.022   |
| medium  | ~$0.042   | ~$0.084   |
| high    | ~$0.167   | ~$0.250   |

4K = cena 2K + ~$0.002 za upscale.

UI pokazuje **live cost preview** przed kliknięciem Generate.
