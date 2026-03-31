export function getBCSColor(bcs) {
  if (bcs < 2.0) return { bg: '#ff555533', text: '#ff8a8a' }
  if (bcs < 2.5) return { bg: '#E07B3933', text: '#f0a070' }
  if (bcs < 3.5) return { bg: '#6B8F7133', text: '#A8C5AD' }
  if (bcs < 4.5) return { bg: '#D4A85333', text: '#D4A853' }
  return              { bg: '#ff555533', text: '#ff8a8a' }
}

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
