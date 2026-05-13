export const getBCSColor = (bcs) => {
  const num = parseFloat(bcs);
  if (isNaN(num)) return { bg: '#E5E7EB', text: '#374151' }; // Gris neutro si no hay dato

  if (num < 2.5) {
    // 🚨 Condición muy baja (Alerta)
    return { bg: '#DC2626', text: '#FFFFFF' }; // Rojo intenso
  } 
  else if (num >= 2.5 && num < 3.5) {
    // ✅ Ideal
    return { bg: '#10B981', text: '#FFFFFF' }; // Verde esmeralda fuerte
  } 
  else if (num >= 3.5 && num < 4.0) {
    // ⚠️ Sobre-condicionada (Precaución)
    return { bg: '#F59E0B', text: '#FFFFFF' }; // Naranja / Ámbar vibrante
  } 
  else {
    // 🛑 Obesa (Alerta máxima)
    return { bg: '#991B1B', text: '#FFFFFF' }; // Rojo oscuro / Vino
  }
};

export function getBCSLabel(bcs) {
  if (!bcs) return '—'
  if (bcs < 1.5) return 'Caquéctica'
  if (bcs < 2.5) return 'Delgada'
  if (bcs < 3.5) return 'Ideal'
  if (bcs < 4.5) return 'Sobre-condicionada'
  return 'Obesa'
}

export function formatPeso(kg) {
  if (!kg) return '—'
  return `${Number(kg).toFixed(1)} kg`
}

export function formatFecha(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('es-EC', { day:'2-digit', month:'short', year:'numeric' })
}

export function formatFechaHora(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-EC', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' })
}
