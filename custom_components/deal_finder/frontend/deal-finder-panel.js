/* Deal Finder – sidebar panel to edit the wishlist. No build step required. */

const I18N = {
  de: {
    title: "Wunschliste",
    add: "Produkt",
    searchAll: "Alle suchen",
    filter: "Filtern…",
    notLoaded: "Deal Finder ist nicht geladen. Bitte die Integration unter Einstellungen → Geräte & Dienste einrichten.",
    empty: "Noch keine Produkte. Füge dein erstes Produkt hinzu!",
    noPrice: "Noch kein Preis",
    at: "bei",
    verified: "geprüft",
    unverified: "nicht geprüft",
    target: "Zielpreis",
    noTarget: "kein Ziel",
    lowest: "Allzeit-Tief",
    checked: "Geprüft",
    never: "noch nie",
    belowTarget: "Unter Ziel",
    underBy: "unter Ziel",
    overBy: "über Ziel",
    searching: "Suche läuft…",
    stale: "Letzte Suche ohne Ergebnis – zeige letzten bekannten Preis.",
    error: "Fehler",
    offers: "Angebote",
    search: "Suchen",
    edit: "Bearbeiten",
    del: "Löschen",
    confirmDelete: "„{name}“ wirklich von der Wunschliste löschen?",
    newProduct: "Produkt hinzufügen",
    editProduct: "Produkt bearbeiten",
    name: "Produktname",
    query: "Suchbegriff (optional)",
    queryHelp: "Leer = Produktname. Möglichst genau: Modell, Speicher, Farbe.",
    targetPrice: "Zielpreis",
    minPrice: "Mindestpreis",
    minHelp: "Filtert Zubehör und Fehltreffer.",
    urls: "Produkt-URLs (eine pro Zeile)",
    urlsHelp: "Shop- oder Preisvergleichsseiten, z.B. toppreise.ch oder geizhals.",
    exclude: "Ausschlussbegriffe",
    excludeHelp: "Kommagetrennt, z.B. gebraucht, refurbished, hülle",
    webSearch: "Im Web suchen (KI / SerpAPI)",
    noWebSearch: "Keine KI und kein SerpAPI konfiguriert – nur Produkt-URLs werden geprüft.",
    cancel: "Abbrechen",
    save: "Speichern",
    products: "Produkte",
    deals: "unter Zielpreis",
    source: "Quelle",
    every: "Suche alle {h} h",
    hide: "Unpassend – ausblenden",
    hidden: "Ausgeblendet",
    restore: "Wiederherstellen",
    restoreAll: "Alle wiederherstellen",
    restoreHint: "Wiederhergestellte Angebote erscheinen bei der nächsten Suche wieder.",
    hideOffer: "Nur dieses Angebot",
    hideShop: "Ganzer Shop",
    hideShopTitle: "Alle Angebote von {shop} für dieses Produkt ausblenden",
    shopHidden: "Shop: {shop} (alle Angebote)",
    reconnecting: "Verbindung wird wiederhergestellt…",
    updating: "Wird aktualisiert…",
    errors: {
      no_source: "Keine Preisquelle: Produkt-URLs angeben oder KI/SerpAPI konfigurieren und Websuche aktivieren.",
      invalid_url: "Bitte gültige http(s)-URLs eingeben.",
      name_required: "Bitte einen Produktnamen eingeben.",
      invalid_number: "Ungültige Zahl.",
      no_offers: "Keine Angebote gefunden.",
    },
  },
  en: {
    title: "Wishlist",
    add: "Product",
    searchAll: "Search all",
    filter: "Filter…",
    notLoaded: "Deal Finder is not loaded. Please set up the integration under Settings → Devices & services.",
    empty: "No products yet. Add your first product!",
    noPrice: "No price yet",
    at: "at",
    verified: "verified",
    unverified: "unverified",
    target: "Target price",
    noTarget: "no target",
    lowest: "All-time low",
    checked: "Checked",
    never: "never",
    belowTarget: "Below target",
    underBy: "below target",
    overBy: "above target",
    searching: "Searching…",
    stale: "Last search found nothing – showing last known price.",
    error: "Error",
    offers: "Offers",
    search: "Search",
    edit: "Edit",
    del: "Delete",
    confirmDelete: "Really remove “{name}” from the wishlist?",
    newProduct: "Add product",
    editProduct: "Edit product",
    name: "Product name",
    query: "Search term (optional)",
    queryHelp: "Empty = product name. Be specific: model, capacity, colour.",
    targetPrice: "Target price",
    minPrice: "Minimum price",
    minHelp: "Filters accessories and false matches.",
    urls: "Product URLs (one per line)",
    urlsHelp: "Shop or price comparison pages.",
    exclude: "Exclude terms",
    excludeHelp: "Comma separated, e.g. used, refurbished, case",
    webSearch: "Search the web (AI / SerpAPI)",
    noWebSearch: "No AI and no SerpAPI configured – only product URLs are checked.",
    cancel: "Cancel",
    save: "Save",
    products: "products",
    deals: "below target",
    source: "Source",
    every: "Search every {h} h",
    hide: "Not matching – hide",
    hidden: "Hidden",
    restore: "Restore",
    restoreAll: "Restore all",
    restoreHint: "Restored offers come back with the next search.",
    hideOffer: "This offer only",
    hideShop: "Whole shop",
    hideShopTitle: "Hide all offers from {shop} for this product",
    shopHidden: "Shop: {shop} (all offers)",
    reconnecting: "Reconnecting…",
    updating: "Updating…",
    errors: {
      no_source: "No price source: enter product URLs or configure AI/SerpAPI and enable web search.",
      invalid_url: "Please enter valid http(s) URLs.",
      name_required: "Please enter a product name.",
      invalid_number: "Invalid number.",
      no_offers: "No offers found.",
    },
  },
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);

