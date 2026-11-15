/* Profile photo picker.
   When a member chooses a picture, shrink it in the browser first so the upload is quick even
   on a phone, then either send it straight away (member page) or show a preview (edit page).
   If anything here fails, the original file is sent as chosen; the server checks it either way. */
(function () {
  var MAX = 1200;   // longest side, in pixels, before sending

  function shrink(file) {
    return new Promise(function (resolve) {
      if (!window.URL || !window.DataTransfer || !/^image\/(jpeg|png|webp)$/.test(file.type)) return resolve(file);
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        try {
          var scale = Math.min(1, MAX / Math.max(img.naturalWidth, img.naturalHeight));
          var w = Math.max(1, Math.round(img.naturalWidth * scale)), h = Math.max(1, Math.round(img.naturalHeight * scale));
          var canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h;
          var ctx = canvas.getContext('2d');
          ctx.fillStyle = '#0a1628'; ctx.fillRect(0, 0, w, h);      // behind see-through pictures
          ctx.drawImage(img, 0, 0, w, h);
          canvas.toBlob(function (blob) {
            URL.revokeObjectURL(url);
            if (!blob || blob.size >= file.size) return resolve(file);
            resolve(new File([blob], 'photo.jpg', { type: 'image/jpeg' }));
          }, 'image/jpeg', 0.9);
        } catch (e) { URL.revokeObjectURL(url); resolve(file); }
      };
      img.onerror = function () { URL.revokeObjectURL(url); resolve(file); };
      img.src = url;
    });
  }

  function preview(input, file) {
    var holder = document.querySelector(input.getAttribute('data-photo-preview') || '');
    if (!holder || !window.URL) return;
    var img = holder.querySelector('img');
    if (!img) { img = document.createElement('img'); img.alt = ''; holder.appendChild(img); }
    img.src = URL.createObjectURL(file);
  }

  Array.prototype.forEach.call(document.querySelectorAll('input[type=file][data-photo-input]'), function (input) {
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (!file) return;
      var auto = input.hasAttribute('data-auto-submit');
      var label = auto && input.parentNode.querySelector('span');
      if (label) label.textContent = 'Uploading…';
      shrink(file).then(function (small) {
        if (small !== file) {
          try { var dt = new DataTransfer(); dt.items.add(small); input.files = dt.files; } catch (e) { /* send the original */ }
        }
        if (auto) input.form.submit(); else preview(input, small);
      });
    });
  });
})();
