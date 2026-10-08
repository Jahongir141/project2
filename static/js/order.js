(function () {
  "use strict";
  var state = JSON.parse(document.getElementById("order-data").textContent);
  var urls = window.ORDER_URLS;
  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var $ = function (id) { return document.getElementById(id); };
  var queue = Promise.resolve();

  function money(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0"); }
  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

  function toast(msg) {
    var t = $("toast");
    t.textContent = msg || "";
    t.classList.toggle("show", !!msg);
  }

  function post(url, data) {
    // So'rovlar ketma-ket bajariladi: tez bosishlar yo'qolmaydi va "yuborish" izoh saqlanishidan keyin ketadi.
    var run = queue.then(function () {
      return fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, "X-Requested-With": "fetch" },
        body: JSON.stringify(data || {})
      }).then(function (res) {
        if (res.redirected) { location.reload(); return null; }
        var type = res.headers.get("content-type") || "";
        if (type.indexOf("application/json") === -1) {
          toast(res.status === 403 ? "Bu amalga ruxsat yo\u2018q." : "Server xatosi (" + res.status + ").");
          openSheet();
          return null;
        }
        return res.json().then(function (j) {
          if (!j.ok) { toast(j.error || "Xatolik yuz berdi."); openSheet(); return null; }
          toast("");
          state = j.order;
          render();
          return j;
        });
      }).catch(function () {
        toast("Tarmoq xatosi. Wi-Fi ulanishini tekshiring.");
        openSheet();
        return null;
      });
    });
    queue = run;
    return run;
  }

  function itemUrl(id, action) { return urls.itemBase + id + "/" + action + "/"; }

  function render() {
    var count = 0;
    state.items.forEach(function (i) { count += i.qty; });
    $("cart-count").textContent = count;
    $("cart-total").textContent = money(state.total);
    $("sheet-total").textContent = money(state.total) + " so\u2018m";
    $("order-status").textContent = state.status_label;

    var box = $("cart-items");
    if (!state.items.length) {
      box.innerHTML = '<div class="cart-empty">Savat bo\u2018sh. Menyudan mahsulot tanlang.</div>';
    } else {
      box.innerHTML = state.items.map(function (i) {
        var controls = "";
        if (i.editable) {
          controls = '<div class="cart-item__row">' +
            '<div class="qty"><button type="button" data-act="dec" data-id="' + i.id + '" aria-label="Kamaytirish">\u2212</button>' +
            '<span>' + i.qty + '</span>' +
            '<button type="button" data-act="inc" data-id="' + i.id + '" aria-label="Ko\u2018paytirish">+</button></div>' +
            '<input class="cart-item__note" data-act="note" data-id="' + i.id + '" maxlength="255" placeholder="Izoh (masalan: achchiq bo\u2018lmasin)" value="' + esc(i.note).replace(/"/g, "&quot;") + '">' +
            '<button type="button" class="cart-item__del" data-act="del" data-id="' + i.id + '" aria-label="O\u2018chirish">\u00d7</button></div>';
        } else if (i.note) {
          controls = '<div class="cart-item__noteview">' + esc(i.note) + '</div>';
        }
        return '<div class="cart-item"><div class="cart-item__top"><div>' +
          '<div class="cart-item__name">' + esc(i.name) + '</div>' +
          '<div class="cart-item__calc">' + i.qty + ' \u00d7 ' + money(i.price) + '</div>' +
          '<span class="chip chip--' + i.status + '">' + esc(i.status_label) + '</span></div>' +
          '<div class="cart-item__sum">' + money(i.line) + '</div></div>' + controls + '</div>';
      }).join("");
    }

    var send = $("send-btn");
    send.disabled = !(state.editable && state.has_new);
    $("pay-btn").disabled = !(state.editable && state.has_sent && !state.has_new && !state.payment_requested);
    $("pay-btn").textContent = state.payment_requested ? "Hisob so\u2018ralgan" : "Hisob so\u2018rash";
    $("cancel-btn").style.display = state.editable && !state.has_sent ? "" : "none";
    if (!state.active) { send.textContent = "BUYURTMA YOPILGAN"; }
  }

  function openSheet() { $("sheet").classList.add("open"); $("backdrop").classList.add("open"); $("sheet").setAttribute("aria-hidden", "false"); }
  function closeSheet() { $("sheet").classList.remove("open"); $("backdrop").classList.remove("open"); $("sheet").setAttribute("aria-hidden", "true"); }

  $("open-cart").addEventListener("click", openSheet);
  $("close-cart").addEventListener("click", closeSheet);
  $("backdrop").addEventListener("click", closeSheet);

  document.querySelectorAll(".product").forEach(function (btn) {
    btn.addEventListener("click", function () {
      post(urls.add, { product_id: btn.dataset.product, quantity: 1 }).then(function (r) {
        if (r) { btn.classList.add("flash-added"); setTimeout(function () { btn.classList.remove("flash-added"); }, 350); }
      });
    });
  });

  function findItem(id) { return state.items.filter(function (i) { return String(i.id) === String(id); })[0]; }

  $("cart-items").addEventListener("click", function (e) {
    var el = e.target.closest("[data-act]");
    if (!el || el.tagName === "INPUT") return;
    var item = findItem(el.dataset.id);
    if (!item) return;
    if (el.dataset.act === "inc") post(itemUrl(item.id, "qty"), { delta: 1 });
    if (el.dataset.act === "dec") post(itemUrl(item.id, "qty"), { delta: -1 });
    if (el.dataset.act === "del") post(itemUrl(item.id, "remove"), {});
  });

  $("cart-items").addEventListener("change", function (e) {
    if (e.target.dataset && e.target.dataset.act === "note") {
      post(itemUrl(e.target.dataset.id, "note"), { note: e.target.value });
    }
  });

  $("send-btn").addEventListener("click", function () {
    var btn = this;
    if (btn.disabled) return;
    btn.disabled = true;
    btn.textContent = "Yuborilmoqda...";
    post(urls.send, {}).then(function (r) {
      btn.textContent = "BUYURTMANI YUBORISH";
      if (r) { toast(""); closeSheet(); showDone(); }
      render();
    });
  });

  $("pay-btn").addEventListener("click", function () { post(urls.pay, {}); });

  $("cancel-btn").addEventListener("click", function () {
    if (!confirm("Buyurtmani bekor qilasizmi?")) return;
    post(urls.cancel, {}).then(function (r) { if (r && r.redirect) location.href = r.redirect; });
  });

  function showDone() {
    var f = document.createElement("div");
    f.className = "flash flash--success";
    f.style.cssText = "position:fixed;left:14px;right:14px;top:14px;z-index:60;text-align:center";
    f.textContent = "Buyurtma yuborildi \u2713";
    document.body.appendChild(f);
    setTimeout(function () { f.remove(); }, 2200);
  }

  render();
})();