const STYLE = `
  :host { display:block; min-height:100vh; background:var(--primary-background-color); color:var(--primary-text-color);
          font-family:var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  * { box-sizing:border-box; }
  .toolbar { display:flex; align-items:center; gap:8px; height:56px; padding:0 12px; position:sticky; top:0; z-index:2;
             background:var(--app-header-background-color, var(--primary-color)); color:var(--app-header-text-color, #fff);
             border-bottom:var(--app-header-border-bottom, none); }
  .toolbar h1 { font-size:20px; font-weight:400; margin:0 0 0 4px; flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .toolbar button { background:transparent; color:inherit; border:1px solid rgba(255,255,255,.5); }
  .toolbar button.primary { background:rgba(255,255,255,.18); }
  main { max-width:1400px; margin:0 auto; padding:16px; }
  .bar { display:flex; flex-wrap:wrap; gap:12px; align-items:center; margin-bottom:16px; color:var(--secondary-text-color); }
  .bar input { flex:1; min-width:180px; max-width:360px; }
  .stats b { color:var(--primary-text-color); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:16px; }
  .card { background:var(--card-background-color, #fff); border-radius:var(--ha-card-border-radius, 12px);
          box-shadow:var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.12)); border:var(--ha-card-border-width,1px) solid var(--divider-color, transparent);
          padding:16px; display:flex; flex-direction:column; gap:10px; position:relative; }
  .card.deal { border:2px solid var(--success-color, #43a047); }
  .top { display:flex; align-items:flex-start; gap:8px; }
  .name { font-size:17px; font-weight:500; flex:1; word-break:break-word; }
  .chip { font-size:12px; padding:3px 8px; border-radius:12px; white-space:nowrap; }
  .chip.deal { background:var(--success-color, #43a047); color:#fff; }
  .chip.busy { background:var(--info-color, #039be5); color:#fff; }
  .price { font-size:30px; font-weight:500; line-height:1.1; }
  .price.none { font-size:18px; color:var(--secondary-text-color); font-weight:400; }
  .meta { font-size:13px; color:var(--secondary-text-color); }
  .meta a, .offers a { color:var(--primary-color); text-decoration:none; }
  .ok { color:var(--success-color, #43a047); }
  .diff { font-size:13px; font-weight:500; }
  .diff.under { color:var(--success-color, #43a047); }
  .diff.over { color:var(--secondary-text-color); }
  .rows { display:grid; grid-template-columns:auto 1fr; gap:4px 12px; font-size:14px; }
  .rows span:nth-child(odd) { color:var(--secondary-text-color); }
  .rows span:nth-child(even) { text-align:right; }
  .warn { font-size:13px; padding:8px 10px; border-radius:8px; background:rgba(var(--rgb-warning-color, 255,166,0), .15); }
  details { font-size:14px; }
  summary { cursor:pointer; color:var(--secondary-text-color); }
  .offers { margin:8px 0 0; padding-left:20px; }
  .offers li { margin:3px 0; }
  .offers .p { font-weight:500; }
  .offers li, .blocked li { display:flex; align-items:baseline; gap:6px; }
  .offers li .txt, .blocked li .txt { flex:1; min-width:0; overflow-wrap:anywhere; }
  .x { border:none; padding:0 4px; font-size:15px; line-height:1; color:var(--secondary-text-color); background:none; border-radius:4px; }
  .x:hover { color:var(--error-color, #db4437); background:rgba(127,127,127,.15); }
  .blocked { margin:8px 0 0; padding-left:0; list-style:none; color:var(--secondary-text-color); }
  .blocked li { margin:4px 0; }
  .blocked button, details .linkbtn { padding:2px 8px; font-size:12px; }
  .hint { font-size:12px; color:var(--secondary-text-color); margin-top:6px; }
  .bestline { display:flex; align-items:baseline; gap:6px; }
  .choice { display:inline-flex; gap:4px; flex-wrap:wrap; justify-content:flex-end; }
  .choice button { padding:2px 8px; font-size:12px; }
  .status { display:none; margin-bottom:12px; padding:8px 12px; border-radius:8px; font-size:14px;
            background:rgba(var(--rgb-info-color, 3,155,229), .15); }
  .status.show { display:block; }
  .bestline .meta { flex:1; }
  .actions { display:flex; gap:8px; margin-top:auto; padding-top:4px; flex-wrap:wrap; }
  button { font:inherit; font-size:14px; cursor:pointer; border-radius:8px; padding:7px 14px;
           border:1px solid var(--divider-color, #ccc); background:transparent; color:var(--primary-text-color); }
  button:hover { filter:brightness(1.1); }
  button.primary { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
  button.danger { color:var(--error-color, #db4437); }
  button:disabled { opacity:.5; cursor:default; }
  input, textarea { font:inherit; font-size:15px; width:100%; padding:9px 11px; border-radius:8px;
                    border:1px solid var(--divider-color, #ccc); background:var(--secondary-background-color, transparent);
                    color:var(--primary-text-color); }
  textarea { min-height:80px; resize:vertical; }
  input:focus, textarea:focus { outline:2px solid var(--primary-color); outline-offset:-1px; }
  .empty, .notice { text-align:center; padding:48px 16px; color:var(--secondary-text-color); }
  .overlay { position:fixed; inset:0; background:rgba(0,0,0,.5); z-index:10; display:flex; align-items:center; justify-content:center; padding:16px; }
  .dialog { background:var(--card-background-color, #fff); color:var(--primary-text-color); border-radius:16px; width:100%; max-width:560px;
            max-height:calc(100vh - 32px); overflow:auto; padding:20px 24px; box-shadow:0 8px 32px rgba(0,0,0,.4); }
  .dialog h2 { margin:0 0 16px; font-weight:400; font-size:22px; }
  .field { margin-bottom:14px; }
  .field label { display:block; font-size:13px; color:var(--secondary-text-color); margin-bottom:4px; }
  .field .help { font-size:12px; color:var(--secondary-text-color); margin-top:3px; }
  .field .err { font-size:12px; color:var(--error-color, #db4437); margin-top:3px; }
  .two { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .check { display:flex; gap:10px; align-items:center; font-size:15px; }
  .check input { width:auto; }
  .formerr { color:var(--error-color, #db4437); font-size:14px; margin-bottom:12px; }
  .dialog .actions { justify-content:flex-end; }
  .spin { display:inline-block; width:12px; height:12px; border:2px solid currentColor; border-right-color:transparent;
          border-radius:50%; animation:spin .8s linear infinite; vertical-align:-2px; margin-right:4px; }
  @keyframes spin { to { transform:rotate(360deg); } }
  @media (max-width:600px) { main { padding:12px; } .two { grid-template-columns:1fr; } .toolbar .label { display:none; } }
`;

class DealFinderPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._filter = "";
    this._dialog = null; // {id, values, errors, saving}
    this._unsub = null;
    this._built = false;
    this._conn = null;
    this._retryTimer = null;
    this._unloadedTimer = null;
    this._pendingBlock = null; // "productId:idx" while the hide choice is shown
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (!this._built) this._build();
    if (this._menuButton) this._menuButton.hass = hass;
    if (first || (hass.connection && hass.connection !== this._conn)) this._resubscribe();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._menuButton) this._menuButton.narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    if (!this._visHandler) {
      // returning to the tab / app: fetch a fresh state
      this._visHandler = () => {
        if (document.visibilityState === "visible" && this.isConnected) this._resubscribe();
      };
      document.addEventListener("visibilitychange", this._visHandler);
    }
    if (this._hass) this._resubscribe();
  }

  disconnectedCallback() {
    this._unsubscribe();
    clearTimeout(this._retryTimer);
    if (this._visHandler) {
      document.removeEventListener("visibilitychange", this._visHandler);
      this._visHandler = null;
    }
    if (this._conn && this._readyHandler) this._conn.removeEventListener("ready", this._readyHandler);
    this._readyHandler = null;
    this._conn = null;
  }

  get t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
    return I18N[lang] || I18N.en;
  }

  get _lang() {
    return this._hass?.locale?.language || this._hass?.language || "en";
  }

  get _isAdmin() {
    return !!this._hass?.user?.is_admin;
  }

  _unsubscribe() {
    if (this._unsub) {
      this._unsub.then((unsub) => unsub()).catch(() => {});
      this._unsub = null;
    }
  }

  _resubscribe() {
    clearTimeout(this._retryTimer);
    this._unsubscribe();
    this._subscribe();
  }

  _subscribe() {
    const conn = this._hass?.connection;
    if (!conn || !this.isConnected || this._unsub) return;
    if (conn !== this._conn) {
      if (this._conn && this._readyHandler) this._conn.removeEventListener("ready", this._readyHandler);
      this._conn = conn;
      // after a reconnect (HA restart, network) the server-side subscription is
      // gone and HA may not have loaded the integration yet -> subscribe anew
      this._readyHandler = () => {
        this._setStatus(this.t.updating);
        clearTimeout(this._retryTimer);
        this._retryTimer = setTimeout(() => this._resubscribe(), 1000);
      };
      conn.addEventListener("ready", this._readyHandler);
    }
    const sub = conn.subscribeMessage((payload) => this._onPayload(payload), { type: "deal_finder/subscribe" });
    this._unsub = sub;
    sub
      .then(() => {
        this._retryDelay = 0;
      })
      .catch(() => {
        if (this._unsub !== sub) return;
        this._unsub = null;
        // e.g. "unknown_command" while HA is still starting -> retry with backoff
        this._retryDelay = Math.min((this._retryDelay || 1000) * 2, 30000);
        this._setStatus(this.t.reconnecting);
        clearTimeout(this._retryTimer);
        this._retryTimer = setTimeout(() => this._subscribe(), this._retryDelay);
      });
  }

  _onPayload(payload) {
    if (!payload.loaded && this._data?.loaded) {
      // transient (reload / restart): keep showing the last data for a while
      this._setStatus(this.t.updating);
      if (!this._unloadedTimer) {
        this._unloadedTimer = setTimeout(() => {
          this._unloadedTimer = null;
          this._data = payload;
          this._setStatus("");
          this._render();
        }, 20000);
      }
      return;
    }
    clearTimeout(this._unloadedTimer);
    this._unloadedTimer = null;
    this._setStatus("");
    this._data = payload;
    this._render();
  }

  _setStatus(text) {
    const el = this.shadowRoot.getElementById("status");
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("show", !!text);
  }

  _build() {
    this._built = true;
    const t = this.t;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <span id="menu"></span>
        <h1>${esc(t.title)}</h1>
        <button id="searchAll" title="${esc(t.searchAll)}">⟳ <span class="label">${esc(t.searchAll)}</span></button>
        <button id="add" class="primary">＋ <span class="label">${esc(t.add)}</span></button>
      </div>
      <main>
        <div class="bar">
          <input id="filter" type="search" placeholder="${esc(t.filter)}">
          <span class="stats" id="stats"></span>
        </div>
        <div id="status" class="status"></div>
        <div id="content"></div>
      </main>
      <div id="dialog"></div>`;

    this._menuButton = document.createElement("ha-menu-button");
    this._menuButton.hass = this._hass;
    this._menuButton.narrow = this._narrow;
    this.shadowRoot.getElementById("menu").appendChild(this._menuButton);

    const $ = (id) => this.shadowRoot.getElementById(id);
    $("add").addEventListener("click", () => this._openDialog(null));
    $("searchAll").addEventListener("click", () => this._search(null));
    $("filter").addEventListener("input", (ev) => {
      this._filter = ev.target.value.toLowerCase();
      this._render();
    });
    $("content").addEventListener("click", (ev) => this._onCardClick(ev));
    this._keyHandler = (ev) => {
      if (ev.key === "Escape" && this._dialog) this._closeDialog();
    };
    window.addEventListener("keydown", this._keyHandler);
  }

  _money(value) {
    if (value === null || value === undefined || value === "") return "–";
    const currency = this._data?.currency || "CHF";
    try {
      return new Intl.NumberFormat(this._lang, { style: "currency", currency }).format(value);
    } catch (e) {
      return `${currency} ${Number(value).toFixed(2)}`;
    }
  }

  _relTime(iso) {
    if (!iso) return this.t.never;
    const diff = (new Date(iso).getTime() - Date.now()) / 1000;
    const rtf = new Intl.RelativeTimeFormat(this._lang, { numeric: "auto" });
    const abs = Math.abs(diff);
    if (abs < 60) return rtf.format(Math.round(diff), "second");
    if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
    if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
    return rtf.format(Math.round(diff / 86400), "day");
  }

  _errorText(code) {
    return this.t.errors[code] || code;
  }

  _render() {
    if (!this._built) return;
    const t = this.t;
    const content = this.shadowRoot.getElementById("content");
    const stats = this.shadowRoot.getElementById("stats");
    const addBtn = this.shadowRoot.getElementById("add");
    const searchBtn = this.shadowRoot.getElementById("searchAll");
    const data = this._data;

    if (!data) {
      content.innerHTML = `<div class="notice"><span class="spin"></span></div>`;
      return;
    }
    const loaded = data.loaded;
    addBtn.style.display = loaded && this._isAdmin ? "" : "none";
    searchBtn.style.display = loaded && data.products.length ? "" : "none";
    if (!loaded) {
      stats.innerHTML = "";
      content.innerHTML = `<div class="notice">${esc(t.notLoaded)}</div>`;
      return;
    }

    const products = [...data.products].sort(
      (a, b) => Number(b.below_target) - Number(a.below_target) || a.title.localeCompare(b.title, this._lang)
    );
    const deals = products.filter((p) => p.below_target).length;
    stats.innerHTML = `<b>${products.length}</b> ${esc(t.products)} · <b>${deals}</b> ${esc(t.deals)} · ${esc(
      t.every.replace("{h}", data.scan_interval_hours)
    )}`;

    const visible = products.filter(
      (p) => !this._filter || p.title.toLowerCase().includes(this._filter) || (p.best?.shop || "").toLowerCase().includes(this._filter)
    );
    if (!products.length) {
      content.innerHTML = `<div class="empty">${esc(t.empty)}</div>`;
      return;
    }
    // keep open <details> across re-renders
    const open = new Set([...content.querySelectorAll("details[open]")].map((d) => d.dataset.id));
    content.innerHTML = `<div class="grid">${visible.map((p) => this._card(p, open)).join("")}</div>`;
  }

  _card(p, openSet) {
    const detailsOpen = openSet.has(p.id);
    const t = this.t;
    const best = p.best;
    const target = p.data.target_price;
    const url = safeUrl(best?.url);
    let diff = "";
    if (best && target) {
      const d = best.price - target;
      diff =
        d <= 0
          ? `<div class="diff under">▼ ${esc(this._money(-d))} ${esc(t.underBy)}</div>`
          : `<div class="diff over">▲ ${esc(this._money(d))} ${esc(t.overBy)}</div>`;
    }
    const chips = [
      p.searching ? `<span class="chip busy"><span class="spin"></span>${esc(t.searching)}</span>` : "",
      p.below_target ? `<span class="chip deal">🔥 ${esc(t.belowTarget)}</span>` : "",
    ].join("");
    const warn = p.last_error
      ? `<div class="warn">⚠ ${p.stale ? esc(t.stale) + "<br>" : ""}${esc(t.error)}: ${esc(this._errorText(p.last_error))}</div>`
      : "";
    const hideBtn = (idx) => {
      if (!this._isAdmin) return "";
      const offer = idx === "best" ? p.best : p.offers[idx];
      if (this._pendingBlock === `${p.id}:${idx}` && offer) {
        const shopName = offer.shop || "";
        const shopBtn =
          shopName || offer.url
            ? `<button data-act="block-shop" data-id="${esc(p.id)}" data-idx="${idx}" title="${esc(
                t.hideShopTitle.replace("{shop}", shopName)
              )}">🏪 ${esc(t.hideShop)}</button>`
            : "";
        return `<span class="choice">
          <button data-act="block-offer" data-id="${esc(p.id)}" data-idx="${idx}">${esc(t.hideOffer)}</button>
          ${shopBtn}
          <button class="x" data-act="block-cancel" title="${esc(t.cancel)}">↩</button></span>`;
      }
      return `<button class="x" data-act="block" data-id="${esc(p.id)}" data-idx="${idx}" title="${esc(t.hide)}" aria-label="${esc(t.hide)}">✕</button>`;
    };
    const offers = p.offers.length
      ? `<details data-id="${esc(p.id)}" ${detailsOpen ? "open" : ""}><summary>${esc(t.offers)} (${p.offers.length})</summary>
          <ol class="offers">${p.offers
            .map((o, i) => {
              const ou = safeUrl(o.url);
              const shop = ou ? `<a href="${esc(ou)}" target="_blank" rel="noopener noreferrer">${esc(o.shop)}</a>` : esc(o.shop);
              const title = o.title ? ` <span class="meta">${esc(o.title)}</span>` : "";
              return `<li><span class="txt"><span class="p">${esc(this._money(o.price))}</span> – ${shop}${o.verified ? ` <span class="ok" title="${esc(t.verified)}">✓</span>` : ""}${title}</span>${hideBtn(i)}</li>`;
            })
            .join("")}</ol></details>`
      : "";
    const blockedList = p.blocked || [];
    const blocked =
      blockedList.length && this._isAdmin
        ? `<details data-id="${esc(p.id)}-blocked" ${openSet.has(p.id + "-blocked") ? "open" : ""}>
            <summary>${esc(t.hidden)} (${blockedList.length})</summary>
            <ul class="blocked">${blockedList
              .map(
                (b) => `<li><span class="txt">${
                  b.kind === "shop"
                    ? "🏪 " + esc(t.shopHidden.replace("{shop}", b.display_shop || b.domain || b.shop || ""))
                    : (b.price ? esc(this._money(b.price)) + " – " : "") +
                      esc(b.display_shop || b.shop || "") +
                      (b.display_title ? " · " + esc(b.display_title) : "")
                }</span><button data-act="unblock" data-id="${esc(p.id)}" data-block="${esc(b.id)}">${esc(t.restore)}</button></li>`
              )
              .join("")}</ul>
            ${blockedList.length > 1 ? `<button class="linkbtn" data-act="unblock-all" data-id="${esc(p.id)}">${esc(t.restoreAll)}</button>` : ""}
            <div class="hint">${esc(t.restoreHint)}</div>
          </details>`
        : "";
    const admin = this._isAdmin
      ? `<button data-act="edit" data-id="${esc(p.id)}">✎ ${esc(t.edit)}</button>
         <button data-act="delete" data-id="${esc(p.id)}" class="danger">🗑 ${esc(t.del)}</button>`
      : "";
    return `
      <div class="card ${p.below_target ? "deal" : ""}">
        <div class="top"><div class="name">${esc(p.title)}</div>${chips}</div>
        ${
          best
            ? `<div class="price">${esc(this._money(best.price))}</div>
               <div class="bestline"><div class="meta">${esc(t.at)} ${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(best.shop)}</a>` : esc(best.shop)}
                 · <span class="${best.verified ? "ok" : ""}">${best.verified ? "✓ " + esc(t.verified) : esc(t.unverified)}</span>
                 · ${esc(t.source)}: ${esc(best.source)}</div>${hideBtn("best")}</div>`
            : `<div class="price none">${esc(t.noPrice)}</div>`
        }
        ${diff}
        <div class="rows">
          <span>${esc(t.target)}</span><span>${target ? esc(this._money(target)) : esc(t.noTarget)}</span>
          <span>${esc(t.lowest)}</span><span>${p.lowest_ever ? esc(this._money(p.lowest_ever.price)) + " · " + esc(p.lowest_ever.shop) : "–"}</span>
          <span>${esc(t.checked)}</span><span title="${esc(p.last_checked || "")}">${esc(this._relTime(p.last_checked))}</span>
        </div>
        ${warn}
        ${offers}
        ${blocked}
        <div class="actions">
          <button data-act="search" data-id="${esc(p.id)}" ${p.searching ? "disabled" : ""}>⟳ ${esc(t.search)}</button>
          ${admin}
        </div>
      </div>`;
  }

  _onCardClick(ev) {
    const btn = ev.target.closest("button[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    const product = this._data?.products.find((p) => p.id === id);
    const act = btn.dataset.act;
    if (act === "block") {
      this._pendingBlock = `${id}:${btn.dataset.idx}`;
      this._render();
      return;
    }
    if (act === "block-cancel") {
      this._pendingBlock = null;
      this._render();
      return;
    }
    if ((act === "block-offer" || act === "block-shop") && product) {
      const idx = btn.dataset.idx;
      const offer = idx === "best" ? product.best : product.offers[Number(idx)];
      this._pendingBlock = null;
      if (offer) this._block(product, offer, btn, act === "block-shop" ? "shop" : "offer");
      return;
    }
    if (btn.dataset.act === "unblock" || btn.dataset.act === "unblock-all") {
      this._unblock(id, btn.dataset.act === "unblock" ? btn.dataset.block : null, btn);
      return;
    }
    if (btn.dataset.act === "search") this._search(id);
    else if (btn.dataset.act === "edit" && product) this._openDialog(product);
    else if (btn.dataset.act === "delete" && product) this._delete(product);
  }

  async _search(productId) {
    try {
      await this._hass.callWS(productId ? { type: "deal_finder/search", product_id: productId } : { type: "deal_finder/search" });
    } catch (err) {
      alert(err?.message || err);
    }
  }

  async _block(product, offer, btn, scope) {
    btn.disabled = true;
    try {
      await this._hass.callWS({
        type: "deal_finder/offer/block",
        product_id: product.id,
        scope,
        offer: { url: offer.url || null, shop: offer.shop || null, title: offer.title || null, price: offer.price ?? null },
      });
    } catch (err) {
      btn.disabled = false;
      alert(err?.message || err);
    }
  }

  async _unblock(productId, blockId, btn) {
    btn.disabled = true;
    const msg = { type: "deal_finder/offer/unblock", product_id: productId };
    if (blockId) msg.block_id = blockId;
    try {
      await this._hass.callWS(msg);
    } catch (err) {
      btn.disabled = false;
      alert(err?.message || err);
    }
  }

  async _delete(product) {
    if (!confirm(this.t.confirmDelete.replace("{name}", product.title))) return;
    try {
      await this._hass.callWS({ type: "deal_finder/product/delete", product_id: product.id });
    } catch (err) {
      alert(err?.message || err);
    }
  }

  _openDialog(product) {
    const d = product?.data || {};
    this._dialog = {
      id: product?.id || null,
      values: {
        name: d.name || product?.title || "",
        query: d.query || "",
        target_price: d.target_price ?? "",
        min_price: d.min_price ?? "",
        urls: d.urls || "",
        exclude_terms: d.exclude_terms || "",
        web_search: d.web_search ?? true,
      },
      errors: {},
      saving: false,
    };
    this._renderDialog();
    setTimeout(() => this.shadowRoot.getElementById("f_name")?.focus(), 50);
  }

  _closeDialog() {
    this._dialog = null;
    this.shadowRoot.getElementById("dialog").innerHTML = "";
  }

  _renderDialog() {
    const host = this.shadowRoot.getElementById("dialog");
    const dlg = this._dialog;
    if (!dlg) {
      host.innerHTML = "";
      return;
    }
    const t = this.t;
    const v = dlg.values;
    const e = dlg.errors;
    const err = (k) => (e[k] ? `<div class="err">${esc(this._errorText(e[k]))}</div>` : "");
    const field = (id, label, input, help = "") =>
      `<div class="field"><label for="f_${id}">${esc(label)}</label>${input}${help ? `<div class="help">${esc(help)}</div>` : ""}${err(id)}</div>`;
    host.innerHTML = `
      <div class="overlay" id="overlay">
        <form class="dialog" id="form" autocomplete="off">
          <h2>${esc(dlg.id ? t.editProduct : t.newProduct)}</h2>
          ${e.base ? `<div class="formerr">${esc(this._errorText(e.base))}</div>` : ""}
          ${field("name", t.name, `<input id="f_name" name="name" required value="${esc(v.name)}">`)}
          ${field("query", t.query, `<input id="f_query" name="query" value="${esc(v.query)}">`, t.queryHelp)}
          <div class="two">
            ${field("target_price", t.targetPrice, `<input id="f_target_price" name="target_price" type="number" min="0" step="0.05" value="${esc(v.target_price)}">`)}
            ${field("min_price", t.minPrice, `<input id="f_min_price" name="min_price" type="number" min="0" step="0.05" value="${esc(v.min_price)}">`, t.minHelp)}
          </div>
          ${field("urls", t.urls, `<textarea id="f_urls" name="urls" placeholder="https://www.toppreise.ch/…">${esc(v.urls)}</textarea>`, t.urlsHelp)}
          ${field("exclude_terms", t.exclude, `<input id="f_exclude_terms" name="exclude_terms" value="${esc(v.exclude_terms)}">`, t.excludeHelp)}
          <div class="field">
            <label class="check"><input type="checkbox" name="web_search" ${v.web_search ? "checked" : ""}> ${esc(t.webSearch)}</label>
            ${this._data?.has_web_search ? "" : `<div class="help">${esc(t.noWebSearch)}</div>`}
          </div>
          <div class="actions">
            <button type="button" id="cancel">${esc(t.cancel)}</button>
            <button type="submit" class="primary" ${dlg.saving ? "disabled" : ""}>${dlg.saving ? '<span class="spin"></span>' : ""}${esc(t.save)}</button>
          </div>
        </form>
      </div>`;
    const $ = (id) => this.shadowRoot.getElementById(id);
    $("cancel").addEventListener("click", () => this._closeDialog());
    $("overlay").addEventListener("mousedown", (ev) => {
      if (ev.target.id === "overlay") this._closeDialog();
    });
    $("form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      this._save(ev.target);
    });
  }

  async _save(form) {
    const dlg = this._dialog;
    const fd = new FormData(form);
    dlg.values = {
      name: fd.get("name") || "",
      query: fd.get("query") || "",
      target_price: fd.get("target_price") || "",
      min_price: fd.get("min_price") || "",
      urls: fd.get("urls") || "",
      exclude_terms: fd.get("exclude_terms") || "",
      web_search: fd.get("web_search") === "on",
    };
    dlg.saving = true;
    this._renderDialog();
    const msg = { type: "deal_finder/product/save", data: dlg.values };
    if (dlg.id) msg.product_id = dlg.id;
    try {
      const res = await this._hass.callWS(msg);
      if (res.success) {
        this._closeDialog();
        return;
      }
      dlg.errors = res.errors || {};
    } catch (err) {
      dlg.errors = { base: err?.message || String(err) };
    }
    dlg.saving = false;
    this._renderDialog();
  }
}

if (!customElements.get("deal-finder-panel")) {
  customElements.define("deal-finder-panel", DealFinderPanel);
}
