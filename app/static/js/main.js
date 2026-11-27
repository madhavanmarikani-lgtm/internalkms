// AI Key Manager - Client Interactions

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize Lucide Icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }

  // 2. Mobile Sidebar Toggle
  const sidebar = document.getElementById('appSidebar');
  const toggleBtn = document.getElementById('sidebarToggle');
  const overlay = document.getElementById('sidebarOverlay');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('show');
      if (overlay) overlay.classList.toggle('d-none');
    });
  }

  if (overlay) {
    overlay.addEventListener('click', () => {
      if (sidebar) sidebar.classList.remove('show');
      overlay.classList.add('d-none');
    });
  }

  // 3. Copy to Clipboard
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const text = this.getAttribute('data-copy');
      if (text) {
        navigator.clipboard.writeText(text).then(() => {
          const original = this.innerHTML;
          this.innerHTML = '<span class="text-success small fw-semibold">Copied</span>';
          setTimeout(() => {
            this.innerHTML = original;
            if (typeof lucide !== 'undefined') lucide.createIcons();
          }, 1500);
        });
      }
    });
  });

  // 4. Mask / Reveal Sensitive Identifiers by Default
  document.querySelectorAll('.btn-reveal-secret').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const targetId = this.getAttribute('data-target');
      const span = document.getElementById(targetId);
      if (!span) return;

      const isMasked = span.getAttribute('data-masked') !== 'false';
      const realVal = span.getAttribute('data-value') || '';
      const maskedVal = span.getAttribute('data-masked-value') || '••••••••••••';

      if (isMasked) {
        span.textContent = realVal;
        span.setAttribute('data-masked', 'false');
        this.title = 'Hide identifier';
      } else {
        span.textContent = maskedVal;
        span.setAttribute('data-masked', 'true');
        this.title = 'Reveal identifier';
      }
    });
  });

  // 5. Client-Side Table Row Filtering
  const clientFilterInput = document.getElementById('clientTableSearch');
  if (clientFilterInput) {
    clientFilterInput.addEventListener('input', function () {
      const val = this.value.toLowerCase();
      document.querySelectorAll('.filterable-row').forEach(row => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(val) ? '' : 'none';
      });
    });
  }

  // 6. Dark Mode Toggle
  const themeBtn = document.getElementById('themeToggleBtn');
  function syncThemeIcon() {
    if (!themeBtn) return;
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    themeBtn.innerHTML = isDark ? '<i data-lucide="sun"></i>' : '<i data-lucide="moon"></i>';
    themeBtn.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }

  if (themeBtn) {
    syncThemeIcon();
    themeBtn.addEventListener('click', () => {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      if (isDark) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('ai_km_theme', 'light');
      } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('ai_km_theme', 'dark');
      }
      syncThemeIcon();
    });
  }
});
