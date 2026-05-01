"""GPT Image Studio - Streamlit UI.

Higgsfield-style generator obrazów oparty na gpt-image-2.
"""

# Wymuszamy UTF-8 wszędzie przed importem czegokolwiek
import os
import sys
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    elif hasattr(_s, "buffer"):
        try:
            import io as _io
            _wrapped = _io.TextIOWrapper(_s.buffer, encoding="utf-8", errors="replace")
            if _s is sys.stdout:
                sys.stdout = _wrapped
            else:
                sys.stderr = _wrapped
        except Exception:
            pass

import io
import time
from pathlib import Path

import streamlit as st
from PIL import Image

import config
from modules import cost_calculator, history, image_generator, upscaler


def _save_keys_to_env(openai_key: str, replicate_key: str):
    """Zapisuje klucze do .env żeby przetrwały odświeżenie strony."""
    env_path = config.ROOT_DIR / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    def _set_var(lines, name, value):
        prefix = f"{name}="
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                if value:
                    lines[i] = f"{prefix}{value}"
                return
        if value:
            lines.append(f"{prefix}{value}")

    _set_var(lines, "OPENAI_API_KEY", openai_key)
    _set_var(lines, "REPLICATE_API_TOKEN", replicate_key)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Przeładuj env vars w tym procesie
    import dotenv
    dotenv.load_dotenv(env_path, override=True)

