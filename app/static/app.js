/**
 * KantinPos İstemci Tarafı JavaScript Yardımcıları
 */

// Sayı formatlayıcı: 1.234,56 ₺
const currencyFormatter = new Intl.NumberFormat('tr-TR', {
  style: 'currency',
  currency: 'TRY',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatMoney(amount) {
  return currencyFormatter.format(amount || 0);
}

// Toast Bildirimi Göster
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast px-4 py-3 rounded-lg text-sm font-medium text-white flex items-center gap-2 ${
    type === 'success' ? 'bg-emerald-600' :
    type === 'error' ? 'bg-rose-600' :
    type === 'warning' ? 'bg-amber-600' : 'bg-slate-800'
  }`;

  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span class="font-bold">${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.4s ease';
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

// Koyu Mod (Dark Mode) Yönetimi
function initTheme() {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (saved === 'dark' || (!saved && prefersDark)) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// Yüksek Kontrast Modu
function toggleHighContrast() {
  const isHc = document.body.classList.toggle('high-contrast');
  localStorage.setItem('highContrast', isHc ? '1' : '0');
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  if (localStorage.getItem('highContrast') === '1') {
    document.body.classList.add('high-contrast');
  }
});
