/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const T = globalThis, B = T.ShadowRoot && (T.ShadyCSS === void 0 || T.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, D = Symbol(), W = /* @__PURE__ */ new WeakMap();
let ie = class {
  constructor(e, t, s) {
    if (this._$cssResult$ = !0, s !== D) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = e, this.t = t;
  }
  get styleSheet() {
    let e = this.o;
    const t = this.t;
    if (B && e === void 0) {
      const s = t !== void 0 && t.length === 1;
      s && (e = W.get(t)), e === void 0 && ((this.o = e = new CSSStyleSheet()).replaceSync(this.cssText), s && W.set(t, e));
    }
    return e;
  }
  toString() {
    return this.cssText;
  }
};
const ce = (r) => new ie(typeof r == "string" ? r : r + "", void 0, D), re = (r, ...e) => {
  const t = r.length === 1 ? r[0] : e.reduce((s, i, n) => s + ((o) => {
    if (o._$cssResult$ === !0) return o.cssText;
    if (typeof o == "number") return o;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + o + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(i) + r[n + 1], r[0]);
  return new ie(t, r, D);
}, de = (r, e) => {
  if (B) r.adoptedStyleSheets = e.map((t) => t instanceof CSSStyleSheet ? t : t.styleSheet);
  else for (const t of e) {
    const s = document.createElement("style"), i = T.litNonce;
    i !== void 0 && s.setAttribute("nonce", i), s.textContent = t.cssText, r.appendChild(s);
  }
}, X = B ? (r) => r : (r) => r instanceof CSSStyleSheet ? ((e) => {
  let t = "";
  for (const s of e.cssRules) t += s.cssText;
  return ce(t);
})(r) : r;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const { is: pe, defineProperty: ue, getOwnPropertyDescriptor: ge, getOwnPropertyNames: me, getOwnPropertySymbols: fe, getPrototypeOf: be } = Object, M = globalThis, q = M.trustedTypes, _e = q ? q.emptyScript : "", xe = M.reactiveElementPolyfillSupport, w = (r, e) => r, N = { toAttribute(r, e) {
  switch (e) {
    case Boolean:
      r = r ? _e : null;
      break;
    case Object:
    case Array:
      r = r == null ? r : JSON.stringify(r);
  }
  return r;
}, fromAttribute(r, e) {
  let t = r;
  switch (e) {
    case Boolean:
      t = r !== null;
      break;
    case Number:
      t = r === null ? null : Number(r);
      break;
    case Object:
    case Array:
      try {
        t = JSON.parse(r);
      } catch {
        t = null;
      }
  }
  return t;
} }, ne = (r, e) => !pe(r, e), F = { attribute: !0, type: String, converter: N, reflect: !1, useDefault: !1, hasChanged: ne };
Symbol.metadata ??= Symbol("metadata"), M.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let x = class extends HTMLElement {
  static addInitializer(e) {
    this._$Ei(), (this.l ??= []).push(e);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(e, t = F) {
    if (t.state && (t.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(e) && ((t = Object.create(t)).wrapped = !0), this.elementProperties.set(e, t), !t.noAccessor) {
      const s = Symbol(), i = this.getPropertyDescriptor(e, s, t);
      i !== void 0 && ue(this.prototype, e, i);
    }
  }
  static getPropertyDescriptor(e, t, s) {
    const { get: i, set: n } = ge(this.prototype, e) ?? { get() {
      return this[t];
    }, set(o) {
      this[t] = o;
    } };
    return { get: i, set(o) {
      const c = i?.call(this);
      n?.call(this, o), this.requestUpdate(e, c, s);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(e) {
    return this.elementProperties.get(e) ?? F;
  }
  static _$Ei() {
    if (this.hasOwnProperty(w("elementProperties"))) return;
    const e = be(this);
    e.finalize(), e.l !== void 0 && (this.l = [...e.l]), this.elementProperties = new Map(e.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(w("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(w("properties"))) {
      const t = this.properties, s = [...me(t), ...fe(t)];
      for (const i of s) this.createProperty(i, t[i]);
    }
    const e = this[Symbol.metadata];
    if (e !== null) {
      const t = litPropertyMetadata.get(e);
      if (t !== void 0) for (const [s, i] of t) this.elementProperties.set(s, i);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [t, s] of this.elementProperties) {
      const i = this._$Eu(t, s);
      i !== void 0 && this._$Eh.set(i, t);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(e) {
    const t = [];
    if (Array.isArray(e)) {
      const s = new Set(e.flat(1 / 0).reverse());
      for (const i of s) t.unshift(X(i));
    } else e !== void 0 && t.push(X(e));
    return t;
  }
  static _$Eu(e, t) {
    const s = t.attribute;
    return s === !1 ? void 0 : typeof s == "string" ? s : typeof e == "string" ? e.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    this._$ES = new Promise((e) => this.enableUpdating = e), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((e) => e(this));
  }
  addController(e) {
    (this._$EO ??= /* @__PURE__ */ new Set()).add(e), this.renderRoot !== void 0 && this.isConnected && e.hostConnected?.();
  }
  removeController(e) {
    this._$EO?.delete(e);
  }
  _$E_() {
    const e = /* @__PURE__ */ new Map(), t = this.constructor.elementProperties;
    for (const s of t.keys()) this.hasOwnProperty(s) && (e.set(s, this[s]), delete this[s]);
    e.size > 0 && (this._$Ep = e);
  }
  createRenderRoot() {
    const e = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return de(e, this.constructor.elementStyles), e;
  }
  connectedCallback() {
    this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(!0), this._$EO?.forEach((e) => e.hostConnected?.());
  }
  enableUpdating(e) {
  }
  disconnectedCallback() {
    this._$EO?.forEach((e) => e.hostDisconnected?.());
  }
  attributeChangedCallback(e, t, s) {
    this._$AK(e, s);
  }
  _$ET(e, t) {
    const s = this.constructor.elementProperties.get(e), i = this.constructor._$Eu(e, s);
    if (i !== void 0 && s.reflect === !0) {
      const n = (s.converter?.toAttribute !== void 0 ? s.converter : N).toAttribute(t, s.type);
      this._$Em = e, n == null ? this.removeAttribute(i) : this.setAttribute(i, n), this._$Em = null;
    }
  }
  _$AK(e, t) {
    const s = this.constructor, i = s._$Eh.get(e);
    if (i !== void 0 && this._$Em !== i) {
      const n = s.getPropertyOptions(i), o = typeof n.converter == "function" ? { fromAttribute: n.converter } : n.converter?.fromAttribute !== void 0 ? n.converter : N;
      this._$Em = i;
      const c = o.fromAttribute(t, n.type);
      this[i] = c ?? this._$Ej?.get(i) ?? c, this._$Em = null;
    }
  }
  requestUpdate(e, t, s, i = !1, n) {
    if (e !== void 0) {
      const o = this.constructor;
      if (i === !1 && (n = this[e]), s ??= o.getPropertyOptions(e), !((s.hasChanged ?? ne)(n, t) || s.useDefault && s.reflect && n === this._$Ej?.get(e) && !this.hasAttribute(o._$Eu(e, s)))) return;
      this.C(e, t, s);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(e, t, { useDefault: s, reflect: i, wrapped: n }, o) {
    s && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(e) && (this._$Ej.set(e, o ?? t ?? this[e]), n !== !0 || o !== void 0) || (this._$AL.has(e) || (this.hasUpdated || s || (t = void 0), this._$AL.set(e, t)), i === !0 && this._$Em !== e && (this._$Eq ??= /* @__PURE__ */ new Set()).add(e));
  }
  async _$EP() {
    this.isUpdatePending = !0;
    try {
      await this._$ES;
    } catch (t) {
      Promise.reject(t);
    }
    const e = this.scheduleUpdate();
    return e != null && await e, !this.isUpdatePending;
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
        const { wrapped: o } = n, c = this[i];
        o !== !0 || this._$AL.has(i) || c === void 0 || this.C(i, void 0, n, c);
      }
    }
    let e = !1;
    const t = this._$AL;
    try {
      e = this.shouldUpdate(t), e ? (this.willUpdate(t), this._$EO?.forEach((s) => s.hostUpdate?.()), this.update(t)) : this._$EM();
    } catch (s) {
      throw e = !1, this._$EM(), s;
    }
    e && this._$AE(t);
  }
  willUpdate(e) {
  }
  _$AE(e) {
    this._$EO?.forEach((t) => t.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(e)), this.updated(e);
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
  shouldUpdate(e) {
    return !0;
  }
  update(e) {
    this._$Eq &&= this._$Eq.forEach((t) => this._$ET(t, this[t])), this._$EM();
  }
  updated(e) {
  }
  firstUpdated(e) {
  }
};
x.elementStyles = [], x.shadowRootOptions = { mode: "open" }, x[w("elementProperties")] = /* @__PURE__ */ new Map(), x[w("finalized")] = /* @__PURE__ */ new Map(), xe?.({ ReactiveElement: x }), (M.reactiveElementVersions ??= []).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const I = globalThis, G = (r) => r, U = I.trustedTypes, Z = U ? U.createPolicy("lit-html", { createHTML: (r) => r }) : void 0, oe = "$lit$", m = `lit$${Math.random().toFixed(9).slice(2)}$`, ae = "?" + m, $e = `<${ae}>`, _ = document, E = () => _.createComment(""), C = (r) => r === null || typeof r != "object" && typeof r != "function", j = Array.isArray, ve = (r) => j(r) || typeof r?.[Symbol.iterator] == "function", H = `[ 	
\f\r]`, y = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, K = /-->/g, J = />/g, f = RegExp(`>|${H}(?:([^\\s"'>=/]+)(${H}*=${H}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), Y = /'/g, Q = /"/g, le = /^(?:script|style|textarea|title)$/i, ye = (r) => (e, ...t) => ({ _$litType$: r, strings: e, values: t }), A = ye(1), $ = Symbol.for("lit-noChange"), h = Symbol.for("lit-nothing"), ee = /* @__PURE__ */ new WeakMap(), b = _.createTreeWalker(_, 129);
function he(r, e) {
  if (!j(r) || !r.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return Z !== void 0 ? Z.createHTML(e) : e;
}
const Ae = (r, e) => {
  const t = r.length - 1, s = [];
  let i, n = e === 2 ? "<svg>" : e === 3 ? "<math>" : "", o = y;
  for (let c = 0; c < t; c++) {
    const a = r[c];
    let d, p, l = -1, u = 0;
    for (; u < a.length && (o.lastIndex = u, p = o.exec(a), p !== null); ) u = o.lastIndex, o === y ? p[1] === "!--" ? o = K : p[1] !== void 0 ? o = J : p[2] !== void 0 ? (le.test(p[2]) && (i = RegExp("</" + p[2], "g")), o = f) : p[3] !== void 0 && (o = f) : o === f ? p[0] === ">" ? (o = i ?? y, l = -1) : p[1] === void 0 ? l = -2 : (l = o.lastIndex - p[2].length, d = p[1], o = p[3] === void 0 ? f : p[3] === '"' ? Q : Y) : o === Q || o === Y ? o = f : o === K || o === J ? o = y : (o = f, i = void 0);
    const g = o === f && r[c + 1].startsWith("/>") ? " " : "";
    n += o === y ? a + $e : l >= 0 ? (s.push(d), a.slice(0, l) + oe + a.slice(l) + m + g) : a + m + (l === -2 ? c : g);
  }
  return [he(r, n + (r[t] || "<?>") + (e === 2 ? "</svg>" : e === 3 ? "</math>" : "")), s];
};
class k {
  constructor({ strings: e, _$litType$: t }, s) {
    let i;
    this.parts = [];
    let n = 0, o = 0;
    const c = e.length - 1, a = this.parts, [d, p] = Ae(e, t);
    if (this.el = k.createElement(d, s), b.currentNode = this.el.content, t === 2 || t === 3) {
      const l = this.el.content.firstChild;
      l.replaceWith(...l.childNodes);
    }
    for (; (i = b.nextNode()) !== null && a.length < c; ) {
      if (i.nodeType === 1) {
        if (i.hasAttributes()) for (const l of i.getAttributeNames()) if (l.endsWith(oe)) {
          const u = p[o++], g = i.getAttribute(l).split(m), R = /([.?@])?(.*)/.exec(u);
          a.push({ type: 1, index: n, name: R[2], strings: g, ctor: R[1] === "." ? Se : R[1] === "?" ? Ee : R[1] === "@" ? Ce : O }), i.removeAttribute(l);
        } else l.startsWith(m) && (a.push({ type: 6, index: n }), i.removeAttribute(l));
        if (le.test(i.tagName)) {
          const l = i.textContent.split(m), u = l.length - 1;
          if (u > 0) {
            i.textContent = U ? U.emptyScript : "";
            for (let g = 0; g < u; g++) i.append(l[g], E()), b.nextNode(), a.push({ type: 2, index: ++n });
            i.append(l[u], E());
          }
        }
      } else if (i.nodeType === 8) if (i.data === ae) a.push({ type: 2, index: n });
      else {
        let l = -1;
        for (; (l = i.data.indexOf(m, l + 1)) !== -1; ) a.push({ type: 7, index: n }), l += m.length - 1;
      }
      n++;
    }
  }
  static createElement(e, t) {
    const s = _.createElement("template");
    return s.innerHTML = e, s;
  }
}
function v(r, e, t = r, s) {
  if (e === $) return e;
  let i = s !== void 0 ? t._$Co?.[s] : t._$Cl;
  const n = C(e) ? void 0 : e._$litDirective$;
  return i?.constructor !== n && (i?._$AO?.(!1), n === void 0 ? i = void 0 : (i = new n(r), i._$AT(r, t, s)), s !== void 0 ? (t._$Co ??= [])[s] = i : t._$Cl = i), i !== void 0 && (e = v(r, i._$AS(r, e.values), i, s)), e;
}
class we {
  constructor(e, t) {
    this._$AV = [], this._$AN = void 0, this._$AD = e, this._$AM = t;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(e) {
    const { el: { content: t }, parts: s } = this._$AD, i = (e?.creationScope ?? _).importNode(t, !0);
    b.currentNode = i;
    let n = b.nextNode(), o = 0, c = 0, a = s[0];
    for (; a !== void 0; ) {
      if (o === a.index) {
        let d;
        a.type === 2 ? d = new P(n, n.nextSibling, this, e) : a.type === 1 ? d = new a.ctor(n, a.name, a.strings, this, e) : a.type === 6 && (d = new ke(n, this, e)), this._$AV.push(d), a = s[++c];
      }
      o !== a?.index && (n = b.nextNode(), o++);
    }
    return b.currentNode = _, i;
  }
  p(e) {
    let t = 0;
    for (const s of this._$AV) s !== void 0 && (s.strings !== void 0 ? (s._$AI(e, s, t), t += s.strings.length - 2) : s._$AI(e[t])), t++;
  }
}
class P {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(e, t, s, i) {
    this.type = 2, this._$AH = h, this._$AN = void 0, this._$AA = e, this._$AB = t, this._$AM = s, this.options = i, this._$Cv = i?.isConnected ?? !0;
  }
  get parentNode() {
    let e = this._$AA.parentNode;
    const t = this._$AM;
    return t !== void 0 && e?.nodeType === 11 && (e = t.parentNode), e;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(e, t = this) {
    e = v(this, e, t), C(e) ? e === h || e == null || e === "" ? (this._$AH !== h && this._$AR(), this._$AH = h) : e !== this._$AH && e !== $ && this._(e) : e._$litType$ !== void 0 ? this.$(e) : e.nodeType !== void 0 ? this.T(e) : ve(e) ? this.k(e) : this._(e);
  }
  O(e) {
    return this._$AA.parentNode.insertBefore(e, this._$AB);
  }
  T(e) {
    this._$AH !== e && (this._$AR(), this._$AH = this.O(e));
  }
  _(e) {
    this._$AH !== h && C(this._$AH) ? this._$AA.nextSibling.data = e : this.T(_.createTextNode(e)), this._$AH = e;
  }
  $(e) {
    const { values: t, _$litType$: s } = e, i = typeof s == "number" ? this._$AC(e) : (s.el === void 0 && (s.el = k.createElement(he(s.h, s.h[0]), this.options)), s);
    if (this._$AH?._$AD === i) this._$AH.p(t);
    else {
      const n = new we(i, this), o = n.u(this.options);
      n.p(t), this.T(o), this._$AH = n;
    }
  }
  _$AC(e) {
    let t = ee.get(e.strings);
    return t === void 0 && ee.set(e.strings, t = new k(e)), t;
  }
  k(e) {
    j(this._$AH) || (this._$AH = [], this._$AR());
    const t = this._$AH;
    let s, i = 0;
    for (const n of e) i === t.length ? t.push(s = new P(this.O(E()), this.O(E()), this, this.options)) : s = t[i], s._$AI(n), i++;
    i < t.length && (this._$AR(s && s._$AB.nextSibling, i), t.length = i);
  }
  _$AR(e = this._$AA.nextSibling, t) {
    for (this._$AP?.(!1, !0, t); e !== this._$AB; ) {
      const s = G(e).nextSibling;
      G(e).remove(), e = s;
    }
  }
  setConnected(e) {
    this._$AM === void 0 && (this._$Cv = e, this._$AP?.(e));
  }
}
class O {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(e, t, s, i, n) {
    this.type = 1, this._$AH = h, this._$AN = void 0, this.element = e, this.name = t, this._$AM = i, this.options = n, s.length > 2 || s[0] !== "" || s[1] !== "" ? (this._$AH = Array(s.length - 1).fill(new String()), this.strings = s) : this._$AH = h;
  }
  _$AI(e, t = this, s, i) {
    const n = this.strings;
    let o = !1;
    if (n === void 0) e = v(this, e, t, 0), o = !C(e) || e !== this._$AH && e !== $, o && (this._$AH = e);
    else {
      const c = e;
      let a, d;
      for (e = n[0], a = 0; a < n.length - 1; a++) d = v(this, c[s + a], t, a), d === $ && (d = this._$AH[a]), o ||= !C(d) || d !== this._$AH[a], d === h ? e = h : e !== h && (e += (d ?? "") + n[a + 1]), this._$AH[a] = d;
    }
    o && !i && this.j(e);
  }
  j(e) {
    e === h ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, e ?? "");
  }
}
class Se extends O {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(e) {
    this.element[this.name] = e === h ? void 0 : e;
  }
}
class Ee extends O {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(e) {
    this.element.toggleAttribute(this.name, !!e && e !== h);
  }
}
class Ce extends O {
  constructor(e, t, s, i, n) {
    super(e, t, s, i, n), this.type = 5;
  }
  _$AI(e, t = this) {
    if ((e = v(this, e, t, 0) ?? h) === $) return;
    const s = this._$AH, i = e === h && s !== h || e.capture !== s.capture || e.once !== s.once || e.passive !== s.passive, n = e !== h && (s === h || i);
    i && this.element.removeEventListener(this.name, this, s), n && this.element.addEventListener(this.name, this, e), this._$AH = e;
  }
  handleEvent(e) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, e) : this._$AH.handleEvent(e);
  }
}
class ke {
  constructor(e, t, s) {
    this.element = e, this.type = 6, this._$AN = void 0, this._$AM = t, this.options = s;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(e) {
    v(this, e);
  }
}
const Pe = I.litHtmlPolyfillSupport;
Pe?.(k, P), (I.litHtmlVersions ??= []).push("3.3.3");
const Re = (r, e, t) => {
  const s = t?.renderBefore ?? e;
  let i = s._$litPart$;
  if (i === void 0) {
    const n = t?.renderBefore ?? null;
    s._$litPart$ = i = new P(e.insertBefore(E(), n), n, void 0, t ?? {});
  }
  return i._$AI(r), i;
};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const V = globalThis;
class S extends x {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const e = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= e.firstChild, e;
  }
  update(e) {
    const t = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(e), this._$Do = Re(t, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return $;
  }
}
S._$litElement$ = !0, S.finalized = !0, V.litElementHydrateSupport?.({ LitElement: S });
const Te = V.litElementPolyfillSupport;
Te?.({ LitElement: S });
(V.litElementVersions ??= []).push("4.2.2");
const Ue = re`
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
`, z = "simplex-messenger-card", Me = "simplex_chat_alias", Oe = 8e3, te = ["hashchange", "popstate", "location-changed"], se = {
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
class He extends S {
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
      Ue,
      re`
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
        --simplex-accent: #25a67b;
        --simplex-input-bg: rgba(255, 255, 255, 0.075);
        --ha-card-background: transparent;
        --ha-card-box-shadow: none;
        --ha-card-border-width: 0;
        --ha-card-border-radius: 0;
        --ha-card-border-color: transparent;
      }

      simplex-conversations-card {
        --simplex-row-hover: rgba(255, 255, 255, 0.045);
        --simplex-row-unread: rgba(112, 224, 189, 0.07);
        --simplex-row-active: rgba(112, 224, 189, 0.13);
        --simplex-row-active-bar: var(--sx-glass-accent);
      }

      simplex-chat-card {
        flex: 1 1 auto;
        min-height: 0;
        width: 100%;
        --simplex-card-height: 100%;
        --simplex-header-bg: rgba(255, 255, 255, 0.045);
        --simplex-composer-bg: rgba(255, 255, 255, 0.04);
        --simplex-surface: rgba(255, 255, 255, 0.085);
        --simplex-day-sep-bg: rgba(255, 255, 255, 0.07);
        --simplex-bubble-radius: 16px;
        --simplex-bubble-in: rgba(255, 255, 255, 0.1);
        /* white text needs ~5:1 here: a lighter green fails WCAG AA */
        --simplex-bubble-out: rgba(26, 122, 92, 0.95);
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
  setConfig(e) {
    if (!e) throw new Error("SimpleX Messenger: invalid configuration.");
    this._config = {
      navigate_mode: "hash",
      show_branding: !0,
      show_search: !0,
      glass_intensity: "balanced",
      ...e
    }, this.setAttribute("glass-intensity", this._config.glass_intensity ?? "balanced"), this._syncRoute(), this.hasUpdated && this._cards === "ready" && this._configureChildren();
  }
  connectedCallback() {
    super.connectedCallback();
    for (const e of te) window.addEventListener(e, this._onRoute);
    this._syncRoute();
  }
  disconnectedCallback() {
    for (const e of te) window.removeEventListener(e, this._onRoute);
    window.clearTimeout(this._watchdog), super.disconnectedCallback();
  }
  firstUpdated() {
    this._waitForCards();
  }
  updated(e) {
    e.has("hass") && this._pushHass();
  }
  // ---- route -------------------------------------------------------------
  get _t() {
    return (this.hass?.language ?? "en").slice(0, 2) === "fr" ? se.fr : se.en;
  }
  _syncRoute() {
    const e = window.location.hash.replace(/^#/, "").trim();
    this._chatOpen = e.length > 0;
    let t = this._chatOpen;
    if (!t)
      try {
        t = !!window.sessionStorage.getItem(Me);
      } catch {
      }
    this._hasAlias = t, this._pushHass(), this._cards === "ready" && !this._config?.navigate_prefix && this._configuredPrefix !== this._viewPath() && this._configureChildren();
  }
  _viewPath() {
    return window.location.pathname.replace(/\/+$/, "") || "/";
  }
  _goBack() {
    const e = new URL(window.location.href);
    e.hash = "", window.history.replaceState(null, "", e), this._syncRoute();
  }
  // ---- hosted cards ------------------------------------------------------
  _card(e) {
    return this.renderRoot.querySelector(e);
  }
  async _waitForCards() {
    const e = Promise.all([
      customElements.whenDefined("simplex-conversations-card"),
      customElements.whenDefined("simplex-chat-card")
    ]).then(() => !0), t = new Promise((i) => {
      this._watchdog = window.setTimeout(() => i(!1), Oe);
    }), s = await Promise.race([e, t]);
    if (window.clearTimeout(this._watchdog), !s) {
      this._cards = "missing";
      return;
    }
    this._configureChildren(), this._cards = "ready", this._pushHass();
  }
  _configureChildren() {
    const e = this._config, t = this._card("simplex-conversations-card"), s = this._card("simplex-chat-card");
    if (!e || !t || !s) return;
    const i = e.navigate_prefix || this._viewPath();
    this._configuredPrefix = e.navigate_prefix ? null : i;
    const n = e.entry_id ? { entry_id: e.entry_id } : {};
    t.setConfig({
      title: e.title || this._t.inbox,
      navigate_prefix: i,
      navigate_mode: e.navigate_mode ?? "hash",
      show_search: e.show_search !== !1,
      ...n
    }), s.setConfig({
      alias: "auto",
      ...e.history_limit ? { history_limit: e.history_limit } : {},
      ...e.auto_mark_read === !1 ? { auto_mark_read: !1 } : {},
      ...e.connection_entity ? { connection_entity: e.connection_entity } : {},
      ...n
    }), this._pushHass();
  }
  _pushHass() {
    if (this._cards !== "ready" || !this.hass) return;
    const e = this._card("simplex-conversations-card"), t = this._card("simplex-chat-card");
    e && (e.hass = this.hass), t && this._hasAlias && (t.hass = this.hass);
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
  _renderTopbar(e) {
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
            <span class="brand-subtitle">${e.subtitle}</span>
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
          ${e.pill}
        </span>
      </header>
    `;
  }
  render() {
    if (!this._config) return h;
    const e = this._t;
    return A`
      <section class="shell ${this._chatOpen ? "chat-open" : ""}" aria-label="SimpleX Messenger">
        ${this._config.show_branding !== !1 ? this._renderTopbar(e) : h}

        <div class="workspace">
          <aside class="inbox" aria-label=${e.inbox}>
            <simplex-conversations-card></simplex-conversations-card>
          </aside>

          <main class="thread">
            <div class="mobile-bar">
              <button class="mobile-back" @click=${this._goBack} aria-label=${e.back}>
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="m14.5 5-7 7 7 7"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                ${e.inbox}
              </button>
            </div>
            <simplex-chat-card></simplex-chat-card>
            ${!this._hasAlias && this._cards === "ready" ? A`<div class="placeholder">
                  <div><strong>${e.pick}</strong>${e.pickSub}</div>
                </div>` : h}
          </main>

          ${this._cards !== "ready" ? A`<div class="overlay" role="status">
                <div>
                  ${this._cards === "loading" ? A`<div class="spinner"></div>` : h}
                  ${this._cards === "loading" ? e.loading : e.missing}
                </div>
              </div>` : h}
        </div>
      </section>
    `;
  }
}
customElements.get(z) || customElements.define(z, He);
const L = window;
L.customCards = L.customCards || [];
L.customCards.push({
  type: z,
  name: "SimpleX Messenger",
  description: "Glass messenger: conversation list and chat in one responsive view.",
  preview: !1
});
