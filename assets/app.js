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
