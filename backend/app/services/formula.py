"""
JER-Weight — Formula Service (Render)
========================================
Cálculo de peso vivo mediante fórmulas morfométricas clásicas,
usadas como método de comparación frente a la estimación por IA.
Pura aritmética — sin dependencias de modelos, sin llamadas HTTP.

Fórmulas (Galindo, 2014):
  Schoorl:        PV = (PT + 22)² / 100
  Crevat-Quittet: PV = PT² × LC / 10800
Donde PT = perímetro torácico (cm), LC = longitud corporal (cm),
PV = peso vivo estimado (kg).
"""
from dataclasses import dataclass


@dataclass
class ResultadoComparacion:
    peso_ia_kg:              float
    peso_schoorl_kg:         float
    peso_crevat_kg:          float
    diferencia_schoorl_kg:   float
    diferencia_schoorl_pct:  float
    diferencia_crevat_kg:    float
    diferencia_crevat_pct:   float


class FormulaService:

    def schoorl(self, perimetro_toracico_cm: float) -> float:
        """PV = (PT + 22)² / 100"""
        pv = ((perimetro_toracico_cm + 22) ** 2) / 100
        return round(pv, 2)

    def crevat_quittet(self, perimetro_toracico_cm: float, longitud_corporal_cm: float) -> float:
        """PV = PT² × LC / 10800"""
        pv = (perimetro_toracico_cm ** 2 * longitud_corporal_cm) / 10800
        return round(pv, 2)

    def comparar(
        self,
        peso_ia_kg: float,
        perimetro_toracico_cm: float,
        longitud_corporal_cm: float,
    ) -> ResultadoComparacion:
        peso_schoorl = self.schoorl(perimetro_toracico_cm)
        peso_crevat  = self.crevat_quittet(perimetro_toracico_cm, longitud_corporal_cm)

        diff_schoorl_kg  = round(peso_ia_kg - peso_schoorl, 2)
        diff_crevat_kg   = round(peso_ia_kg - peso_crevat, 2)

        diff_schoorl_pct = round(abs(diff_schoorl_kg) / peso_schoorl * 100, 2) if peso_schoorl else 0.0
        diff_crevat_pct  = round(abs(diff_crevat_kg) / peso_crevat * 100, 2) if peso_crevat else 0.0

        return ResultadoComparacion(
            peso_ia_kg              = peso_ia_kg,
            peso_schoorl_kg         = peso_schoorl,
            peso_crevat_kg          = peso_crevat,
            diferencia_schoorl_kg   = diff_schoorl_kg,
            diferencia_schoorl_pct  = diff_schoorl_pct,
            diferencia_crevat_kg    = diff_crevat_kg,
            diferencia_crevat_pct   = diff_crevat_pct,
        )


formula_service = FormulaService()