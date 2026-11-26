document.addEventListener('click', function (ev) {
  var b = ev.target.closest('button.poster');
  if (!b) return;
  var f = document.createElement('iframe');
  var s = +b.dataset.start || 0;
  f.src = 'https://www.youtube-nocookie.com/embed/' + b.dataset.id + '?autoplay=1&playsinline=1&rel=0' + (s ? '&start=' + s : '');
  f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
  f.allowFullscreen = true;
  f.referrerPolicy = 'strict-origin-when-cross-origin';
  f.title = b.getAttribute('aria-label');
  b.replaceWith(f);
});

// 카톡 링크의 #t=acu.pha 로 (없으면 침·부항) 오늘 받은 치료 표시 (# 뒤는 서버로 전송되지 않음)
(function () {
  var m = /(?:^#|&)t=([a-z.]+)/.exec(location.hash);
  var codes = m ? m[1] : 'acu.cup';  // 링크에 치료 코드가 없으면 공통 치료(침·부항)
  var names = [];
  codes.split('.').forEach(function (k) {
    var li = document.querySelector('#after li[data-t="' + k + '"]');
    if (li) { li.hidden = false; names.push(li.querySelector('b').textContent); }
  });
  if (!names.length) return;
  document.getElementById('today').textContent = names.join(' · ');
  document.querySelector('.summary .today').hidden = false;
})();