st.set_page_config(
    page_title="GPT Image Studio",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Session state ----------
def _init_session():
    """Inicjalizuje session_state, wczytując klucze z .env przy pierwszym uruchomieniu."""
    if "session_initialized" not in st.session_state:
        st.session_state.session_initialized = True
        # Pre-fill kluczy z .env / Streamlit secrets przy starcie sesji
        for key in ("OPENAI_API_KEY", "REPLICATE_API_TOKEN"):
            if key not in st.session_state:
                val = config.get_secret(key)
                if val:
                    st.session_state[key] = val
    defaults = {"prompt": "", "negative_prompt": "", "last_results": [], "edit_image": None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()


# ---------- Sidebar ----------
def render_sidebar():
    st.sidebar.title("⚙️ Ustawienia")

    # Klucze API
    with st.sidebar.expander("🔑 Klucze API", expanded=not config.get_secret("OPENAI_API_KEY")):
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.get("OPENAI_API_KEY", ""),
            placeholder="sk-...",
        )
        replicate_key = st.text_input(
            "Replicate Token (opc., dla 4K)",
            type="password",
            value=st.session_state.get("REPLICATE_API_TOKEN", ""),
            placeholder="r8_...",
        )
        if st.button("💾 Zapisz klucze", use_container_width=True, key="save_keys"):
            _save_keys_to_env(openai_key, replicate_key)
            if openai_key:
                st.session_state["OPENAI_API_KEY"] = openai_key
            if replicate_key:
                st.session_state["REPLICATE_API_TOKEN"] = replicate_key
            st.success("✅ Klucze zapisane — nie musisz ich więcej wpisywać!")
            st.rerun()
        else:
            if openai_key:
                st.session_state["OPENAI_API_KEY"] = openai_key
            if replicate_key:
                st.session_state["REPLICATE_API_TOKEN"] = replicate_key

    # Status
    has_openai = bool(config.get_secret("OPENAI_API_KEY"))
    has_replicate = upscaler.has_replicate()
    st.sidebar.markdown("**Status API:**")
    st.sidebar.markdown(
        f"- OpenAI: {'✅' if has_openai else '❌ wpisz klucz wyżej'}"
    )
    st.sidebar.markdown(
        f"- Replicate (4K upscale): {'✅' if has_replicate else '⚠️ brak — 4K przez Lanczos'}"
    )

    st.sidebar.divider()

    quality = st.sidebar.radio(
        "Jakość",
        config.QUALITIES,
        index=1,
        horizontal=True,
        help="low = najtaniej, high = najlepsza jakość",
    )

    resolution = st.sidebar.radio(
        "Rozdzielczość",
        config.RESOLUTIONS,
        index=0,
        horizontal=True,
        help="4K = generujemy 2K i upscalujemy AI 2× przez Real-ESRGAN",
    )

    aspect_ratio = st.sidebar.radio(
        "Aspect ratio",
        config.ASPECT_RATIOS,
        index=0,
        horizontal=True,
    )

    batch_size = st.sidebar.slider(
        "Batch size (ile obrazów na klik)",
        config.BATCH_MIN,
        config.BATCH_MAX,
        value=1,
    )

    # Wymiar do pokazania
    native_res = config.native_resolution(resolution)
    w, h = config.SIZE_MAP[(aspect_ratio, native_res)]
    if config.needs_upscale(resolution):
        st.sidebar.caption(f"Wymiar: {w}x{h} -> upscale -> {w*2}x{h*2}")
    else:
        st.sidebar.caption(f"Wymiar: {w}x{h}")

    # Cost preview
    cost = cost_calculator.estimate_cost(quality, resolution, batch_size)
    st.sidebar.markdown(
        f"### 💰 Szacowany koszt: **{cost_calculator.format_cost(cost)}**"
    )
    st.sidebar.caption(f"({batch_size} × {quality} × {resolution})")

    return {
        "quality": quality,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "batch_size": batch_size,
    }


# ---------- Tab: Generate ----------
def render_generate_tab(settings):
    st.header("🎨 Generuj obrazy")

    prompt = st.text_area(
        "Prompt",
        value=st.session_state.prompt,
        height=120,
        placeholder="np. futurystyczne miasto nocą, neonowe światła, deszcz, cyberpunk",
        key="prompt_input",
    )

    with st.expander("➕ Negative prompt (opcjonalnie)"):
        negative_prompt = st.text_area(
            "Czego unikać",
            value=st.session_state.negative_prompt,
            height=60,
            placeholder="np. rozmycie, niska jakość, podpisy, znaki wodne",
            key="neg_prompt_input",
        )

    with st.expander("🖼️ Obrazy referencyjne (opcjonalnie, max 4) — Higgsfield-style"):
        st.caption(
            "Wgraj 1–4 obrazów referencyjnych. Model użyje ich jako inspiracji "
            "stylem/kompozycją. Włącza endpoint /v1/images/edits."
        )
        ref_files = st.file_uploader(
            "Wgraj obrazy",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="ref_uploader",
        )
        if ref_files and len(ref_files) > config.MAX_REFERENCE_IMAGES:
            st.warning(
                f"Max {config.MAX_REFERENCE_IMAGES} obrazów. Użyję pierwszych {config.MAX_REFERENCE_IMAGES}."
            )
            ref_files = ref_files[: config.MAX_REFERENCE_IMAGES]
        if ref_files:
            cols = st.columns(len(ref_files))
            for col, f in zip(cols, ref_files):
                col.image(f, use_container_width=True)

    if st.button("🚀 Generate", type="primary", use_container_width=True):
        if not prompt.strip():
            st.error("Wpisz prompt.")
            return

        if not config.get_secret("OPENAI_API_KEY"):
            st.error("Brak OPENAI_API_KEY w .env. Skopiuj .env.example i wpisz klucz.")
            return

        ref_bytes = [f.read() for f in (ref_files or [])]

        with st.spinner(
            f"Generuję {settings['batch_size']} × {settings['quality']} {settings['resolution']}..."
        ):
            try:
                t0 = time.time()
                images = image_generator.generate_images(
                    prompt=prompt,
                    quality=settings["quality"],
                    aspect_ratio=settings["aspect_ratio"],
                    resolution=settings["resolution"],
                    n=settings["batch_size"],
                    reference_images=ref_bytes if ref_bytes else None,
                    negative_prompt=negative_prompt,
                )

                if config.needs_upscale(settings["resolution"]):
                    progress = st.progress(0, text="Upscaling do 4K...")
                    upscaled = []
                    for i, img in enumerate(images, 1):
                        upscaled.append(upscaler.upscale_to_4k(img))
                        progress.progress(
                            i / len(images),
                            text=f"Upscale {i}/{len(images)}",
                        )
                    images = upscaled
                    progress.empty()

                elapsed = time.time() - t0
                cost = cost_calculator.estimate_cost(
                    settings["quality"], settings["resolution"], settings["batch_size"]
                )

                metadata = {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "model": config.MODEL_ID,
                    "quality": settings["quality"],
                    "resolution": settings["resolution"],
                    "aspect_ratio": settings["aspect_ratio"],
                    "batch_size": settings["batch_size"],
                    "reference_images_count": len(ref_bytes),
                    "estimated_cost_usd": round(cost, 4),
                    "generation_time_s": round(elapsed, 1),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }

                folder = history.save_generation(images, metadata)
                st.session_state.last_results = [
                    (str(folder / f"image_{i+1}.png"), metadata)
                    for i in range(len(images))
                ]

                st.success(
                    f"✅ Wygenerowano {len(images)} obrazów w {elapsed:.1f}s "
                    f"(koszt ~{cost_calculator.format_cost(cost)}). Zapisane: {folder.name}"
                )
            except Exception as e:
                st.error(f"❌ Błąd: {e}")
                return

    # Wyniki
    if st.session_state.last_results:
        st.divider()
        st.subheader("📸 Wyniki")
        cols = st.columns(2)
        for i, (path, meta) in enumerate(st.session_state.last_results):
            with cols[i % 2]:
                st.image(path, use_container_width=True)
                with open(path, "rb") as f:
                    st.download_button(
                        "⬇️ Pobierz PNG",
                        f.read(),
                        file_name=Path(path).name,
                        mime="image/png",
                        key=f"dl_{i}",
                        use_container_width=True,
                    )
                c1, c2 = st.columns(2)
                if c1.button("♻️ Użyj promptu", key=f"reuse_{i}", use_container_width=True):
                    st.session_state.prompt = meta.get("prompt", "")
                    st.session_state.negative_prompt = meta.get("negative_prompt", "")
                    st.rerun()
                if c2.button("🎨 Edytuj", key=f"edit_{i}", use_container_width=True):
                    st.session_state.edit_image = Path(path).read_bytes()
                    st.info("Przejdź do zakładki **Edit / Inpaint**.")


# ---------- Tab: Edit ----------
def render_edit_tab(settings):
    st.header("🎨 Edit / Inpaint")
    st.caption(
        "Wgraj obraz, opcjonalnie maskę (PNG z przezroczystością — przezroczyste obszary "
        "zostaną przemalowane) i wpisz prompt opisujący zmianę."
    )

    if st.session_state.edit_image:
        st.success("Obraz wczytany z zakładki Generate.")
        if st.button("Wyczyść", key="clear_edit"):
            st.session_state.edit_image = None
            st.rerun()
        img_bytes = st.session_state.edit_image
    else:
        uploaded = st.file_uploader("Obraz do edycji", type=["png", "jpg", "jpeg"])
        img_bytes = uploaded.read() if uploaded else None

    if img_bytes:
        st.image(img_bytes, caption="Wejście", use_container_width=True)

    mask_file = st.file_uploader(
        "Maska (opcjonalnie, PNG z alpha)",
        type=["png"],
        key="mask_upload",
    )
    mask_bytes = mask_file.read() if mask_file else None

    edit_prompt = st.text_area(
        "Prompt edycji",
        height=100,
        placeholder="np. zamień niebo na zachód słońca",
    )

    if st.button("🚀 Edytuj", type="primary", use_container_width=True):
        if not img_bytes:
            st.error("Wgraj obraz.")
            return
        if not edit_prompt.strip():
            st.error("Wpisz prompt.")
            return

        with st.spinner("Edytuję..."):
            try:
                results = image_generator.edit_image(
                    image_bytes=img_bytes,
                    prompt=edit_prompt,
                    quality=settings["quality"],
                    aspect_ratio=settings["aspect_ratio"],
                    resolution=settings["resolution"],
                    mask_bytes=mask_bytes,
                    n=1,
                )
                if config.needs_upscale(settings["resolution"]):
                    results = [upscaler.upscale_to_4k(r) for r in results]

                metadata = {
                    "prompt": edit_prompt,
                    "model": config.MODEL_ID,
                    "mode": "edit" if not mask_bytes else "inpaint",
                    "quality": settings["quality"],
                    "resolution": settings["resolution"],
                    "aspect_ratio": settings["aspect_ratio"],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                folder = history.save_generation(results, metadata)

                st.success(f"✅ Zapisane w {folder.name}")
                for r in results:
                    st.image(r, use_container_width=True)
                    st.download_button(
                        "⬇️ Pobierz",
                        r,
                        file_name="edit.png",
                        mime="image/png",
                        use_container_width=True,
                    )
            except Exception as e:
                st.error(f"❌ Błąd: {e}")


# ---------- Tab: History ----------
def render_history_tab():
    st.header("📚 Historia generacji")

    entries = history.load_history(limit=100)
    if not entries:
        st.info("Brak historii — wygeneruj coś w zakładce Generate.")
        return

    st.caption(f"Pokazuję {len(entries)} ostatnich generacji")

    for entry in entries:
        first_prompt = history.get_first_prompt(entry)
        prompt_preview = (first_prompt[:80] + "...") if len(first_prompt) > 80 else first_prompt
        with st.expander(f"📁 {entry['name']} — {prompt_preview or '(bez promptu)'}"):
            cols = st.columns(min(4, len(entry["items"])))
            for i, item in enumerate(entry["items"]):
                with cols[i % len(cols)]:
                    st.image(item["path"], use_container_width=True)
                    meta = item["metadata"]
                    st.caption(
                        f"**{meta.get('quality','?')}** {meta.get('resolution','?')} "
                        f"{meta.get('aspect_ratio','?')}"
                    )
                    with open(item["path"], "rb") as f:
                        st.download_button(
                            "⬇️",
                            f.read(),
                            file_name=Path(item["path"]).name,
                            mime="image/png",
                            key=f"hist_dl_{entry['name']}_{i}",
                        )

            if first_prompt and st.button(
                "♻️ Użyj tego promptu", key=f"hist_reuse_{entry['name']}"
            ):
                meta = entry["items"][0]["metadata"]
                st.session_state.prompt = meta.get("prompt", "")
                st.session_state.negative_prompt = meta.get("negative_prompt", "")
                st.rerun()


# ---------- Main ----------
st.title("🎨 GPT Image Studio")
st.caption(
    f"Higgsfield-style generator obrazów na **{config.MODEL_ID}** • "
    "1K/2K/4K • batch • reference images • inpainting"
)

settings = render_sidebar()

tab_gen, tab_edit, tab_history = st.tabs(["🎨 Generate", "✏️ Edit / Inpaint", "📚 History"])

with tab_gen:
    render_generate_tab(settings)

with tab_edit:
    render_edit_tab(settings)

with tab_history:
    render_history_tab()
