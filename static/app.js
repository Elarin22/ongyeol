(() => {
  'use strict';

  const body = document.body;
  const menuButton = document.querySelector('[data-sidebar-toggle]');
  const sidebar = document.getElementById('sidebar');
  const closeTarget = document.querySelector('[data-sidebar-close]');

  const closeSidebar = () => {
    body.classList.remove('sidebar-open');
    menuButton?.setAttribute('aria-expanded', 'false');
    menuButton?.setAttribute('aria-label', '메뉴 열기');
  };

  if (menuButton && sidebar) {
    menuButton.addEventListener('click', () => {
      const isOpen = body.classList.toggle('sidebar-open');
      menuButton.setAttribute('aria-expanded', String(isOpen));
      menuButton.setAttribute('aria-label', isOpen ? '메뉴 닫기' : '메뉴 열기');
    });

    closeTarget?.addEventListener('click', closeSidebar);
    sidebar.addEventListener('click', (event) => {
      if (event.target.closest('a')) closeSidebar();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeSidebar();
    });
    window.addEventListener('resize', () => {
      if (window.matchMedia('(min-width: 761px)').matches) closeSidebar();
    });
  }

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) return;

    const dismiss = event.target.closest('.flash-dismiss');
    if (dismiss) dismiss.closest('.flash-message')?.remove();

    const copyButton = event.target.closest('[data-copy-target]');
    if (copyButton) {
      const target = document.getElementById(copyButton.dataset.copyTarget || '');
      if (target instanceof HTMLInputElement) {
        target.focus();
        target.select();
        const feedback = copyButton.closest('.created-invite-link')?.querySelector('.copy-feedback');
        const showResult = (copied) => {
          if (feedback) feedback.textContent = copied ? '초대 링크를 복사했어요.' : '복사하지 못했어요. 주소를 선택해 직접 복사해 주세요.';
        };
        if (navigator.clipboard?.writeText) {
          navigator.clipboard.writeText(target.value).then(() => showResult(true)).catch(() => {
            try { showResult(document.execCommand('copy')); } catch { showResult(false); }
          });
        } else {
          try { showResult(document.execCommand('copy')); } catch { showResult(false); }
        }
      }
    }
  });

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const message = form.dataset.confirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });

  const settingsForm = document.querySelector('.settings-form');
  const reminderToggle = settingsForm?.querySelector('input[name="reminder_enabled"]');
  if (settingsForm instanceof HTMLFormElement && reminderToggle instanceof HTMLInputElement) {
    settingsForm.addEventListener('submit', async (event) => {
      if (!reminderToggle.checked || !('Notification' in window) || Notification.permission !== 'default') return;
      event.preventDefault();
      const note = settingsForm.querySelector('.reminder-privacy-note');
      try {
        const permission = await Notification.requestPermission();
        if (permission === 'granted') {
          settingsForm.requestSubmit();
        } else if (note) {
          note.textContent = '브라우저 알림 권한이 허용되지 않았어요. 설정은 저장되지만 알림은 표시되지 않습니다.';
        }
      } catch {
        if (note) note.textContent = '브라우저에서 알림 권한을 요청하지 못했어요. 브라우저 설정을 확인해 주세요.';
      }
    });
  }

  const reminderEnabled = body.dataset.reminderEnabled === '1';
  const reminderTime = body.dataset.reminderTime || '';
  if (!reminderEnabled || !/^([01]\d|2[0-3]):[0-5]\d$/.test(reminderTime) || !('Notification' in window)) return;

  const checkReminder = () => {
    if (Notification.permission !== 'granted') return;
    const now = new Date();
    const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    if (currentTime !== reminderTime) return;
    const localDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const storageKey = `ongyeol.reminder.sent.${localDate}`;
    try {
      if (window.localStorage.getItem(storageKey)) return;
      window.localStorage.setItem(storageKey, '1');
    } catch {
      // If browser storage is unavailable, still show the reminder.
    }
    new Notification('온결 · 오늘의 공부를 기록해요', {
      body: '잠깐 돌아보는 것도 좋은 공부 습관이에요. 오늘의 집중을 남겨 볼까요?',
      icon: '/static/favicon.svg',
      tag: `ongyeol-study-reminder-${localDate}`,
    });
  };

  checkReminder();
  window.setInterval(checkReminder, 15000);
})();
