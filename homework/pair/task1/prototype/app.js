(function () {
  var current = 'home';
  var screens = document.querySelectorAll('.screen');
  var links = document.querySelectorAll('.screen-link');
  var toast = document.getElementById('toast');
  var toastTimer = null;

  function showScreen(name) {
    var found = false;
    screens.forEach(function (screen) {
      var active = screen.id === 'screen-' + name;
      screen.classList.toggle('active', active);
      if (active) found = true;
    });
    if (!found) return;
    current = name;
    links.forEach(function (link) {
      link.classList.toggle('active', link.getAttribute('data-goto') === name);
    });
    var activeScreen = document.getElementById('screen-' + name);
    if (activeScreen) activeScreen.scrollTop = 0;
    if (history.replaceState) history.replaceState(null, '', '#' + name);
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { toast.classList.remove('show'); }, 1800);
  }

  document.addEventListener('click', function (event) {
    var target = event.target.closest('[data-goto]');
    if (target) {
      event.preventDefault();
      showScreen(target.getAttribute('data-goto'));
      return;
    }
    var action = event.target.closest('[data-action="contact"]');
    if (action) {
      showToast('已打开联系方式面板：手机号 13x-xxxx-xxxx');
      return;
    }
    var statusButton = event.target.closest('.toggle-status');
    if (statusButton) {
      var card = statusButton.closest('.post-card');
      var badge = card.querySelector('.status');
      if (badge.classList.contains('pending')) {
        badge.textContent = '已找到';
        badge.classList.remove('pending');
        badge.classList.add('done');
        statusButton.textContent = '重新设为寻找中';
        showToast('状态已修改为“已找到”');
      } else {
        badge.textContent = '寻找中';
        badge.classList.remove('done');
        badge.classList.add('pending');
        statusButton.textContent = '标记为已找到';
        showToast('状态已重新设为“寻找中”');
      }
    }
  });

  document.querySelectorAll('.segment button, .chip, .publish-switch button').forEach(function (button) {
    button.addEventListener('click', function () {
      var parent = button.parentElement;
      parent.querySelectorAll('button').forEach(function (item) { item.classList.remove('active'); });
      button.classList.add('active');
    });
  });

  var initial = location.hash ? location.hash.slice(1) : 'home';
  showScreen(initial);
})();
