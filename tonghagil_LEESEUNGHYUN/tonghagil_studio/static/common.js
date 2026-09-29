// Command Center 공통 동작: 안내 토스트, 아직 준비 안 된 메뉴/주소 없는 에이전트 처리
(function () {
  const toast = document.getElementById('cc-toast');
  let timer;

  window.ccToast = function (message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(timer);
    timer = setTimeout(() => toast.classList.remove('is-visible'), 2600);
  };

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-coming-soon]')) {
      window.ccToast('준비 중인 메뉴예요.');
      return;
    }
    const noUrl = event.target.closest('[data-no-url]');
    if (noUrl) {
      event.preventDefault();
      window.ccToast(`'${noUrl.dataset.noUrl}' 에이전트는 아직 주소가 등록되지 않았어요.`);
    }
  });
})();
