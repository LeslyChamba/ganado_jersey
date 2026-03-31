# test_vision.py
"""
PRUEBA DEL MÓDULO DE VISIÓN
=============================
Ejecuta el pipeline OpenCV en una imagen de prueba
y muestra los resultados + imagen de debug anotada.

Escala calculada automáticamente usando la altura
promedio de la raza Jersey (123 cm). Sin barra de referencia.

Uso:
    python test_vision.py ruta/foto_vaca.jpg
    python test_vision.py ruta/foto_vaca.jpg --altura 118
    python test_vision.py ruta/foto_vaca.jpg --out mi_debug.jpg

El parámetro --altura permite ajustar si sabes que una vaca
específica es notablemente más pequeña o grande que el promedio.
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.vision.morphometry import (
    process_image,
    save_debug_image,
    JERSEY_ALTURA_PROMEDIO_CM,
)


def main():
    parser = argparse.ArgumentParser(
        description="Probar visión computacional — escala por altura promedio Jersey"
    )
    parser.add_argument("image", help="Ruta a la imagen lateral de la vaca")
    parser.add_argument(
        "--altura", type=float, default=JERSEY_ALTURA_PROMEDIO_CM,
        help=f"Altura promedio asumida en cm (default: {JERSEY_ALTURA_PROMEDIO_CM})"
    )
    parser.add_argument("--out", default="debug_output.jpg",
                        help="Ruta de salida de la imagen anotada")
    args = parser.parse_args()

    img_path = Path(args.image)
    if not img_path.exists():
        print(f"\n❌ Imagen no encontrada: {img_path}")
        sys.exit(1)

    print(f"\n🔍 Procesando: {img_path.name}")
    print(f"   Altura Jersey asumida: {args.altura} cm\n")

    # Temporalmente sobreescribir la constante si se pasó --altura
    import app.services.vision.morphometry as morph_module
    morph_module.JERSEY_ALTURA_PROMEDIO_CM = args.altura

    with open(img_path, "rb") as f:
        image_bytes = f.read()

    result = process_image(image_bytes)

    # ── Mostrar resultados ────────────────────────────────────────────────
    sep = "═" * 50
    print(sep)
    print("  MEDIDAS MORFOMÉTRICAS")
    print(sep)
    print(f"  Largo corporal (lc)         {result.largo_corporal_cm:>7.1f} cm")
    print(f"  Altura a la cruz (ac)       {result.altura_cruz_cm:>7.1f} cm")
    print(f"  Perímetro torácico (pt)     {result.perimetro_toracico_cm:>7.1f} cm")
    print(f"  Ancho de cadera             {result.ancho_cadera_cm:>7.1f} cm")
    print()
    print(f"  Escala calculada            {result.pixels_per_cm:>7.3f} px/cm")
    print(f"  Confianza de segmentación   {result.confidence:>7.2f} / 1.0")
    print()
    print("  FEATURES PARA XGBOOST")
    print(f"  area_norm                   {result.area_norm:>10.5f}")
    print(f"  ratio_lh                    {result.ratio_lh:>10.4f}")
    print(f"  perimeter_norm              {result.perimeter_norm:>10.4f}")
    print(sep)

    # ── Advertencias ─────────────────────────────────────────────────────
    if result.scale_warning:
        print(f"\n⚠  ADVERTENCIA DE ESCALA:")
        print(f"   {result.scale_warning}")
        print("   Verifica que el cuerpo completo sea visible en la foto.")

    if result.confidence < 0.50:
        print(f"\n⚠  CONFIANZA BAJA ({result.confidence:.2f})")
        print("   La segmentación no fue limpia. Verifica que:")
        print("   - La vaca ocupa al menos 50% del alto del frame")
        print("   - El fondo contrasta con el animal")
        print("   - La foto es lateral (no frontal ni en diagonal)")

    if result.confidence >= 0.65 and not result.scale_warning:
        print(f"\n✓  Segmentación OK (confianza: {result.confidence:.2f})")

    # ── Guardar debug ─────────────────────────────────────────────────────
    save_debug_image(result, args.out)
    print(f"\n✓  Imagen anotada guardada en: {args.out}")
    print("   Ábrela para verificar que las líneas de medición están bien.\n")


if __name__ == "__main__":
    main()
