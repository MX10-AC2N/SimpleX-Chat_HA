/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const T = globalThis, B = T.ShadowRoot && (T.ShadyCSS === void 0 || T.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, D = Symbol(), W = /* @__PURE__ */ new WeakMap();
let it = class {
  constructor(t, e, s) {
    if (this._$cssResult$ = !0, s !== D) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = e;
  }
  get styleSheet() {
    let t = this.o;
    const e = this.t;
    if (B && t === void 0) {
      const s = e !== void 0 && e.length === 1;
      s && (t = W.get(e)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), s && W.set(e, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const dt = (r) => new it(typeof r == "string" ? r : r + "", void 0, D), rt = (r, ...t) => {
  const e = r.length === 1 ? r[0] : t.reduce((s, i, n) => s + ((o) => {
    if (o._$cssResult$ === !0) return o.cssText;
    if (typeof o == "number") return o;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + o + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(i) + r[n + 1], r[0]);
  return new it(e, r, D);
}, ct = (r, t) => {
  if (B) r.adoptedStyleSheets = t.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
  else for (const e of t) {
    const s = document.createElement("style"), i = T.litNonce;
    i !== void 0 && s.setAttribute("nonce", i), s.textContent = e.cssText, r.appendChild(s);
  }
}, X = B ? (r) => r : (r) => r instanceof CSSStyleSheet ? ((t) => {
  let e = "";
  for (const s of t.cssRules) e += s.cssText;
  return dt(e);
})(r) : r;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const { is: pt, defineProperty: ut, getOwnPropertyDescriptor: gt, getOwnPropertyNames: ft, getOwnPropertySymbols: _t, getPrototypeOf: mt } = Object, M = globalThis, q = M.trustedTypes, bt = q ? q.emptyScript : "", $t = M.reactiveElementPolyfillSupport, w = (r, t) => r, N = { toAttribute(r, t) {
  switch (t) {
    case Boolean:
      r = r ? bt : null;
      break;
    case Object:
    case Array:
      r = r == null ? r : JSON.stringify(r);
  }
  return r;
}, fromAttribute(r, t) {
  let e = r;
  switch (t) {
    case Boolean:
      e = r !== null;
      break;
    case Number:
      e = r === null ? null : Number(r);
      break;
    case Object:
    case Array:
      try {
        e = JSON.parse(r);
      } catch {
        e = null;
      }
  }
  return e;
} }, nt = (r, t) => !pt(r, t), F = { attribute: !0, type: String, converter: N, reflect: !1, useDefault: !1, hasChanged: nt };
Symbol.metadata ??= Symbol("metadata"), M.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let $ = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ??= []).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, e = F) {
    if (e.state && (e.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((e = Object.create(e)).wrapped = !0), this.elementProperties.set(t, e), !e.noAccessor) {
      const s = Symbol(), i = this.getPropertyDescriptor(t, s, e);
      i !== void 0 && ut(this.prototype, t, i);
    }
  }
  static getPropertyDescriptor(t, e, s) {
    const { get: i, set: n } = gt(this.prototype, t) ?? { get() {
      return this[e];
    }, set(o) {
      this[e] = o;
    } };
    return { get: i, set(o) {
      const d = i?.call(this);
      n?.call(this, o), this.requestUpdate(t, d, s);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? F;
  }
  static _$Ei() {
    if (this.hasOwnProperty(w("elementProperties"))) return;
    const t = mt(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(w("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(w("properties"))) {
      const e = this.properties, s = [...ft(e), ..._t(e)];
      for (const i of s) this.createProperty(i, e[i]);
    }
    const t = this[Symbol.metadata];
    if (t !== null) {
      const e = litPropertyMetadata.get(t);
      if (e !== void 0) for (const [s, i] of e) this.elementProperties.set(s, i);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [e, s] of this.elementProperties) {
      const i = this._$Eu(e, s);
      i !== void 0 && this._$Eh.set(i, e);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(t) {
    const e = [];
    if (Array.isArray(t)) {
      const s = new Set(t.flat(1 / 0).reverse());
      for (const i of s) e.unshift(X(i));
    } else t !== void 0 && e.push(X(t));
    return e;
  }
  static _$Eu(t, e) {
    const s = e.attribute;
    return s === !1 ? void 0 : typeof s == "string" ? s : typeof t == "string" ? t.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    this._$ES = new Promise((t) => this.enableUpdating = t), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((t) => t(this));
  }
  addController(t) {
    (this._$EO ??= /* @__PURE__ */ new Set()).add(t), this.renderRoot !== void 0 && this.isConnected && t.hostConnected?.();
  }
  removeController(t) {
    this._$EO?.delete(t);
  }
  _$E_() {
    const t = /* @__PURE__ */ new Map(), e = this.constructor.elementProperties;
    for (const s of e.keys()) this.hasOwnProperty(s) && (t.set(s, this[s]), delete this[s]);
    t.size > 0 && (this._$Ep = t);
  }
  createRenderRoot() {
    const t = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return ct(t, this.constructor.elementStyles), t;
  }
  connectedCallback() {
    this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(!0), this._$EO?.forEach((t) => t.hostConnected?.());
  }
  enableUpdating(t) {
  }
  disconnectedCallback() {
    this._$EO?.forEach((t) => t.hostDisconnected?.());
  }
  attributeChangedCallback(t, e, s) {
    this._$AK(t, s);
  }
  _$ET(t, e) {
    const s = this.constructor.elementProperties.get(t), i = this.constructor._$Eu(t, s);
    if (i !== void 0 && s.reflect === !0) {
      const n = (s.converter?.toAttribute !== void 0 ? s.converter : N).toAttribute(e, s.type);
      this._$Em = t, n == null ? this.removeAttribute(i) : this.setAttribute(i, n), this._$Em = null;
    }
  }
  _$AK(t, e) {
    const s = this.constructor, i = s._$Eh.get(t);
    if (i !== void 0 && this._$Em !== i) {
      const n = s.getPropertyOptions(i), o = typeof n.converter == "function" ? { fromAttribute: n.converter } : n.converter?.fromAttribute !== void 0 ? n.converter : N;
      this._$Em = i;
      const d = o.fromAttribute(e, n.type);
      this[i] = d ?? this._$Ej?.get(i) ?? d, this._$Em = null;
    }
  }
  requestUpdate(t, e, s, i = !1, n) {
    if (t !== void 0) {
      const o = this.constructor;
      if (i === !1 && (n = this[t]), s ??= o.getPropertyOptions(t), !((s.hasChanged ?? nt)(n, e) || s.useDefault && s.reflect && n === this._$Ej?.get(t) && !this.hasAttribute(o._$Eu(t, s)))) return;
      this.C(t, e, s);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, e, { useDefault: s, reflect: i, wrapped: n }, o) {
    s && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, o ?? e ?? this[t]), n !== !0 || o !== void 0) || (this._$AL.has(t) || (this.hasUpdated || s || (e = void 0), this._$AL.set(t, e)), i === !0 && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
  }
  async _$EP() {
    this.isUpdatePending = !0;
    try {
      await this._$ES;
    } catch (e) {
      Promise.reject(e);
    }
    const t = this.scheduleUpdate();
    return t != null && await t, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
        for (const [i, n] of this._$Ep) this[i] = n;
        this._$Ep = void 0;
      }
      const s = this.constructor.elementProperties;
      if (s.size > 0) for (const [i, n] of s) {
        const { wrapped: o } = n, d = this[i];
        o !== !0 || this._$AL.has(i) || d === void 0 || this.C(i, void 0, n, d);
      }
    }
    let t = !1;
    const e = this._$AL;
    try {
      t = this.shouldUpdate(e), t ? (this.willUpdate(e), this._$EO?.forEach((s) => s.hostUpdate?.()), this.update(e)) : this._$EM();
    } catch (s) {
      throw t = !1, this._$EM(), s;
    }
    t && this._$AE(e);
  }
  willUpdate(t) {
  }
  _$AE(t) {
    this._$EO?.forEach((e) => e.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(t)), this.updated(t);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(t) {
    return !0;
  }
  update(t) {
    this._$Eq &&= this._$Eq.forEach((e) => this._$ET(e, this[e])), this._$EM();
  }
  updated(t) {
  }
  firstUpdated(t) {
  }
};
$.elementStyles = [], $.shadowRootOptions = { mode: "open" }, $[w("elementProperties")] = /* @__PURE__ */ new Map(), $[w("finalized")] = /* @__PURE__ */ new Map(), $t?.({ ReactiveElement: $ }), (M.reactiveElementVersions ??= []).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const I = globalThis, G = (r) => r, U = I.trustedTypes, Z = U ? U.createPolicy("lit-html", { createHTML: (r) => r }) : void 0, ot = "$lit$", f = `lit$${Math.random().toFixed(9).slice(2)}$`, at = "?" + f, xt = `<${at}>`, b = document, E = () => b.createComment(""), k = (r) => r === null || typeof r != "object" && typeof r != "function", j = Array.isArray, vt = (r) => j(r) || typeof r?.[Symbol.iterator] == "function", H = `[ 	
\f\r]`, y = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, K = /-->/g, J = />/g, _ = RegExp(`>|${H}(?:([^\\s"'>=/]+)(${H}*=${H}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), Y = /'/g, Q = /"/g, lt = /^(?:script|style|textarea|title)$/i, yt = (r) => (t, ...e) => ({ _$litType$: r, strings: t, values: e }), A = yt(1), x = Symbol.for("lit-noChange"), h = Symbol.for("lit-nothing"), tt = /* @__PURE__ */ new WeakMap(), m = b.createTreeWalker(b, 129);
function ht(r, t) {
  if (!j(r) || !r.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return Z !== void 0 ? Z.createHTML(t) : t;
}
const At = (r, t) => {
  const e = r.length - 1, s = [];
  let i, n = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", o = y;
  for (let d = 0; d < e; d++) {
    const a = r[d];
    let c, p, l = -1, u = 0;
    for (; u < a.length && (o.lastIndex = u, p = o.exec(a), p !== null); ) u = o.lastIndex, o === y ? p[1] === "!--" ? o = K : p[1] !== void 0 ? o = J : p[2] !== void 0 ? (lt.test(p[2]) && (i = RegExp("</" + p[2], "g")), o = _) : p[3] !== void 0 && (o = _) : o === _ ? p[0] === ">" ? (o = i ?? y, l = -1) : p[1] === void 0 ? l = -2 : (l = o.lastIndex - p[2].length, c = p[1], o = p[3] === void 0 ? _ : p[3] === '"' ? Q : Y) : o === Q || o === Y ? o = _ : o === K || o === J ? o = y : (o = _, i = void 0);
    const g = o === _ && r[d + 1].startsWith("/>") ? " " : "";
    n += o === y ? a + xt : l >= 0 ? (s.push(c), a.slice(0, l) + ot + a.slice(l) + f + g) : a + f + (l === -2 ? d : g);
  }
  return [ht(r, n + (r[e] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), s];
};
class C {
  constructor({ strings: t, _$litType$: e }, s) {
    let i;
    this.parts = [];
    let n = 0, o = 0;
    const d = t.length - 1, a = this.parts, [c, p] = At(t, e);
    if (this.el = C.createElement(c, s), m.currentNode = this.el.content, e === 2 || e === 3) {
      const l = this.el.content.firstChild;
      l.replaceWith(...l.childNodes);
    }
    for (; (i = m.nextNode()) !== null && a.length < d; ) {
      if (i.nodeType === 1) {
        if (i.hasAttributes()) for (const l of i.getAttributeNames()) if (l.endsWith(ot)) {
          const u = p[o++], g = i.getAttribute(l).split(f), R = /([.?@])?(.*)/.exec(u);
          a.push({ type: 1, index: n, name: R[2], strings: g, ctor: R[1] === "." ? St : R[1] === "?" ? Et : R[1] === "@" ? kt : O }), i.removeAttribute(l);
        } else l.startsWith(f) && (a.push({ type: 6, index: n }), i.removeAttribute(l));
        if (lt.test(i.tagName)) {
          const l = i.textContent.split(f), u = l.length - 1;
          if (u > 0) {
            i.textContent = U ? U.emptyScript : "";
            for (let g = 0; g < u; g++) i.append(l[g], E()), m.nextNode(), a.push({ type: 2, index: ++n });
            i.append(l[u], E());
          }
        }
      } else if (i.nodeType === 8) if (i.data === at) a.push({ type: 2, index: n });
      else {
        let l = -1;
        for (; (l = i.data.indexOf(f, l + 1)) !== -1; ) a.push({ type: 7, index: n }), l += f.length - 1;
      }
      n++;
    }
  }
  static createElement(t, e) {
    const s = b.createElement("template");
    return s.innerHTML = t, s;
  }
}
function v(r, t, e = r, s) {
  if (t === x) return t;
  let i = s !== void 0 ? e._$Co?.[s] : e._$Cl;
  const n = k(t) ? void 0 : t._$litDirective$;
  return i?.constructor !== n && (i?._$AO?.(!1), n === void 0 ? i = void 0 : (i = new n(r), i._$AT(r, e, s)), s !== void 0 ? (e._$Co ??= [])[s] = i : e._$Cl = i), i !== void 0 && (t = v(r, i._$AS(r, t.values), i, s)), t;
}
class wt {
  constructor(t, e) {
    this._$AV = [], this._$AN = void 0, this._$AD = t, this._$AM = e;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(t) {
    const { el: { content: e }, parts: s } = this._$AD, i = (t?.creationScope ?? b).importNode(e, !0);
    m.currentNode = i;
    let n = m.nextNode(), o = 0, d = 0, a = s[0];
    for (; a !== void 0; ) {
      if (o === a.index) {
        let c;
        a.type === 2 ? c = new P(n, n.nextSibling, this, t) : a.type === 1 ? c = new a.ctor(n, a.name, a.strings, this, t) : a.type === 6 && (c = new Ct(n, this, t)), this._$AV.push(c), a = s[++d];
      }
      o !== a?.index && (n = m.nextNode(), o++);
    }
    return m.currentNode = b, i;
  }
  p(t) {
    let e = 0;
    for (const s of this._$AV) s !== void 0 && (s.strings !== void 0 ? (s._$AI(t, s, e), e += s.strings.length - 2) : s._$AI(t[e])), e++;
  }
}
class P {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t, e, s, i) {
    this.type = 2, this._$AH = h, this._$AN = void 0, this._$AA = t, this._$AB = e, this._$AM = s, this.options = i, this._$Cv = i?.isConnected ?? !0;
  }
  get parentNode() {
    let t = this._$AA.parentNode;
    const e = this._$AM;
    return e !== void 0 && t?.nodeType === 11 && (t = e.parentNode), t;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(t, e = this) {
    t = v(this, t, e), k(t) ? t === h || t == null || t === "" ? (this._$AH !== h && this._$AR(), this._$AH = h) : t !== this._$AH && t !== x && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : vt(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== h && k(this._$AH) ? this._$AA.nextSibling.data = t : this.T(b.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    const { values: e, _$litType$: s } = t, i = typeof s == "number" ? this._$AC(t) : (s.el === void 0 && (s.el = C.createElement(ht(s.h, s.h[0]), this.options)), s);
    if (this._$AH?._$AD === i) this._$AH.p(e);
    else {
      const n = new wt(i, this), o = n.u(this.options);
      n.p(e), this.T(o), this._$AH = n;
    }
  }
  _$AC(t) {
    let e = tt.get(t.strings);
    return e === void 0 && tt.set(t.strings, e = new C(t)), e;
  }
  k(t) {
    j(this._$AH) || (this._$AH = [], this._$AR());
    const e = this._$AH;
    let s, i = 0;
    for (const n of t) i === e.length ? e.push(s = new P(this.O(E()), this.O(E()), this, this.options)) : s = e[i], s._$AI(n), i++;
    i < e.length && (this._$AR(s && s._$AB.nextSibling, i), e.length = i);
  }
  _$AR(t = this._$AA.nextSibling, e) {
    for (this._$AP?.(!1, !0, e); t !== this._$AB; ) {
      const s = G(t).nextSibling;
      G(t).remove(), t = s;
    }
  }
  setConnected(t) {
    this._$AM === void 0 && (this._$Cv = t, this._$AP?.(t));
  }
}
class O {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t, e, s, i, n) {
    this.type = 1, this._$AH = h, this._$AN = void 0, this.element = t, this.name = e, this._$AM = i, this.options = n, s.length > 2 || s[0] !== "" || s[1] !== "" ? (this._$AH = Array(s.length - 1).fill(new String()), this.strings = s) : this._$AH = h;
  }
  _$AI(t, e = this, s, i) {
    const n = this.strings;
    let o = !1;
    if (n === void 0) t = v(this, t, e, 0), o = !k(t) || t !== this._$AH && t !== x, o && (this._$AH = t);
    else {
      const d = t;
      let a, c;
      for (t = n[0], a = 0; a < n.length - 1; a++) c = v(this, d[s + a], e, a), c === x && (c = this._$AH[a]), o ||= !k(c) || c !== this._$AH[a], c === h ? t = h : t !== h && (t += (c ?? "") + n[a + 1]), this._$AH[a] = c;
    }
    o && !i && this.j(t);
  }
  j(t) {
    t === h ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class St extends O {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === h ? void 0 : t;
  }
}
class Et extends O {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== h);
  }
}
class kt extends O {
  constructor(t, e, s, i, n) {
    super(t, e, s, i, n), this.type = 5;
  }
  _$AI(t, e = this) {
    if ((t = v(this, t, e, 0) ?? h) === x) return;
    const s = this._$AH, i = t === h && s !== h || t.capture !== s.capture || t.once !== s.once || t.passive !== s.passive, n = t !== h && (s === h || i);
    i && this.element.removeEventListener(this.name, this, s), n && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class Ct {
  constructor(t, e, s) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = e, this.options = s;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    v(this, t);
  }
}
const Pt = I.litHtmlPolyfillSupport;
Pt?.(C, P), (I.litHtmlVersions ??= []).push("3.3.3");
const Rt = (r, t, e) => {
  const s = e?.renderBefore ?? t;
  let i = s._$litPart$;
  if (i === void 0) {
    const n = e?.renderBefore ?? null;
    s._$litPart$ = i = new P(t.insertBefore(E(), n), n, void 0, e ?? {});
  }
  return i._$AI(r), i;
};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const V = globalThis;
class S extends $ {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t.firstChild, t;
  }
  update(t) {
    const e = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = Rt(e, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return x;
  }
}
S._$litElement$ = !0, S.finalized = !0, V.litElementHydrateSupport?.({ LitElement: S });
const Tt = V.litElementPolyfillSupport;
Tt?.({ LitElement: S });
(V.litElementVersions ??= []).push("4.2.2");
const Ut = rt`
  :host {
    --sx-glass-bg: rgba(15, 22, 30, 0.76);
    --sx-glass-border: rgba(219, 237, 248, 0.12);
    --sx-glass-highlight: rgba(255, 255, 255, 0.09);
    --sx-glass-text: #f3f7fa;
    --sx-glass-muted: #9eacb9;
    --sx-glass-accent: #70e0bd;
    --sx-glass-accent-strong: #38c99b;
    --sx-glass-radius: 22px;
    --sx-glass-blur: 22px;

    color: var(--sx-glass-text);
    color-scheme: dark;
    display: block;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system,
      BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  :host([glass-intensity="subtle"]) {
    --sx-glass-bg: rgba(15, 22, 30, 0.9);
    --sx-glass-blur: 12px;
  }

  :host([glass-intensity="strong"]) {
    --sx-glass-bg: rgba(15, 22, 30, 0.62);
    --sx-glass-blur: 30px;
  }

  /* No blur at all (wall tablets, old phones): solid background. */
  :host([glass-intensity="off"]) {
    --sx-glass-bg: #0e151c;
    --sx-glass-blur: 0px;
  }

  * {
    box-sizing: border-box;
  }

  button {
    font: inherit;
  }

  button:focus-visible {
    outline: 2px solid var(--sx-glass-accent);
    outline-offset: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
`, z = "simplex-messenger-card", Mt = "simplex_chat_alias", Ot = 8e3, et = ["hashchange", "popstate", "location-changed"], st = {
  en: {
    inbox: "Conversations",
    subtitle: "Private messenger",
    pill: "Private communication",
    pick: "Select a conversation",
    pickSub: "Choose a contact or a group in the list.",
    back: "Back to conversations",
    loading: "Loading SimpleX…",
    missing: "The SimpleX cards are not loaded. Restart Home Assistant, then reload this page (Ctrl+F5)."
  },
  fr: {
    inbox: "Conversations",
    subtitle: "Messagerie privée",
    pill: "Communication privée",
    pick: "Sélectionnez une conversation",
    pickSub: "Choisissez un contact ou un groupe dans la liste.",
    back: "Retour aux conversations",
    loading: "Chargement de SimpleX…",
    missing: "Les cartes SimpleX ne sont pas chargées. Redémarrez Home Assistant puis rechargez la page (Ctrl+F5)."
  }
};
class Ht extends S {
  constructor() {
    super(...arguments), this._chatOpen = !1, this._hasAlias = !1, this._cards = "loading", this._configuredPrefix = null, this._onRoute = () => this._syncRoute();
  }
  static {
    this.properties = {
      hass: { attribute: !1 },
      _config: { state: !0 },
      _chatOpen: { state: !0 },
      _hasAlias: { state: !0 },
      _cards: { state: !0 }
    };
  }
  static {
    this.styles = [
      Ut,
      rt`
      :host {
        width: 100%;
        min-width: 0;
      }

      .shell {
        position: relative;
        isolation: isolate;
        display: flex;
        flex-direction: column;
        width: 100%;
        min-height: 520px;
        height: min(860px, calc(100vh - 148px));
        overflow: hidden;
        border: 1px solid var(--sx-glass-border);
        border-radius: var(--sx-glass-radius);
        background:
          radial-gradient(ellipse at 8% 0%, rgba(73, 170, 159, 0.17), transparent 36%),
          radial-gradient(ellipse at 92% 100%, rgba(99, 125, 202, 0.13), transparent 38%),
          var(--sx-glass-bg);
        box-shadow:
          0 24px 70px rgba(0, 0, 0, 0.28),
          inset 0 1px 0 var(--sx-glass-highlight);
        backdrop-filter: blur(var(--sx-glass-blur)) saturate(145%);
        -webkit-backdrop-filter: blur(var(--sx-glass-blur)) saturate(145%);
      }

      :host([glass-intensity="off"]) .shell {
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        box-shadow: none;
      }

      .topbar {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        min-height: 64px;
        padding: 10px 20px;
        border-bottom: 1px solid var(--sx-glass-border);
        background: rgba(255, 255, 255, 0.025);
      }

      .brand {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
      }

      .brand-mark {
        display: grid;
        width: 38px;
        height: 38px;
        place-items: center;
        border: 1px solid rgba(112, 224, 189, 0.28);
        border-radius: 13px;
        color: var(--sx-glass-accent);
        background: linear-gradient(145deg, rgba(112, 224, 189, 0.18), rgba(112, 224, 189, 0.045));
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.13);
      }

      .brand-mark svg {
        width: 21px;
        height: 21px;
      }

      .brand-copy {
        display: grid;
        gap: 2px;
        min-width: 0;
      }

      .brand-name {
        font-size: 15px;
        line-height: 1.15;
        font-weight: 720;
        letter-spacing: -0.025em;
      }

      .brand-subtitle {
        color: var(--sx-glass-muted);
        font-size: 10px;
        line-height: 1;
        letter-spacing: 0.15em;
        text-transform: uppercase;
      }

      .privacy-pill {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 7px 10px;
        border: 1px solid rgba(112, 224, 189, 0.17);
        border-radius: 999px;
        background: rgba(112, 224, 189, 0.065);
        color: #b9f4df;
        font-size: 12px;
        white-space: nowrap;
      }

      .privacy-pill svg {
        width: 13px;
        height: 13px;
      }

      .workspace {
        position: relative;
        flex: 1 1 auto;
        display: grid;
        grid-template-columns: minmax(270px, 340px) minmax(0, 1fr);
        min-height: 0;
        overflow: hidden;
      }

      .inbox,
      .thread {
        position: relative;
        min-width: 0;
        min-height: 0;
      }

      .inbox {
        overflow-y: auto;
        border-right: 1px solid var(--sx-glass-border);
        background: rgba(255, 255, 255, 0.018);
        scrollbar-width: thin;
      }

      .thread {
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: rgba(8, 14, 20, 0.16);
      }

      /* Theme the hosted cards through their public CSS variables. */
      simplex-conversations-card,
      simplex-chat-card {
        display: block;
        --simplex-bg: transparent;
        --ha-card-background: transparent;
        --ha-card-box-shadow: none;
        --ha-card-border-width: 0;
        --ha-card-border-radius: 0;
        --ha-card-border-color: transparent;
      }

      simplex-chat-card {
        flex: 1 1 auto;
        min-height: 0;
        width: 100%;
        --simplex-card-height: 100%;
        --simplex-header-bg: rgba(255, 255, 255, 0.045);
        --simplex-bubble-in: rgba(255, 255, 255, 0.1);
        --simplex-bubble-out: rgba(56, 201, 155, 0.78);
      }

      .mobile-bar {
        display: none;
      }

      .placeholder,
      .overlay {
        position: absolute;
        inset: 0;
        z-index: 3;
        display: grid;
        place-items: center;
        padding: 24px;
        color: var(--sx-glass-muted);
        text-align: center;
        font-size: 13px;
      }

      .placeholder {
        pointer-events: none;
        background: rgba(8, 14, 20, 0.35);
      }

      .overlay {
        background: rgba(8, 14, 20, 0.55);
      }

      .placeholder strong {
        display: block;
        margin-bottom: 6px;
        color: var(--sx-glass-text);
        font-size: 15px;
        font-weight: 650;
      }

      .spinner {
        width: 30px;
        height: 30px;
        margin: 0 auto 12px;
        border: 2px solid rgba(112, 224, 189, 0.18);
        border-top-color: var(--sx-glass-accent);
        border-radius: 50%;
        animation: spin 0.9s linear infinite;
      }

      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }

      @media (max-width: 760px) {
        .shell {
          height: calc(100dvh - 112px);
          min-height: 480px;
          border-radius: 16px;
        }

        .topbar {
          min-height: 56px;
          padding: 8px 13px;
        }

        .brand-mark {
          width: 34px;
          height: 34px;
          border-radius: 11px;
        }

        .privacy-pill {
          padding: 6px 8px;
          font-size: 10px;
        }

        .workspace {
          display: block;
        }

        .inbox,
        .thread {
          position: absolute;
          inset: 0;
          border: 0;
        }

        .thread {
          display: none;
        }

        .shell.chat-open .inbox {
          display: none;
        }

        .shell.chat-open .thread {
          display: flex;
        }

        /* Full-screen conversation: the brand bar makes room. */
        .shell.chat-open .topbar {
          display: none;
        }

        .mobile-bar {
          flex: 0 0 auto;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 8px;
          border-bottom: 1px solid var(--sx-glass-border);
          background: rgba(255, 255, 255, 0.025);
        }

        .mobile-back {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 6px 12px 6px 8px;
          border: 1px solid var(--sx-glass-border);
          border-radius: 12px;
          color: var(--sx-glass-text);
          background: rgba(18, 27, 36, 0.6);
          font-size: 13px;
          cursor: pointer;
        }

        .mobile-back svg {
          width: 16px;
          height: 16px;
        }

        .placeholder {
          display: none;
        }
      }

      @media (max-width: 420px) {
        .shell {
          height: calc(100dvh - 96px);
          border-radius: 12px;
        }

        .brand-subtitle {
          display: none;
        }
      }
    `
    ];
  }
  setConfig(t) {
    if (!t) throw new Error("SimpleX Messenger: invalid configuration.");
    this._config = {
      navigate_mode: "hash",
      show_branding: !0,
      show_search: !0,
      glass_intensity: "balanced",
      ...t
    }, this.setAttribute("glass-intensity", this._config.glass_intensity ?? "balanced"), this._syncRoute(), this.hasUpdated && this._cards === "ready" && this._configureChildren();
  }
  connectedCallback() {
    super.connectedCallback();
    for (const t of et) window.addEventListener(t, this._onRoute);
    this._syncRoute();
  }
  disconnectedCallback() {
    for (const t of et) window.removeEventListener(t, this._onRoute);
    window.clearTimeout(this._watchdog), super.disconnectedCallback();
  }
  firstUpdated() {
    this._waitForCards();
  }
  updated(t) {
    t.has("hass") && this._pushHass();
  }
  // ---- route -------------------------------------------------------------
  get _t() {
    return (this.hass?.language ?? "en").slice(0, 2) === "fr" ? st.fr : st.en;
  }
  _syncRoute() {
    const t = window.location.hash.replace(/^#/, "").trim();
    this._chatOpen = t.length > 0;
    let e = this._chatOpen;
    if (!e)
      try {
        e = !!window.sessionStorage.getItem(Mt);
      } catch {
      }
    this._hasAlias = e, this._pushHass(), this._cards === "ready" && !this._config?.navigate_prefix && this._configuredPrefix !== this._viewPath() && this._configureChildren();
  }
  _viewPath() {
    return window.location.pathname.replace(/\/+$/, "") || "/";
  }
  _goBack() {
    const t = new URL(window.location.href);
    t.hash = "", window.history.replaceState(null, "", t), this._syncRoute();
  }
  // ---- hosted cards ------------------------------------------------------
  _card(t) {
    return this.renderRoot.querySelector(t);
  }
  async _waitForCards() {
    const t = Promise.all([
      customElements.whenDefined("simplex-conversations-card"),
      customElements.whenDefined("simplex-chat-card")
    ]).then(() => !0), e = new Promise((i) => {
      this._watchdog = window.setTimeout(() => i(!1), Ot);
    }), s = await Promise.race([t, e]);
    if (window.clearTimeout(this._watchdog), !s) {
      this._cards = "missing";
      return;
    }
    this._configureChildren(), this._cards = "ready", this._pushHass();
  }
  _configureChildren() {
    const t = this._config, e = this._card("simplex-conversations-card"), s = this._card("simplex-chat-card");
    if (!t || !e || !s) return;
    const i = t.navigate_prefix || this._viewPath();
    this._configuredPrefix = t.navigate_prefix ? null : i;
    const n = t.entry_id ? { entry_id: t.entry_id } : {};
    e.setConfig({
      title: t.title || this._t.inbox,
      navigate_prefix: i,
      navigate_mode: t.navigate_mode ?? "hash",
      show_search: t.show_search !== !1,
      ...n
    }), s.setConfig({
      alias: "auto",
      ...t.history_limit ? { history_limit: t.history_limit } : {},
      ...t.auto_mark_read === !1 ? { auto_mark_read: !1 } : {},
      ...t.connection_entity ? { connection_entity: t.connection_entity } : {},
      ...n
    }), this._pushHass();
  }
  _pushHass() {
    if (this._cards !== "ready" || !this.hass) return;
    const t = this._card("simplex-conversations-card"), e = this._card("simplex-chat-card");
    t && (t.hass = this.hass), e && this._hasAlias && (e.hass = this.hass);
  }
  // ---- Lovelace card API -------------------------------------------------
  getCardSize() {
    return 8;
  }
  getGridOptions() {
    return { columns: 12, rows: 8, min_columns: 6, min_rows: 5 };
  }
  static getConfigElement() {
    return document.createElement("simplex-messenger-card-editor");
  }
  static getStubConfig() {
    return { show_branding: !0, glass_intensity: "balanced" };
  }
  // ---- render ------------------------------------------------------------
  _renderTopbar(t) {
    return A`
      <header class="topbar">
        <div class="brand">
          <div class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M4.5 6.8A3.3 3.3 0 0 1 7.8 3.5h8.4a3.3 3.3 0 0 1 3.3 3.3v6.4a3.3 3.3 0 0 1-3.3 3.3h-4.4l-4.6 3.2v-3.2h-.1a3.3 3.3 0 0 1-2.6-3.3V6.8Z"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linejoin="round"
              />
              <path d="M8 8.8h8M8 12h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </div>
          <div class="brand-copy">
            <span class="brand-name">SimpleX</span>
            <span class="brand-subtitle">${t.subtitle}</span>
          </div>
        </div>
        <span class="privacy-pill">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M7 10V7a5 5 0 0 1 10 0v3m-11 0h12v10H6V10Z"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          ${t.pill}
        </span>
      </header>
    `;
  }
  render() {
    if (!this._config) return h;
    const t = this._t;
    return A`
      <section class="shell ${this._chatOpen ? "chat-open" : ""}" aria-label="SimpleX Messenger">
        ${this._config.show_branding !== !1 ? this._renderTopbar(t) : h}

        <div class="workspace">
          <aside class="inbox" aria-label=${t.inbox}>
            <simplex-conversations-card></simplex-conversations-card>
          </aside>

          <main class="thread">
            <div class="mobile-bar">
              <button class="mobile-back" @click=${this._goBack} aria-label=${t.back}>
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="m14.5 5-7 7 7 7"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                ${t.inbox}
              </button>
            </div>
            <simplex-chat-card></simplex-chat-card>
            ${!this._hasAlias && this._cards === "ready" ? A`<div class="placeholder">
                  <div><strong>${t.pick}</strong>${t.pickSub}</div>
                </div>` : h}
          </main>

          ${this._cards !== "ready" ? A`<div class="overlay" role="status">
                <div>
                  ${this._cards === "loading" ? A`<div class="spinner"></div>` : h}
                  ${this._cards === "loading" ? t.loading : t.missing}
                </div>
              </div>` : h}
        </div>
      </section>
    `;
  }
}
customElements.get(z) || customElements.define(z, Ht);
const L = window;
L.customCards = L.customCards || [];
L.customCards.push({
  type: z,
  name: "SimpleX Messenger",
  description: "Glass messenger: conversation list and chat in one responsive view.",
  preview: !1
});
